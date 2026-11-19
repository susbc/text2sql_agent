"""SQLite 执行/方言/安全边界 reconciliation 测试（Task 4，spec §5.3）。

覆盖：
- 6 应用表全部禁查（validate_query_scope 内建黑名单，allow-all/显式放行均兜底）；
- 业务表放行，main. schema 限定正确处理（SQLite 默认 schema＝main）；
- constrain_read_query sqlite 分支不注 MAX_EXECUTION_TIME（超时由客户端看门狗），
  LIMIT 注入产物可在真实 SQLite 库执行；
- 方言 fallback 一致 sqlite（generator/sql_chain/dialect_detector），治理闸门仍 mysql-only；
- 端到端：临时 SQLite 业务库（真实种子）→ execute_sql 返回真实行。

注意：worktree .env 设 SQL_DIALECT=mysql（用户配置，不动）；本文件所有用例
显式传 dialect='sqlite'，不依赖环境默认。
"""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.history.sqlite_client import SQLiteClient
from core.sql.validator import (
    constrain_read_query,
    is_safe_read_query,
    validate_query_scope,
)

_APP_TABLES = [
    "knowledge_metadata", "table_schema", "column_schema",
    "sql_generation_history", "retrieval_terms", "user_feedback",
]
_BUSINESS_TABLES = {
    "users", "transaction_record", "user_account", "risk_blacklist",
    "prediction_results", "account_freeze_log", "daily_account_check",
    "fee_rate_config",
}


@pytest.fixture()
def client(tmp_path):
    instance = SQLiteClient(str(tmp_path / "text2sql_exec_test.db"))
    assert instance.connect() is True
    try:
        yield instance
    finally:
        instance.close()


def _make_generator(db_client, dialect="sqlite", config=None):
    """真实 SQLGenerationChain（显式方言）+ Mock LLM/检索器：只测执行+安全，不测生成。"""
    from core.chain.sql_chain import SQLGenerationChain
    from core.sql.generator import SQLGenerator

    retriever = Mock()
    retriever.history_index = None
    chain = SQLGenerationChain(llm=Mock(), dialect=dialect)
    merged = {"sql_dialect": dialect}
    if config:
        merged.update(config)
    return SQLGenerator(
        llm=Mock(),
        knowledge_retriever=retriever,
        sql_chain=chain,
        db_client=db_client,
        config=merged,
    )


# ==================== 应用表禁查（安全边界） ====================

@pytest.mark.parametrize("table", _APP_TABLES)
@pytest.mark.parametrize("qualifier", ["", "main."])
def test_app_tables_blocked(table, qualifier):
    sql = f"SELECT * FROM {qualifier}{table}"
    # 只读形态本身合法；表级拒绝由 validate_query_scope 内建黑名单负责。
    assert is_safe_read_query(sql, dialect="sqlite") is True
    scope = validate_query_scope(sql, dialect="sqlite")
    assert scope["valid"] is False
    assert any("禁止访问内部表" in error for error in scope["errors"])


@pytest.mark.parametrize("table", _APP_TABLES)
def test_app_tables_blocked_even_if_allowlist_bypassed(table):
    """defense-in-depth：即便 allowed_tables 显式放行应用表，内建黑名单仍拒绝。"""
    scope = validate_query_scope(
        f"SELECT * FROM {table}",
        allowed_tables=[table],
        allowed_schemas=["main"],
        dialect="sqlite",
    )
    assert scope["valid"] is False
    assert any("禁止访问内部表" in error for error in scope["errors"])


def test_app_table_block_is_case_insensitive():
    for sql in (
        "SELECT * FROM SQL_GENERATION_HISTORY",
        "SELECT * FROM Knowledge_Metadata",
        "SELECT * FROM main.RETRIEVAL_TERMS",
    ):
        scope = validate_query_scope(sql, dialect="sqlite")
        assert scope["valid"] is False, sql


# ==================== 业务表放行 / main schema ====================

def test_business_tables_allowed():
    assert validate_query_scope(
        "SELECT * FROM users",
        allowed_tables=["users"],
        allowed_schemas=["main"],
        dialect="sqlite",
    )["valid"]
    assert validate_query_scope(
        "SELECT * FROM main.users",
        allowed_tables=["users"],
        allowed_schemas=["main"],
        dialect="sqlite",
    )["valid"]
    # 无 schema 前缀不受 allowed_schemas 约束（SQLite 默认即 main）。
    assert validate_query_scope(
        "SELECT id FROM users WHERE id = 1",
        allowed_tables=["users"],
        allowed_schemas=["main"],
        dialect="sqlite",
    )["valid"]
    # legacy 无限制 API 下业务表同样放行。
    assert validate_query_scope("SELECT * FROM users", dialect="sqlite")["valid"]


