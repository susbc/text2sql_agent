"""SQLiteClient 单测：接口 parity、SQL 翻译、初始化/种子门控、超时看门狗、治理往返。

fixture 策略（文档化）：使用真实种子（data/seed_business.sql + data/seed_history.sql）
初始化的临时文件库。fresh 库基线＝历史 50 行（max id 79）+ 业务 30 行（8 表）。
功能断言全部相对该基线计算，不依赖系统时钟与种子行的排序假设。
"""
from __future__ import annotations

import inspect
import sqlite3

import pytest

import config
from core.config_validation import RuntimeConfigurationError
from core.history.mysql_client import MySQLClient
from core.history.proof import (
    GovernedHistoryFinalization,
    GovernedHistorySave,
    create_history_proof_pair,
)
from core.history.sqlite_client import QueryTimeoutExceeded, SQLiteClient

_SEED_HISTORY_ROWS = 50
_SEED_MAX_HISTORY_ID = 79
_APP_TABLES = {
    "knowledge_metadata", "table_schema", "column_schema",
    "sql_generation_history", "retrieval_terms", "user_feedback",
}
_BUSINESS_TABLES = {
    "users", "transaction_record", "user_account", "risk_blacklist",
    "prediction_results", "account_freeze_log", "daily_account_check",
    "fee_rate_config",
}
_SLOW_CTE = (
    "WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM cnt "
    "WHERE x < 100000000) SELECT COUNT(*) AS n FROM cnt"
)
_SHA = "a" * 64


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "text2sql_test.db")


@pytest.fixture()
def client(db_path):
    instance = SQLiteClient(db_path)
    assert instance.connect() is True
    try:
        yield instance
    finally:
        instance.close()


def _count(client, table):
    return client.execute_query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]


def _table_names(client):
    rows = client.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row["name"] for row in rows}


def _governed_save_command(session_id="gov-session"):
    return GovernedHistorySave(
        session_id=session_id,
        user_query="订单金额",
        generated_sql="SELECT SUM(trans_amount) FROM transaction_record",
        matched_knowledge_json=None,
        retrieval_query="订单金额",
        validation_status="success",
        validation_error=None,
        semantic_datasource="sales",
        semantic_dialect="mysql",
        semantic_version="1.0.0",
        semantic_content_sha256=_SHA,
    )


# ==================== 接口 parity ====================

def test_public_method_signatures_match_mysql_client():
    """每个 MySQLClient 公开方法在 SQLiteClient 上同名同签名（允许附加带默认值的 kw-only）。"""
    for name, member in vars(MySQLClient).items():
        if name.startswith("_") or not inspect.isfunction(member):
            continue
        assert hasattr(SQLiteClient, name), f"缺少公开方法：{name}"
        mysql_sig = inspect.signature(member)
        sqlite_sig = inspect.signature(getattr(SQLiteClient, name))
        mysql_params = list(mysql_sig.parameters.values())[1:]  # 去 self
        sqlite_params = list(sqlite_sig.parameters.values())[1:]
        sqlite_by_name = {p.name: p for p in sqlite_params}
        for param in mysql_params:
            assert param.name in sqlite_by_name, f"{name} 缺少参数 {param.name}"
            other = sqlite_by_name[param.name]
            assert other.kind is param.kind, f"{name}.{param.name} 参数类别不一致"
            assert other.default == param.default, f"{name}.{param.name} 默认值不一致"
        extra = [p for p in sqlite_params if p.name not in {q.name for q in mysql_params}]
        for param in extra:
            assert param.kind is inspect.Parameter.KEYWORD_ONLY, f"{name} 附加参数须 kw-only"
            assert param.default is not inspect.Parameter.empty, f"{name} 附加参数须有默认值"
    assert SQLiteClient.explain_query_enforces_wall_clock_deadline is True


def test_database_attribute_is_main(client):
    assert client.database == "main"


def test_history_max_records_validation(db_path):
    with pytest.raises(RuntimeConfigurationError):
        SQLiteClient(db_path, history_max_records=0)


# ==================== connect / 初始化 / 种子门控 ====================

