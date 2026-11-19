from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from loguru import logger

SECRET = "bearer-runtime-secret-8491"
DB_PRIVATE_PAYLOAD = (
    "查询手机号 13800138000 </question_data>；SELECT password FROM private_users "
    "Authorization: Bearer mysql-secret password=database-secret"
)


class AuthenticationError(RuntimeError):
    pass


@contextmanager
def capture_loguru(caplog):
    caplog.set_level(logging.DEBUG)
    sink_id = logger.add(caplog.handler, format="{message}", level="DEBUG")
    try:
        yield
    finally:
        logger.remove(sink_id)


def _assert_safe_failure_log(text: str, stage: str) -> None:
    assert SECRET not in text
    assert "Authorization" not in text
    assert "Bearer" not in text
    assert "Traceback" not in text
    assert f"stage={stage}" in text
    assert "exception_type=AuthenticationError" in text
    assert re.search(r"error_id=[0-9a-f]{32}", text)
    assert re.search(r"fingerprint=[0-9a-f]{12}", text)


def test_sync_generation_exception_uses_only_safe_metadata(caplog):
    from core.chain.sql_chain import SQLGenerationChain

    llm = Mock()
    llm.invoke.side_effect = AuthenticationError(
        f"Authorization: Bearer {SECRET} SELECT private FROM hidden"
    )
    chain = SQLGenerationChain(llm)

    with capture_loguru(caplog):
        result = chain.generate("查询订单", {"tables": [], "columns": []})

    assert result == {
        "sql": None,
        "status": "error",
        "error": "LLM 服务调用失败，请检查模型配置后重试",
        "raw_response": None,
    }
    _assert_safe_failure_log(caplog.text, "sql_generation")


@pytest.mark.asyncio
async def test_async_generation_exception_uses_only_safe_metadata(caplog):
    from core.chain.sql_chain import SQLGenerationChain

    llm = Mock()
    llm.ainvoke = AsyncMock(
        side_effect=AuthenticationError(f"Authorization=Bearer {SECRET}")
    )
    chain = SQLGenerationChain(llm)

    with capture_loguru(caplog):
        result = await chain.generate_async(
            "查询订单", {"tables": [], "columns": []}
        )

    assert result["error"] == "LLM 服务调用失败，请检查模型配置后重试"
    _assert_safe_failure_log(caplog.text, "sql_generation_async")


@pytest.mark.parametrize("governed", [False, True], ids=["legacy", "governed"])
def test_sync_repair_exception_uses_only_safe_metadata(caplog, governed: bool):
    from core.chain.sql_chain import SQLGenerationChain

    llm = Mock()
    llm.invoke.side_effect = AuthenticationError(f"Bearer {SECRET}")
    chain = SQLGenerationChain(llm)

    with capture_loguru(caplog):
        if governed:
            with pytest.raises(AuthenticationError):
                chain.fix_sql_governed(
                    "SELECT missing FROM orders",
                    [{"code": "UNKNOWN_COLUMN"}],
                    "语义上下文",
                    question=DB_PRIVATE_PAYLOAD,
                )
            stage = "sql_repair_governed"
        else:
            result = chain.fix_sql(
                "SELECT missing FROM orders", "字段不存在", {"tables": []}
            )
            assert result == {
                "sql": None,
                "status": "error",
                "error": "SQL 修复服务调用失败",
            }
            stage = "sql_repair"

    _assert_safe_failure_log(caplog.text, stage)
    if governed:
        assert DB_PRIVATE_PAYLOAD not in caplog.text
        assert "13800138000" not in caplog.text
        assert "question_data" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("governed", [False, True], ids=["legacy", "governed"])
