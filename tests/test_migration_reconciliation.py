"""MySQL→SQLite 迁移对账测试（spec §5.2 / Task 1）。

种子文件由 scripts/migrate_mysql_to_sqlite.py 从源 MySQL（business_db）只读生成：
- data/seed_business.sql：8 业务表 DDL + 30 行
- data/seed_history.sql：6 应用表 DDL + 50 行历史（sql_generation_history）

本测试不连接 MySQL：用 sqlite3 :memory: 加载种子，逐表 COUNT 对账控制器核定的
源行数，并用 PRAGMA table_info 校验类型亲和（spec §5.1 映射）。
"""
import sqlite3
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_BUSINESS = PROJECT_ROOT / "data" / "seed_business.sql"
SEED_HISTORY = PROJECT_ROOT / "data" / "seed_history.sql"

# 源 MySQL business_db 逐表行数（迁移前核定，2026-11-19）
EXPECTED_COUNTS = {
    # 业务表（合计 30 行＝12+8+6+3+1；brief/spec  prose 的“31”为笔误，
    # 逐表数与活体源库两次核验一致，对账以逐表 COUNT==源为准）
    "users": 12,
    "transaction_record": 8,
    "user_account": 6,
    "risk_blacklist": 3,
    "prediction_results": 1,
    "account_freeze_log": 0,
    "daily_account_check": 0,
    "fee_rate_config": 0,
    # 应用表（历史 50 行，其余 0）
    "sql_generation_history": 50,
    "user_feedback": 0,
    "table_schema": 0,
    "column_schema": 0,
    "knowledge_metadata": 0,
    "retrieval_terms": 0,
}