def test_connect_fresh_db_creates_app_tables_and_loads_seeds(client):
    names = _table_names(client)
    assert _APP_TABLES <= names
    assert _BUSINESS_TABLES <= names
    assert _count(client, "sql_generation_history") == _SEED_HISTORY_ROWS
    assert _count(client, "users") == 12
    assert _count(client, "risk_blacklist") == 3
    assert sum(_count(client, t) for t in _BUSINESS_TABLES) == 30
    indexes = {
        row["name"]
        for row in client.execute_query("PRAGMA index_list(sql_generation_history)")
    }
    assert "sql_generation_history_idx_governed_few_shot" in indexes


def test_connect_is_idempotent_on_populated_db(db_path):
    first = SQLiteClient(db_path)
    assert first.connect() is True
    first.save_sql_history("往返", "SELECT 1", session_id="idem")
    first.close()

    second = SQLiteClient(db_path)
    assert second.connect() is True
    try:
        assert _count(second, "sql_generation_history") == _SEED_HISTORY_ROWS + 1
        assert sum(_count(second, t) for t in _BUSINESS_TABLES) == 30
        # 同一实例重复 connect 亦幂等
        assert second.connect() is True
        assert _count(second, "sql_generation_history") == _SEED_HISTORY_ROWS + 1
    finally:
        second.close()


def test_connect_existing_db_never_replays_seeds(db_path):
    # 预置一个仅含业务表 users（1 行）的旧库：种子不得重放
    raw = sqlite3.connect(db_path)
    raw.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, note TEXT)")
    raw.execute("INSERT INTO users (user_id, note) VALUES (1, 'legacy')")
    raw.commit()
    raw.close()

    instance = SQLiteClient(db_path)
    assert instance.connect() is True
    try:
        assert _count(instance, "users") == 1  # 未被种子覆盖/追加
        assert _count(instance, "sql_generation_history") == 0  # 历史种子未重放
        assert _APP_TABLES <= _table_names(instance)  # 应用表仍幂等补齐
        assert not (_BUSINESS_TABLES - {"users"}) & _table_names(instance)
    finally:
        instance.close()


