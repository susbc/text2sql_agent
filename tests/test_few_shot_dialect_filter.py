"""Task 5（spec §5.4）：few-shot 方言过滤。

legacy MySQL 历史（sql_dialect='mysql'）不得注入 SQLite 生成提示；新历史默认
sql_dialect='sqlite'；治理 few-shot 路径（governance_validated + semantic_* 身份）
行为不变；dialect=None 保持旧行为（向后兼容）。

fixture 策略沿用 tests/test_sqlite_client.py：真实种子初始化的临时文件库。
fresh 基线历史 50 行（max id 79）中含 6 条双 success 的 mysql 方言旧行——正是
spec §5.4 要排除的污染源；功能断言全部相对该基线计算（同 test_sqlite_client 策略）。
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.history.proof import (
    GovernedHistoryFinalization,
    GovernedHistorySave,
    create_history_proof_pair,
)
from core.history.sqlite_client import SQLiteClient

_SHA = "a" * 64


@pytest.fixture()
def client(tmp_path):
    instance = SQLiteClient(str(tmp_path / "few_shot_dialect.db"))
    assert instance.connect() is True
    try:
        yield instance
    finally:
        instance.close()


def _insert_history_row(
    client,
    *,
    dialect,
    user_query,
    generated_sql="SELECT 1",
    validation_status="success",
    execution_status="success",
):
    """直插一条指定方言的历史行（模拟迁移旧行/新行），返回其 id。"""
    client.execute_update(
        """
        INSERT INTO sql_generation_history
        (session_id, user_query, generated_sql, sql_dialect,
         validation_status, execution_status)
        VALUES (:session_id, :user_query, :generated_sql, :sql_dialect,
                :validation_status, :execution_status)
        """,
        {
            "session_id": f"session-{user_query}",
            "user_query": user_query,
            "generated_sql": generated_sql,
            "sql_dialect": dialect,
            "validation_status": validation_status,
            "execution_status": execution_status,
        },
        raise_on_error=True,
    )
    rows = client.execute_query(
        "SELECT id FROM sql_generation_history WHERE user_query = :user_query",
        {"user_query": user_query},
    )
    return rows[0]["id"]


def _dual_success_ids_by_dialect(client):
    """基线：当前库中满足 few-shot 双 success 条件的行 id（按方言分组）。"""
    rows = client.execute_query(
        "SELECT id, sql_dialect FROM sql_generation_history "
        "WHERE validation_status = 'success' AND execution_status = 'success'"
    )
    by_dialect = {}
    for row in rows:
        by_dialect.setdefault(row["sql_dialect"], set()).add(row["id"])
    return by_dialect


# ==================== legacy 路径方言过滤 ====================

def test_mysql_history_excluded_from_sqlite_few_shot(client):
    baseline = _dual_success_ids_by_dialect(client)
    baseline_mysql = baseline.get("mysql", set())
    baseline_sqlite = baseline.get("sqlite", set())
    # 种子确含双 success 的 mysql 旧行（真实污染源），过滤必须将其排除
    assert baseline_mysql

    mysql_id = _insert_history_row(
        client,
        dialect="mysql",
        user_query="legacy mysql 问题",
        generated_sql="SELECT DATE_FORMAT(created_at, '%Y-%m') FROM orders",
    )
    sqlite_id = _insert_history_row(
        client,
        dialect="sqlite",
        user_query="sqlite 新问题",
        generated_sql="SELECT strftime('%Y-%m', created_at) FROM orders",
    )
    # 双 success 过滤仍生效：同方言的失败行不得进入 few-shot
    _insert_history_row(
        client,
        dialect="sqlite",
        user_query="sqlite 失败问题",
        validation_status="fail",
    )

    sqlite_rows = client.get_successful_history_for_few_shot(dialect="sqlite")
    assert {row["id"] for row in sqlite_rows} == baseline_sqlite | {sqlite_id}
    # 种子 mysql 旧行与新增 mysql 行均被排除
    assert not (baseline_mysql | {mysql_id}) & {row["id"] for row in sqlite_rows}

    mysql_rows = client.get_successful_history_for_few_shot(dialect="mysql")
    assert {row["id"] for row in mysql_rows} == baseline_mysql | {mysql_id}

    # dialect=None（含显式传入）保持旧行为：返回全部双 success 历史（向后兼容）
    expected_all = baseline_mysql | baseline_sqlite | {mysql_id, sqlite_id}
    all_rows = client.get_successful_history_for_few_shot()
    assert {row["id"] for row in all_rows} == expected_all
    explicit_none = client.get_successful_history_for_few_shot(dialect=None)
    assert {row["id"] for row in explicit_none} == expected_all


def test_new_history_defaults_sqlite(client):
    history_id = client.save_sql_history(
        "新问题", "SELECT 1", validation_status="success"
    )
    assert history_id is not None
    detail = client.get_history_detail(history_id)
    assert detail["sql_dialect"] == "sqlite"

    # 迁移旧行保持 mysql，且不被 sqlite few-shot 检索命中
    mysql_id = _insert_history_row(client, dialect="mysql", user_query="legacy 旧行")
    assert client.get_history_detail(mysql_id)["sql_dialect"] == "mysql"

    # 新行执行成功后进入 sqlite few-shot；mysql 旧行不进入
    assert client.update_sql_execution(history_id, "success") is True
    sqlite_ids = {
        row["id"] for row in client.get_successful_history_for_few_shot(dialect="sqlite")
    }
    assert history_id in sqlite_ids
    assert mysql_id not in sqlite_ids
    mysql_ids = {
        row["id"] for row in client.get_successful_history_for_few_shot(dialect="mysql")
    }
    assert history_id not in mysql_ids
    assert mysql_id in mysql_ids


def test_dialect_filter_adds_sql_dialect_predicate():
    """过滤落在客户端查询（WHERE sql_dialect=:dialect），参数化绑定。"""
    instance = SQLiteClient(":memory:")
    instance.execute_query = Mock(return_value=[])

    instance.get_successful_history_for_few_shot(limit=12, dialect="sqlite")

    query, params = instance.execute_query.call_args.args
    normalized_query = " ".join(query.split()).lower()
    assert "validation_status = 'success'" in normalized_query
    assert "execution_status = 'success'" in normalized_query
    assert "sql_dialect = :dialect" in normalized_query
    assert params == {"limit": 12, "dialect": "sqlite"}


def test_no_dialect_keeps_legacy_query_shape():
    """dialect=None 不引入 sql_dialect 谓词/参数（既有查询形状不变）。"""
    instance = SQLiteClient(":memory:")
    instance.execute_query = Mock(return_value=[])

    instance.get_successful_history_for_few_shot(limit=12)

    query, params = instance.execute_query.call_args.args
    normalized_query = " ".join(query.split()).lower()
    assert "sql_dialect" not in normalized_query
    assert params == {"limit": 12}


# ==================== 治理路径不受影响 ====================

def test_governed_few_shot_unaffected(tmp_path):
    issuer, verifier = create_history_proof_pair()
    instance = SQLiteClient(
        str(tmp_path / "governed_few_shot.db"), governance_proof_verifier=verifier
    )
    assert instance.connect() is True
    try:
        command = GovernedHistorySave(
            session_id="gov-session",
            user_query="治理问题",
            generated_sql="SELECT SUM(trans_amount) FROM transaction_record",
            matched_knowledge_json=None,
            retrieval_query="治理问题",
            validation_status="success",
            validation_error=None,
            semantic_datasource="sales",
            semantic_dialect="mysql",
            semantic_version="1.0.0",
            semantic_content_sha256=_SHA,
        )
        history_id = instance.save_governed_sql_history(command, issuer.issue(command))
        assert history_id is not None
        finalize = GovernedHistoryFinalization(
            history_id=history_id,
            session_id=command.session_id,
            user_query=command.user_query,
            generated_sql=command.generated_sql,
            execution_status="success",
            execution_error=None,
            execution_result_json='{"row_count": 1}',
            semantic_datasource="sales",
            semantic_dialect="mysql",
            semantic_version="1.0.0",
            semantic_content_sha256=_SHA,
        )
        assert instance.finalize_governed_sql_execution(
            finalize, issuer.issue(finalize)
        ) is True

        # legacy 双 success 行（两种方言）不得混入治理检索
        legacy_mysql = _insert_history_row(instance, dialect="mysql", user_query="legacy mysql")
        legacy_sqlite = _insert_history_row(instance, dialect="sqlite", user_query="legacy sqlite")

        rows = instance.get_successful_history_for_few_shot(
            limit=100,
            semantic_datasource="sales",
            semantic_dialect="mysql",
            semantic_version="1.0.0",
            semantic_content_sha256=_SHA,
            governance_validated=True,
        )
        assert [row["id"] for row in rows] == [history_id]
        assert legacy_mysql not in {row["id"] for row in rows}
        assert legacy_sqlite not in {row["id"] for row in rows}

        # 身份不匹配仍为空；未验证的治理检索仍拒绝（fail-closed 不变）
        assert instance.get_successful_history_for_few_shot(
            semantic_datasource="finance",
            semantic_dialect="mysql",
            semantic_version="1.0.0",
            semantic_content_sha256=_SHA,
            governance_validated=True,
        ) == []
        with pytest.raises(ValueError):
            instance.get_successful_history_for_few_shot(governance_validated=False)
    finally:
        instance.close()


# ==================== 调用方传入当前方言 ====================

@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_load_few_shot_history_passes_configured_dialect(dialect):
    from core.app_context import ApplicationContext

    context = ApplicationContext({"few_shot_enabled": True, "sql_dialect": dialect})
    context._db_client = Mock(engine=object())
    context._db_client.get_successful_history_for_few_shot.return_value = []
    context._knowledge_retriever = Mock()
    context._correctness_pipeline = None

    context._load_few_shot_history()

    context._db_client.get_successful_history_for_few_shot.assert_called_once_with(
        limit=100, dialect=dialect
    )
    context._knowledge_retriever.build_few_shot_index.assert_called_once_with([])


@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_populate_retriever_legacy_passes_candidate_dialect(dialect):
    from core.app_context import ApplicationContext

    context = ApplicationContext({"few_shot_enabled": True})
    context._db_client = Mock(engine=object())
    context._db_client.get_table_schema.return_value = []
    context._db_client.get_successful_history_for_few_shot.return_value = []
    context._correctness_pipeline = None
    retriever = Mock()

    context._populate_retriever(
        retriever,
        {"few_shot_enabled": True, "sql_dialect": dialect},
        correctness_pipeline=None,
    )

    context._db_client.get_successful_history_for_few_shot.assert_called_once_with(
        limit=100, dialect=dialect
    )
    retriever.build_few_shot_index.assert_called_once_with([])