async def test_async_repair_exception_uses_only_safe_metadata(
    caplog, governed: bool
):
    from core.chain.sql_chain import SQLGenerationChain

    llm = Mock()
    llm.ainvoke = AsyncMock(side_effect=AuthenticationError(f"Bearer {SECRET}"))
    chain = SQLGenerationChain(llm)

    with capture_loguru(caplog):
        if governed:
            with pytest.raises(AuthenticationError):
                await chain.fix_sql_governed_async(
                    "SELECT missing FROM orders",
                    [{"code": "UNKNOWN_COLUMN"}],
                    "语义上下文",
                    question=DB_PRIVATE_PAYLOAD,
                )
            stage = "sql_repair_governed_async"
        else:
            result = await chain.fix_sql_async(
                "SELECT missing FROM orders", "字段不存在", {"tables": []}
            )
            assert result["error"] == "SQL 修复服务调用失败"
            stage = "sql_repair_async"

    _assert_safe_failure_log(caplog.text, stage)
    if governed:
        assert DB_PRIVATE_PAYLOAD not in caplog.text
        assert "13800138000" not in caplog.text
        assert "question_data" not in caplog.text


def test_safe_file_formatter_drops_exception_and_bearer_content(tmp_path: Path):
    from core.utils.log_sanitizer import safe_log_format

    path = tmp_path / "app.log"
    sink_id = logger.add(path, format=safe_log_format)
    try:
        try:
            raise AuthenticationError(f"Authorization: Bearer {SECRET}")
        except AuthenticationError as exc:
            logger.opt(exception=exc).error(
                "request failed Authorization: Bearer {}", SECRET
            )
    finally:
        logger.remove(sink_id)

    rendered = path.read_text(encoding="utf-8")
    assert SECRET not in rendered
    assert "Authorization" not in rendered
    assert "Bearer" not in rendered
    assert "Traceback" not in rendered


def test_safe_streamlit_sink_never_receives_bearer_content():
    from core.utils.log_sanitizer import make_safe_streamlit_sink

    rendered: list[str] = []
    sink = make_safe_streamlit_sink(rendered.append)
    sink(f"request failed Authorization: Bearer {SECRET}")

    assert len(rendered) == 1
    assert SECRET not in rendered[0]
    assert "Authorization" not in rendered[0]
    assert "Bearer" not in rendered[0]


def _assert_db_failure_is_metadata_only(text: str, stage: str) -> None:
    assert DB_PRIVATE_PAYLOAD not in text
    for raw_fragment in (
        "查询手机号",
        "13800138000",
        "SELECT password",
        "private_users",
        "Authorization",
        "mysql-secret",
        "database-secret",
        "Traceback",
    ):
        assert raw_fragment not in text
    assert f"stage={stage}" in text
    assert "exception_type=AuthenticationError" in text


@pytest.mark.parametrize(
    ("operation", "expected", "stage"),
    [
        ("query", [], "sqlite_query"),
        ("update", 0, "sqlite_update"),
        ("history_save", None, "sqlite_history_save"),
        ("governed_history_save", None, "sqlite_governed_history_save"),
    ],
)
def test_sqlite_public_failure_paths_never_log_exception_sql_or_params(
    caplog, operation: str, expected, stage: str
):
    """Break caught: database exceptions or statements reaching any public log sink."""
    from core.history.sqlite_client import SQLiteClient

    verifier = Mock()
    verifier.consume.return_value = True
    client = SQLiteClient(":memory:", governance_proof_verifier=verifier)

    @contextmanager
    def failing_connection():
        raise AuthenticationError(DB_PRIVATE_PAYLOAD)
        yield  # pragma: no cover

    client.get_connection = failing_connection
    command = SimpleNamespace(
        session_id="session-a",
        user_query=DB_PRIVATE_PAYLOAD,
        generated_sql="SELECT password FROM private_users",
        matched_knowledge_json=None,
        retrieval_query=DB_PRIVATE_PAYLOAD,
        validation_status="success",
        validation_error=None,
        semantic_datasource="sales",
        semantic_dialect="mysql",
        semantic_version="1.0.0",
        semantic_content_sha256="1" * 64,
    )

    with capture_loguru(caplog):
        if operation == "query":
            result = client.execute_query(
                "SELECT password FROM private_users WHERE mobile=:mobile",
                {"mobile": "13800138000"},
            )
        elif operation == "update":
            result = client.execute_update(
                "UPDATE private_users SET password=:password",
                {"password": "database-secret"},
            )
        elif operation == "history_save":
            result = client.save_sql_history(
                DB_PRIVATE_PAYLOAD,
                "SELECT password FROM private_users",
            )
        else:
            result = client.save_governed_sql_history(command, object())

    assert result == expected
    _assert_db_failure_is_metadata_only(caplog.text, stage)