@pytest.fixture()
def seed_db():
    """将两个种子文件加载进内存库（每个测试独立、可重复）。"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SEED_BUSINESS.read_text(encoding="utf-8"))
        conn.executescript(SEED_HISTORY.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.close()


def _table_info(conn, table):
    return {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}


def test_seed_row_counts_match_source(seed_db):
    tables = {
        row[0]
        for row in seed_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == set(EXPECTED_COUNTS), "种子表集合必须与源 14 表一致"
    for table, expected in EXPECTED_COUNTS.items():
        actual = seed_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert actual == expected, f"{table}: 种子 {actual} 行 != 源 {expected} 行"
    business_total = sum(
        seed_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in EXPECTED_COUNTS
        if t not in {"sql_generation_history", "user_feedback", "table_schema",
                     "column_schema", "knowledge_metadata", "retrieval_terms"}
    )
    assert business_total == 30


def test_seed_business_schema_types(seed_db):
    # users：非自增 BIGINT 主键 → INTEGER PK（无 AUTOINCREMENT）
    users = _table_info(seed_db, "users")
    assert users["user_id"][2] == "INTEGER"
    assert users["user_id"][5] == 1  # pk
    assert users["rfm_score"][2] == "REAL"  # DOUBLE → REAL
    assert users["event_date"][2] == "TEXT"  # DATE → TEXT
    assert users["is_churned"][2] == "INTEGER"  # TINYINT → INTEGER

    # 货币列 DECIMAL → NUMERIC 亲和
    for table, column in [
        ("user_account", "balance"),
        ("user_account", "frozen_balance"),
        ("transaction_record", "trans_amount"),
        ("transaction_record", "fee_amount"),
        ("fee_rate_config", "rate_fee"),
        ("account_freeze_log", "freeze_amount"),
    ]:
        info = _table_info(seed_db, table)
        assert info[column][2] == "NUMERIC", f"{table}.{column} 应为 NUMERIC"

    # DATETIME → TEXT；自增 BIGINT 主键 → INTEGER PRIMARY KEY AUTOINCREMENT
    trans = _table_info(seed_db, "transaction_record")
    assert trans["create_time"][2] == "TEXT"
    assert trans["id"][2] == "INTEGER" and trans["id"][5] == 1
    ddl = seed_db.execute(
        "SELECT sql FROM sqlite_master WHERE name='transaction_record'"
    ).fetchone()[0]
    assert "AUTOINCREMENT" in ddl


def test_seed_app_schema_types(seed_db):
    hist = _table_info(seed_db, "sql_generation_history")
    assert hist["id"][2] == "INTEGER" and hist["id"][5] == 1
    assert hist["sql_dialect"][2] == "TEXT"
    # 新行默认方言 sqlite（spec §5.4）；迁移旧行保留 mysql（见下方测试）
    assert hist["sql_dialect"][4] == "'sqlite'"
    assert hist["governance_validated"][2] == "INTEGER"
    assert hist["governance_validated"][3] == 1  # NOT NULL
    assert hist["governance_validated"][4] == "0"
    assert hist["execution_result"][2] == "TEXT"  # JSON → TEXT
    assert hist["matched_knowledge"][2] == "TEXT"
    assert hist["created_at"][2] == "TEXT"  # TIMESTAMP → TEXT
    assert hist["created_at"][4] == "CURRENT_TIMESTAMP"
    assert hist["semantic_content_sha256"][2] == "TEXT"  # CHAR(64) → TEXT

    # 其余应用表主键/亲和抽查
    for table in ("user_feedback", "table_schema", "column_schema",
                  "knowledge_metadata", "retrieval_terms"):
        info = _table_info(seed_db, table)
        assert info["id"][2] == "INTEGER" and info["id"][5] == 1
    assert _table_info(seed_db, "retrieval_terms")["weight"][2] == "REAL"
    assert _table_info(seed_db, "table_schema")["properties"][2] == "TEXT"

    # 外键保留：user_feedback.history_id → sql_generation_history(id) CASCADE
    fks = list(seed_db.execute("PRAGMA foreign_key_list(user_feedback)"))
    assert len(fks) == 1
    assert fks[0][2] == "sql_generation_history"
    assert fks[0][3] == "history_id" and fks[0][4] == "id"
    assert fks[0][6] == "CASCADE"


def test_legacy_history_rows_keep_mysql_dialect(seed_db):
    # 源 50 行历史 sql_dialect 全为 'mysql'，迁移必须忠实保留
    total, mysql_rows = seed_db.execute(
        "SELECT COUNT(*), SUM(CASE WHEN sql_dialect='mysql' THEN 1 ELSE 0 END) "
        "FROM sql_generation_history"
    ).fetchone()
    assert total == 50 and mysql_rows == 50
    # 源 id 范围 1..79（有空洞），显式 id 必须保留
    assert seed_db.execute(
        "SELECT COUNT(DISTINCT id), MIN(id), MAX(id) FROM sql_generation_history"
    ).fetchone() == (50, 1, 79)


def test_new_history_row_defaults_to_sqlite_dialect(seed_db):
    seed_db.execute(
        "INSERT INTO sql_generation_history (user_query) VALUES ('对账测试查询')"
    )
    row = seed_db.execute(
        "SELECT sql_dialect, validation_status, execution_status, governance_validated "
        "FROM sql_generation_history WHERE user_query='对账测试查询'"
    ).fetchone()
    assert row == ("sqlite", "pending", "pending", 0)
    # AUTOINCREMENT：新行 id 必须大于迁移保留的最大 id
    new_id = seed_db.execute(
        "SELECT id FROM sql_generation_history WHERE user_query='对账测试查询'"
    ).fetchone()[0]
    assert new_id > 79


def test_seed_money_and_datetime_fidelity(seed_db):
    # 源值抽查（只读 SELECT 核定）：transaction_record id=1
    amount, fee, created, currency = seed_db.execute(
        "SELECT trans_amount, fee_amount, create_time, currency_code "
        "FROM transaction_record WHERE id=1"
    ).fetchone()
    assert float(amount) == pytest.approx(5000.0)
    assert float(fee) == pytest.approx(0.0)
    assert created == "2026-10-29 17:49:03"
    assert currency == "CNY"
    # user_account id=1 余额 25800.5000
    balance = seed_db.execute(
        "SELECT balance FROM user_account WHERE id=1"
    ).fetchone()[0]
    assert float(balance) == pytest.approx(25800.5)
    # prediction_results：DATETIME + FLOAT 忠实
    exported, prob = seed_db.execute(
        "SELECT exported_at, probability FROM prediction_results WHERE id=1"
    ).fetchone()
    assert exported == "2026-11-12 19:44:39"
    assert float(prob) == pytest.approx(0.979167)