def test_connect_migrates_legacy_schema(db_path):
    raw = sqlite3.connect(db_path)
    # 治理列出现之前的旧表：完整基础列（含旧默认 sql_dialect='mysql'）缺 5 治理列
    raw.execute(
        """
        CREATE TABLE sql_generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_query TEXT NOT NULL,
            generated_sql TEXT,
            sql_dialect TEXT DEFAULT 'mysql',
            validation_status TEXT DEFAULT 'pending',
            validation_error TEXT,
            execution_status TEXT DEFAULT 'pending',
            execution_error TEXT,
            execution_result TEXT,
            matched_knowledge TEXT,
            retrieval_query TEXT,
            feedback_score INTEGER,
            feedback_comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    raw.execute(
        """
        CREATE TABLE table_schema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            table_comment TEXT,
            database_name TEXT DEFAULT 'text2sql_db',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uk_table_name UNIQUE (table_name, database_name)
        )
        """
    )
    raw.commit()
    raw.close()

    instance = SQLiteClient(db_path)
    assert instance.connect() is True
    try:
        history_columns = {
            row["name"]
            for row in instance.execute_query("PRAGMA table_info(sql_generation_history)")
        }
        assert {
            "semantic_datasource", "semantic_dialect", "semantic_version",
            "semantic_content_sha256", "governance_validated",
        } <= history_columns
        table_columns = {
            row["name"]
            for row in instance.execute_query("PRAGMA table_info(table_schema)")
        }
        assert "properties" in table_columns
        indexes = {
            row["name"]
            for row in instance.execute_query("PRAGMA index_list(sql_generation_history)")
        }
        assert "sql_generation_history_idx_governed_few_shot" in indexes
        # 迁移后治理/普通写入均可用
        assert instance.save_sql_history("迁移后", "SELECT 1") is not None
        assert instance.upsert_table_schema("users", "用户表", {"k": 1}) is True
    finally:
        instance.close()


def test_get_connection_requires_connect(db_path):
    instance = SQLiteClient(db_path)
    with pytest.raises(RuntimeError):
        with instance.get_connection():
            pass


def test_close_disposes_engine(client):
    client.close()
    assert client.engine is None
    assert client.execute_query("SELECT 1") == []


# ==================== execute_query / execute_update ====================

def test_execute_query_named_params(client):
    rows = client.execute_query(
        "SELECT id, target_id FROM risk_blacklist WHERE risk_level = :lvl ORDER BY id",
        {"lvl": 3},
    )
    assert rows == [{"id": 1, "target_id": "U10004"}]
    assert client.execute_query("SELECT 1 AS one") == [{"one": 1}]


def test_execute_query_error_contract(client):
    assert client.execute_query("SELECT * FROM no_such_table") == []
    with pytest.raises(Exception):
        client.execute_query("SELECT * FROM no_such_table", raise_on_error=True)


def test_execute_update_named_params(client):
    affected = client.execute_update(
        "UPDATE risk_blacklist SET block_scene = :scene WHERE id = :id",
        {"scene": "全部交易", "id": 1},
    )
    assert affected == 1
    rows = client.execute_query("SELECT block_scene FROM risk_blacklist WHERE id = 1")
    assert rows[0]["block_scene"] == "全部交易"
    assert client.execute_update("UPDATE no_such_table SET x = 1") == 0
    with pytest.raises(Exception):
        client.execute_update("UPDATE no_such_table SET x = 1", raise_on_error=True)


# ==================== execute_query_limited + 看门狗 ====================

def test_execute_query_limited_truncation(client):
    rows, truncated = client.execute_query_limited(
        "SELECT id FROM sql_generation_history ORDER BY id", max_rows=10
    )
    assert len(rows) == 10
    assert truncated is True
    rows, truncated = client.execute_query_limited(
        "SELECT id FROM sql_generation_history ORDER BY id", max_rows=_SEED_HISTORY_ROWS
    )
    assert len(rows) == _SEED_HISTORY_ROWS
    assert truncated is False
    rows, truncated = client.execute_query_limited(
        "SELECT id FROM risk_blacklist WHERE risk_level = :lvl",
        max_rows=100,
        params={"lvl": 3},
    )
    assert rows == [{"id": 1}]
    assert truncated is False
    with pytest.raises(ValueError):
        client.execute_query_limited("SELECT 1", max_rows=0)


def test_execute_query_limited_watchdog_cancels_slow_query(client):
    with pytest.raises(TimeoutError):
        client.execute_query_limited(_SLOW_CTE, max_rows=1, timeout_ms=50)
    # 看门狗取消后连接池仍健康
    assert client.execute_query("SELECT 1 AS ok") == [{"ok": 1}]
    rows, truncated = client.execute_query_limited(
        "SELECT id FROM risk_blacklist ORDER BY id", max_rows=2, timeout_ms=5000
    )
    assert len(rows) == 2
    assert truncated is True


def test_execute_query_limited_default_timeout_reads_config(client, monkeypatch):
    monkeypatch.setattr(config, "SQL_QUERY_TIMEOUT_MS", 50)
    with pytest.raises(QueryTimeoutExceeded):
        client.execute_query_limited(_SLOW_CTE, max_rows=1)


def test_execute_query_limited_rejects_invalid_timeout(client):
    with pytest.raises(ValueError):
        client.execute_query_limited("SELECT 1", max_rows=1, timeout_ms=0)


# ==================== upsert（ON CONFLICT 翻译） ====================

def test_upsert_table_schema_on_conflict_updates(client):
    assert client.upsert_table_schema("users", "用户表", {"source": "seed"}) is True
    assert client.upsert_table_schema("users", "用户表 v2", {"source": "sync"}) is True
    rows = client.execute_query(
        "SELECT table_name, table_comment, properties, updated_at "
        "FROM table_schema WHERE table_name = 'users'"
    )
    assert len(rows) == 1
    assert rows[0]["table_comment"] == "用户表 v2"
    assert rows[0]["properties"] == '{"source": "sync"}'
    assert rows[0]["updated_at"] is not None


def test_upsert_column_schema_requires_table_and_matches_mysql_semantics(client):
    assert client.upsert_column_schema("missing_table", "id") is False
    assert client.upsert_table_schema("users", "用户表") is True
    assert client.upsert_column_schema(
        "users", "user_id", "INTEGER", "用户 ID", is_nullable=False, is_primary_key=True
    ) is True
    # canonical column_schema 除 PK 外无唯一键（与 MySQL 活体库一致）：
    # MySQL ON DUPLICATE KEY 永不触发 → 忠实 port 亦为重复插入。
    assert client.upsert_column_schema("users", "user_id", "INTEGER") is True
    rows = client.execute_query(
        "SELECT column_name, column_type, is_nullable, is_primary_key "
        "FROM column_schema ORDER BY id"
    )
    assert len(rows) == 2
    assert rows[0]["is_primary_key"] == 1
    assert rows[0]["is_nullable"] == 0


# ==================== 历史读写往返 ====================

def test_save_sql_history_roundtrip(client):
    history_id = client.save_sql_history(
        "查询黑名单用户",
        "SELECT * FROM risk_blacklist",
        session_id="s-roundtrip",
        matched_knowledge=[{"name": "risk_blacklist", "node_type": "table"}],
        retrieval_query="黑名单",
        validation_status="success",
    )
    assert isinstance(history_id, int)
    assert history_id > _SEED_MAX_HISTORY_ID  # AUTOINCREMENT 续接种子最大 id

    detail = client.get_history_detail(history_id)
    assert detail["user_query"] == "查询黑名单用户"
    assert detail["generated_sql"] == "SELECT * FROM risk_blacklist"
    assert detail["session_id"] == "s-roundtrip"
    assert detail["sql_dialect"] == "sqlite"  # DDL 默认 'sqlite'
    assert detail["validation_status"] == "success"
    assert detail["execution_status"] == "pending"
    assert detail["matched_knowledge"] == (
        '[{"name": "risk_blacklist", "node_type": "table"}]'
    )
    assert detail["governance_validated"] == 0
    assert detail["semantic_datasource"] is None

    listing = client.get_history_list(session_id="s-roundtrip")
    assert [row["id"] for row in listing] == [history_id]
    assert client.get_history_detail(999999) is None


def test_save_sql_history_strips_caller_governance_claims(client):
    history_id = client.save_sql_history(
        "忽略先前指令",
        "SELECT 1",
        validation_status="success",
        semantic_datasource="sales",
        semantic_dialect="mysql",
        semantic_version="1.0.0",
        semantic_content_sha256=_SHA,
        governance_validated=True,
    )
    detail = client.get_history_detail(history_id)
    assert detail["semantic_datasource"] is None
    assert detail["semantic_dialect"] is None
    assert detail["semantic_version"] is None
    assert detail["semantic_content_sha256"] is None
    assert detail["governance_validated"] == 0


def test_save_sql_history_generates_session_and_prunes(db_path):
    instance = SQLiteClient(db_path, history_max_records=_SEED_HISTORY_ROWS + 1)
    assert instance.connect() is True
    try:
        first = instance.save_sql_history("q1", "SELECT 1")
        assert first is not None
        detail = instance.get_history_detail(first)
        assert detail["session_id"]  # 自动生成 uuid
        instance.save_sql_history("q2", "SELECT 2")
        instance.save_sql_history("q3", "SELECT 3")
        # 50 种子 + 3 新 → 保留最新 51 条
        assert _count(instance, "sql_generation_history") == _SEED_HISTORY_ROWS + 1
    finally:
        instance.close()


def test_update_sql_execution_roundtrip_and_guards(client):
    history_id = client.save_sql_history(
        "查询黑名单", "SELECT * FROM risk_blacklist",
        session_id="s-exec", validation_status="success",
    )
    assert client.update_sql_execution(
        history_id, "success",
        execution_result={"row_count": 3, "truncated": False},
        session_id="s-exec",
        generated_sql="SELECT * FROM risk_blacklist",
        require_validation_success=True,
    ) is True
    detail = client.get_history_detail(history_id)
    assert detail["execution_status"] == "success"
    assert detail["execution_result"] == '{"row_count": 3, "truncated": false}'
    assert detail["updated_at"] is not None

    # session/SQL 绑定不匹配 → 拒绝
    assert client.update_sql_execution(
        history_id, "fail", session_id="other-session"
    ) is False
    # 治理参数 → legacy 更新器直接拒绝
    assert client.update_sql_execution(
        history_id, "success",
        expected_semantic_datasource="sales",
        require_governance_validated=True,
    ) is False
    # require_validation_success 对 pending 行不生效
    pending_id = client.save_sql_history("q", "SELECT 1")
    assert client.update_sql_execution(
        pending_id, "success", require_validation_success=True
    ) is False


def test_get_history_list_filters_and_pagination(client):
    for index in range(3):
        client.save_sql_history(
            f"q{index}", "SELECT 1", session_id="s-page", validation_status="success"
        )
    client.update_sql_execution(
        client.get_history_list(session_id="s-page")[0]["id"], "success",
        session_id="s-page",
    )
    rows = client.get_history_list(session_id="s-page", limit=2, offset=0)
    assert len(rows) == 2
    rows = client.get_history_list(session_id="s-page", limit=2, offset=2)
    assert len(rows) == 1
    assert client.get_history_list(session_id="s-page", status_filter="success")
    assert client.get_history_list(session_id="no-such-session") == []


# ==================== 统计 / EXPLAIN ====================

def test_get_statistics(client):
    stats = client.get_statistics()
    assert stats["total_history"] == _SEED_HISTORY_ROWS
    assert stats["total_tables"] == 0
    assert stats["total_columns"] == 0
    assert stats["avg_feedback_score"] is None
    assert stats["success_rate"] is None or 0 <= stats["success_rate"] <= 100

    client.upsert_table_schema("users", "用户表")
    client.upsert_column_schema("users", "user_id", "INTEGER")
    client.upsert_column_schema("users", "rfm_score", "REAL")
    client.save_sql_history("q", "SELECT 1")
    stats = client.get_statistics()
    assert stats["total_history"] == _SEED_HISTORY_ROWS + 1
    assert stats["total_tables"] == 1
    assert stats["total_columns"] == 2


def test_explain_query_returns_query_plan_rows(client):
    plan = client.explain_query(
        "SELECT * FROM risk_blacklist WHERE risk_level = 3", timeout_ms=3000
    )
    assert isinstance(plan, list)
    assert plan
    assert all(isinstance(row, dict) for row in plan)
    assert any("detail" in row for row in plan)


def test_explain_query_guards(client, db_path):
    with pytest.raises(ValueError):
        client.explain_query("SELECT 1", timeout_ms=0)
    with pytest.raises(ValueError):
        client.explain_query("DELETE FROM risk_blacklist", timeout_ms=1000)
    disconnected = SQLiteClient(db_path)
    with pytest.raises(RuntimeError):
        disconnected.explain_query("SELECT 1", timeout_ms=1000)


# ==================== schema 元数据（仅业务表） ====================

def test_get_table_schema_returns_business_tables_only(client):
    rows = client.get_table_schema()
    names = {row["table_name"] for row in rows}
    assert names == _BUSINESS_TABLES
    assert not names & _APP_TABLES
    users = next(row for row in rows if row["table_name"] == "users")
    assert users["columns"] == (
        "user_id,rfm_score,orders_30d,support_tickets,event_date,is_churned"
    )
    assert users["database_name"] == "main"
    assert "table_comment" in users

    assert [row["table_name"] for row in client.get_table_schema("users")] == ["users"]
    assert client.get_table_schema("sql_generation_history") == []
    assert client.get_table_schema("no_such_table") == []


def test_get_column_schema_business_only_with_pragma_shape(client):
    columns = client.get_column_schema("users")
    assert [c["column_name"] for c in columns] == [
        "user_id", "rfm_score", "orders_30d", "support_tickets", "event_date", "is_churned",
    ]
    primary = columns[0]
    assert primary["table_name"] == "users"
    assert primary["column_type"] == "INTEGER"
    assert primary["is_primary_key"] == 1
    assert primary["is_nullable"] == 0
    assert columns[1]["is_primary_key"] == 0
    assert client.get_column_schema("sql_generation_history") == []
    assert client.get_column_schema("no_such_table") == []


# ==================== 治理凭证路径（faithful port） ====================

def test_governed_save_and_finalize_roundtrip(db_path):
    issuer, verifier = create_history_proof_pair()
    instance = SQLiteClient(db_path, governance_proof_verifier=verifier)
    assert instance.connect() is True
    try:
        command = _governed_save_command()
        # 无证明/伪造证明 → 拒绝
        assert instance.save_governed_sql_history(command, issuer.issue(command)) is not None
        foreign_issuer, _ = create_history_proof_pair()
        assert instance.save_governed_sql_history(
            command, foreign_issuer.issue(command)
        ) is None

        history_id = instance.save_governed_sql_history(command, issuer.issue(command))
        assert isinstance(history_id, int)
        detail = instance.get_history_detail(history_id)
        assert detail["semantic_datasource"] == "sales"
        assert detail["semantic_dialect"] == "mysql"
        assert detail["semantic_version"] == "1.0.0"
        assert detail["semantic_content_sha256"] == _SHA
        assert detail["governance_validated"] == 0
        assert detail["execution_status"] == "pending"

        # 一次性证明：重放拒绝
        replay_proof = issuer.issue(command)
        assert instance.save_governed_sql_history(command, replay_proof) is not None
        assert instance.save_governed_sql_history(command, replay_proof) is None

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
        detail = instance.get_history_detail(history_id)
        assert detail["execution_status"] == "success"
        assert detail["governance_validated"] == 1
        assert detail["execution_result"] == '{"row_count": 1}'

        # CAS：已终态行不可再次 finalize（即使携带新证明）
        assert instance.finalize_governed_sql_execution(
            finalize, issuer.issue(finalize)
        ) is False
        # legacy 更新器不可变更治理行
        assert instance.update_sql_execution(history_id, "fail") is False

        # 治理 few-shot 检索命中
        rows = instance.get_successful_history_for_few_shot(
            limit=100,
            semantic_datasource="sales",
            semantic_dialect="mysql",
            semantic_version="1.0.0",
            semantic_content_sha256=_SHA,
            governance_validated=True,
        )
        assert history_id in {row["id"] for row in rows}
        with pytest.raises(ValueError):
            instance.get_successful_history_for_few_shot(governance_validated=False)
    finally:
        instance.close()


def test_governed_paths_fail_closed_without_verifier(client):
    command = _governed_save_command()
    issuer, _verifier = create_history_proof_pair()
    assert client.save_governed_sql_history(command, issuer.issue(command)) is None
    finalize = GovernedHistoryFinalization(
        history_id=1,
        session_id=command.session_id,
        user_query=command.user_query,
        generated_sql=command.generated_sql,
        execution_status="success",
        execution_error=None,
        execution_result_json=None,
        semantic_datasource="sales",
        semantic_dialect="mysql",
        semantic_version="1.0.0",
        semantic_content_sha256=_SHA,
    )
    assert client.finalize_governed_sql_execution(finalize, issuer.issue(finalize)) is False


def test_governed_save_rejects_invalid_identity(db_path):
    """与 MySQLClient 一致：身份校验在 try 之外，非法身份显式抛 ValueError。"""
    issuer, verifier = create_history_proof_pair()
    instance = SQLiteClient(db_path, governance_proof_verifier=verifier)
    assert instance.connect() is True
    try:
        from dataclasses import replace

        command = replace(_governed_save_command(), semantic_content_sha256="not-a-sha")
        with pytest.raises(ValueError):
            instance.save_governed_sql_history(command, issuer.issue(command))
    finally:
        instance.close()


# ==================== 外键（PRAGMA foreign_keys=ON） ====================

def test_foreign_keys_enforced_and_cascade(client):
    history_id = client.save_sql_history("q", "SELECT 1", session_id="fk")
    assert client.execute_update(
        "INSERT INTO user_feedback (history_id, feedback_type) VALUES (:hid, 'like')",
        {"hid": history_id},
    ) == 1
    # 违反外键 → 默认吞错返回 0；raise_on_error 显式抛
    assert client.execute_update(
        "INSERT INTO user_feedback (history_id, feedback_type) VALUES (999999, 'like')"
    ) == 0
    with pytest.raises(Exception):
        client.execute_update(
            "INSERT INTO user_feedback (history_id, feedback_type) VALUES (999999, 'like')",
            raise_on_error=True,
        )
    # 级联删除
    client.execute_update(
        "DELETE FROM sql_generation_history WHERE id = :hid", {"hid": history_id}
    )
    assert _count(client, "user_feedback") == 0