def test_sqlite_guarded_finalize_masks_failure_and_preserves_false_result(caplog):
    """Break caught: guarded finalization propagating or logging sensitive failures."""
    from core.history.sqlite_client import SQLiteClient

    verifier = Mock()
    verifier.consume.return_value = True
    client = SQLiteClient(":memory:", governance_proof_verifier=verifier)
    client.execute_update = Mock(side_effect=AuthenticationError(DB_PRIVATE_PAYLOAD))
    command = SimpleNamespace(
        history_id=7,
        session_id="session-a",
        user_query=DB_PRIVATE_PAYLOAD,
        generated_sql="SELECT password FROM private_users",
        execution_status="fail",
        execution_error=DB_PRIVATE_PAYLOAD,
        execution_result_json=None,
        semantic_datasource="sales",
        semantic_dialect="mysql",
        semantic_version="1.0.0",
        semantic_content_sha256="1" * 64,
    )

    with capture_loguru(caplog):
        result = client.finalize_governed_sql_execution(command, object())

    assert result is False
    _assert_db_failure_is_metadata_only(
        caplog.text, "sqlite_governed_history_finalize"
    )


def test_sqlite_migration_logs_only_safe_metadata_before_reraising(caplog):
    """Break caught: migration DDL or driver text leaking on a non-duplicate error."""
    from core.history.sqlite_client import SQLiteClient

    client = SQLiteClient(":memory:")
    client.execute_update = Mock(side_effect=AuthenticationError(DB_PRIVATE_PAYLOAD))

    with capture_loguru(caplog), pytest.raises(AuthenticationError):
        client._apply_history_schema_change(
            "ALTER TABLE private_users ADD COLUMN password VARCHAR(255)"
        )

    _assert_db_failure_is_metadata_only(
        caplog.text, "sqlite_history_schema_migration"
    )


def test_sqlite_connect_cleanup_failure_keeps_the_false_public_result(
    caplog, monkeypatch
):
    """Break caught: engine cleanup masking the stable connection failure contract."""
    from sqlalchemy import create_engine

    import core.history.sqlite_client as sqlite_module

    # event.listen 要求真实 Engine 目标：用真实内存引擎，仅 mock connect/dispose
    # 注入「连接失败 + 清理失败」双重故障。
    engine = create_engine("sqlite://")
    engine.connect = Mock(side_effect=AuthenticationError(DB_PRIVATE_PAYLOAD))
    engine.dispose = Mock(side_effect=AuthenticationError(DB_PRIVATE_PAYLOAD))
    monkeypatch.setattr(sqlite_module, "create_engine", Mock(return_value=engine))
    client = sqlite_module.SQLiteClient(":memory:")

    with capture_loguru(caplog):
        result = client.connect()

    assert result is False
    assert client.engine is None
    _assert_db_failure_is_metadata_only(caplog.text, "sqlite_connect")
    assert "stage=sqlite_connect_cleanup" in caplog.text


def test_sqlite_nonexception_logs_do_not_echo_config_or_table_identifiers(
    caplog, tmp_path
):
    """Break caught: success/fallback logs bypassing the safe exception boundary."""
    from core.history.sqlite_client import SQLiteClient

    # 秘密载荷进入库文件名：初始化成功日志只允许输出路径指纹；
    # 不存在的表名同样只允许输出指纹（真实临时文件库，无需 mock 引擎）。
    client = SQLiteClient(str(tmp_path / f"{DB_PRIVATE_PAYLOAD}.db"))

    with capture_loguru(caplog):
        assert client.connect() is True
        assert client.upsert_column_schema(DB_PRIVATE_PAYLOAD, "id") is False
    client.close()

    for raw_fragment in (
        "查询手机号",
        "13800138000",
        "SELECT password",
        "private_users",
        "Authorization",
        "mysql-secret",
        "database-secret",
    ):
        assert raw_fragment not in caplog.text