def test_safety_fallback_allowed_tables_are_business_only(client):
    generator = _make_generator(client)
    assert {row["table_name"] for row in client.get_table_schema()} == _BUSINESS_TABLES
    # allowed_tables/allowed_schemas 均 None → 业务表白名单 + main schema fallback。
    assert generator._get_query_safety_error("SELECT * FROM users", None, None) is None
    assert generator._get_query_safety_error(
        "SELECT * FROM main.users", None, None
    ) is None
    error = generator._get_query_safety_error("SELECT * FROM no_such_table", None, None)
    assert error and "表不在允许范围内" in error


# ==================== constrain_read_query sqlite 分支 ====================

def test_constrain_read_query_sqlite_omits_timeout_hint(client):
    constrained = constrain_read_query(
        "SELECT * FROM risk_blacklist", max_rows=2, timeout_ms=10000, dialect="sqlite"
    )
    assert "MAX_EXECUTION_TIME" not in constrained
    assert "LIMIT 3" in constrained
    rows, truncated = client.execute_query_limited(constrained, max_rows=2)
    assert len(rows) == 2
    assert truncated is True


def test_constrain_read_query_sqlite_preserves_stricter_limit(client):
    constrained = constrain_read_query(
        "SELECT * FROM risk_blacklist LIMIT 1",
        max_rows=500, timeout_ms=10000, dialect="sqlite",
    )
    assert "LIMIT 1" in constrained
    rows, truncated = client.execute_query_limited(constrained, max_rows=500)
    assert len(rows) == 1
    assert truncated is False


def test_constrain_read_query_mysql_keeps_timeout_hint():
    constrained = constrain_read_query(
        "SELECT * FROM users", max_rows=10, timeout_ms=5000, dialect="mysql"
    )
    assert "MAX_EXECUTION_TIME(5000)" in constrained


# ==================== 方言 fallback 一致 sqlite ====================

def test_dialect_fallbacks_are_sqlite():
    from core.chain.sql_chain import SQLGenerationChain
    from core.sql.dialect_detector import SQLDialectDetector

    assert SQLGenerationChain(llm=Mock()).dialect == "sqlite"
    assert SQLDialectDetector(None).detect_from_query("查询黑名单") == ("sqlite", None)

    generator = _make_generator(None, config={"sql_dialect": None})
    generator.config = {}
    assert generator.detect_dialect("查询黑名单") == ("sqlite", None)
    assert generator._detect_dialect_and_db("查询黑名单", None, None) == ("sqlite", None)


def test_governance_gate_still_mysql_only():
    from core.config_validation import RuntimeConfigurationError

    generator = _make_generator(None)
    generator.correctness_pipeline = Mock()
    assert generator._validate_governed_dialect("mysql") == "mysql"
    with pytest.raises(RuntimeConfigurationError):
        generator._validate_governed_dialect("sqlite")


# ==================== 端到端执行 ====================

def test_execute_sql_on_sqlite_end_to_end(client):
    generator = _make_generator(client)
    result = generator.execute_sql(
        "SELECT id, target_id, risk_level FROM risk_blacklist ORDER BY id"
    )
    assert result["status"] == "success"
    assert result["error"] is None
    assert result["row_count"] == 3
    assert result["truncated"] is False
    assert [row["target_id"] for row in result["data"]] == [
        "U10004", "6222020000001002", "203.0.113.66",
    ]
    assert [row["risk_level"] for row in result["data"]] == [3, 2, 1]


def test_execute_sql_schema_qualified_main(client):
    generator = _make_generator(client)
    result = generator.execute_sql("SELECT COUNT(*) AS n FROM main.risk_blacklist")
    assert result["status"] == "success"
    assert result["data"][0]["n"] == 3


def test_execute_sql_constrained_sql_is_valid_sqlite(client, monkeypatch):
    captured = {}
    original = client.execute_query_limited

    def spy(query, max_rows, **kwargs):
        captured["sql"] = query
        return original(query, max_rows=max_rows, **kwargs)

    monkeypatch.setattr(client, "execute_query_limited", spy)
    generator = _make_generator(client)
    result = generator.execute_sql("SELECT * FROM risk_blacklist")
    assert result["status"] == "success"
    assert "MAX_EXECUTION_TIME" not in captured["sql"]
    assert "LIMIT" in captured["sql"]


@pytest.mark.parametrize("table", _APP_TABLES)
def test_execute_sql_rejects_app_tables(client, table):
    generator = _make_generator(client)
    result = generator.execute_sql(f"SELECT * FROM {table}")
    assert result["status"] == "error"
    assert "禁止访问内部表" in result["error"]
    assert result["data"] is None


def test_execute_sql_app_table_blocked_even_with_explicit_allowlist(client):
    generator = _make_generator(client)
    result = generator.execute_sql(
        "SELECT * FROM knowledge_metadata",
        allowed_tables=["knowledge_metadata"],
        allowed_schemas=["main"],
    )
    assert result["status"] == "error"
    assert "禁止访问内部表" in result["error"]
    assert result["data"] is None
