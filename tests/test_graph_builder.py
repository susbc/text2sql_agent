"""
知识图谱构建模块测试脚本
"""
import sys
import os
import json
import sqlite3
from pathlib import Path

import pytest

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config import NEO4J_ENABLED, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL
from core.knowledge.neo4j_client import Neo4jClient
from core.graph_builder import run_pipeline, GraphBuilderPipeline
from core.graph_builder.extractors.live_db_extractor import LiveDBExtractor
from core.graph_builder.extractors.offline_extractor import OfflineExtractor
from core.graph_builder.extractors.offline_json_extractor import OfflineJSONExtractor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_BUSINESS = PROJECT_ROOT / "data" / "seed_business.sql"
SEED_HISTORY = PROJECT_ROOT / "data" / "seed_history.sql"

# 与 core/history/sqlite_client._APP_TABLES / live_db_extractor._APP_TABLES 对齐
APP_TABLES = {
    "knowledge_metadata", "table_schema", "column_schema",
    "sql_generation_history", "retrieval_terms", "user_feedback",
}
BUSINESS_TABLES = {
    "users", "transaction_record", "user_account", "risk_blacklist",
    "prediction_results", "account_freeze_log", "daily_account_check",
    "fee_rate_config",
}


def _seed_sqlite_file(db_path: Path, extra_ddl: str = ""):
    """用种子文件初始化临时 SQLite 库（业务 8 表 + 应用 6 表，供排除断言）。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SEED_BUSINESS.read_text(encoding="utf-8"))
        conn.executescript(SEED_HISTORY.read_text(encoding="utf-8"))
        if extra_ddl:
            conn.executescript(extra_ddl)
    finally:
        conn.close()

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="{message}")


def test_offline_extractor():
    """测试离线 DDL 抽取器"""
    print("\n" + "=" * 60)
    print("测试 1: 离线 DDL 抽取器")
    print("=" * 60)

    ddl_content = """
    CREATE TABLE bank_customer (
        customer_id BIGINT PRIMARY KEY COMMENT '客户 ID',
        customer_name VARCHAR(100) NOT NULL COMMENT '客户姓名',
        id_card VARCHAR(18) COMMENT '身份证号',
        phone VARCHAR(20) COMMENT '手机号'
    ) COMMENT='客户信息表';

    CREATE TABLE deposit_account (
        account_id VARCHAR(32) PRIMARY KEY COMMENT '账户 ID',
        customer_id BIGINT NOT NULL COMMENT '客户 ID',
        account_type VARCHAR(10) COMMENT '账户类型',
        balance DECIMAL(18,2) DEFAULT 0 COMMENT '余额'
    ) COMMENT='存款账户表';

    CREATE TABLE transaction_record (
        trans_id VARCHAR(64) PRIMARY KEY COMMENT '交易 ID',
        account_id VARCHAR(32) NOT NULL COMMENT '账户 ID',
        trans_type VARCHAR(10) COMMENT '交易类型',
        amount DECIMAL(18,2) NOT NULL COMMENT '金额'
    ) COMMENT='交易流水表';
    """

    ddl_path = Path("/tmp/test_schema.sql")
    ddl_path.write_text(ddl_content, encoding="utf-8")

    try:
        pipeline = GraphBuilderPipeline(
            llm_provider=LLM_PROVIDER,
            llm_model=LLM_MODEL,
            llm_config={"api_key": LLM_API_KEY, "base_url": LLM_BASE_URL} if LLM_API_KEY else {}
        )

        result = pipeline.extract_from_files(
            ddl_path=str(ddl_path),
            database_name="bank_db"
        )

        print("\n抽取完成！")
        print(f"   数据库：{len(result.databases)}")
        print(f"   表：{len(result.tables)}")
        print(f"   字段：{sum(len(t.columns) for t in result.tables)}")
        print(f"   关系：{len(result.relationships)}")

        print("\n表列表:")
        for table in result.tables:
            print(f"   - {table.name}: {len(table.columns)} 个字段")
            if table.description:
                print(f"     注释：{table.description}")

        if result.relationships:
            print("\n推断的关系:")
            for rel in result.relationships:
                print(f"   - {rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}")

        assert len(result.databases) == 1
        assert len(result.tables) == 3
        assert sum(len(t.columns) for t in result.tables) == 12

    finally:
        if ddl_path.exists():
            ddl_path.unlink()


def test_offline_json_extractor_preserves_multi_database_metadata(tmp_path):
    """JSON 导入应保留多数据库、字段别名和关系扩展属性。"""
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({
        "databases": [
            {"database_id": 10, "name": "sales", "db_type": "mysql"},
            {"id": 20, "name": "finance", "db_type": "mysql"}
        ],
        "tables": [
            {
                "name": "orders",
                "database": "sales",
                "columns": [
                    {"name": "id", "type": "BIGINT", "is_partition": True}
                ],
                "properties": {"owner": "bi"}
            },
            {
                "name": "invoice",
                "database_id": 20,
                "columns": [
                    {"name": "order_id", "data_type": "BIGINT"}
                ]
            }
        ],
        "relationships": [
            {
                "from_table": "invoice",
                "from_column": "order_id",
                "to_table": "orders",
                "to_column": "id",
                "relationship_type": "foreign_key",
                "weight": 0.7,
                "occurrence_count": 3,
                "source": "import"
            }
        ],
        "concepts": [
            {"name": "订单", "related_tables": ["orders"]}
        ]
    }, ensure_ascii=False), encoding="utf-8")

    result = OfflineJSONExtractor(json_path=str(graph_path)).extract()

    assert [db.id for db in result.databases] == [10, 20]
    assert result.tables[0].database_id == 10
    assert result.tables[1].database == "finance"
    assert result.tables[0].columns[0].data_type == "BIGINT"
    assert result.tables[0].columns[0].is_partition is True
    assert result.relationships[0].weight == 0.7
    assert result.relationships[0].occurrence_count == 3
    assert result.relationships[0].source == "import"
    assert result.relationships[0].from_database == "finance"
    assert result.relationships[0].from_database_id == 20
    assert result.relationships[0].to_database == "sales"
    assert result.relationships[0].to_database_id == 10
    assert result.concepts[0].mapped_tables == ["orders"]


def test_offline_extractor_column_types_and_nullable(tmp_path):
    """括号类型不得损坏；显式 NULL/DEFAULT NULL 可空，NOT NULL 与主键不可空。"""
    ddl_path = tmp_path / "types.sql"
    ddl_path.write_text("""
    CREATE TABLE sample (
        name VARCHAR(100) NOT NULL COMMENT '名称',
        price DECIMAL(18,2) DEFAULT 0 COMMENT '价格',
        note TEXT DEFAULT NULL COMMENT '备注',
        flag TINYINT NULL COMMENT '显式可空',
        id BIGINT PRIMARY KEY COMMENT '主键'
    ) COMMENT='样例表';
    """, encoding="utf-8")

    result = OfflineExtractor(ddl_path=str(ddl_path)).extract()
    columns = {c.name: c for c in result.tables[0].columns}

    assert columns["name"].data_type == "VARCHAR"
    assert columns["name"].is_nullable is False
    assert columns["price"].data_type == "DECIMAL"
    assert columns["price"].is_nullable is True
    assert columns["note"].is_nullable is True
    assert columns["flag"].is_nullable is True
    assert columns["id"].is_nullable is False


def test_offline_extractor_multi_database_ddl(tmp_path):
    """USE 语句与 db.table 限定名应把表归到正确的数据库。"""
    ddl_path = tmp_path / "multi_db.sql"
    ddl_path.write_text("""
    CREATE DATABASE sales;
    CREATE DATABASE finance;
    USE sales;
    CREATE TABLE orders (order_id BIGINT PRIMARY KEY) COMMENT='订单';
    CREATE TABLE finance.invoice (invoice_id BIGINT PRIMARY KEY) COMMENT='发票';
    USE finance;
    CREATE TABLE account (account_id BIGINT PRIMARY KEY) COMMENT='账户';
    """, encoding="utf-8")

    result = OfflineExtractor(ddl_path=str(ddl_path)).extract()
    by_name = {t.name: t for t in result.tables}

    assert {d.name for d in result.databases} == {"sales", "finance"}
    assert by_name["orders"].database == "sales"
    assert by_name["invoice"].database == "finance"
    assert by_name["account"].database == "finance"
    assert all(t.database_id for t in result.tables)


def test_full_pipeline_with_neo4j():
    """测试完整流水线 + Neo4j 装载"""
    if os.getenv("TEXT2SQL_RUN_DB_TESTS") != "1" or not NEO4J_ENABLED:
        pytest.skip("设置 TEXT2SQL_RUN_DB_TESTS=1 且 NEO4J_ENABLED=true 后运行真实 Neo4j 装载测试")

    print("\n" + "=" * 60)
    print("测试 2: 完整流水线 + Neo4j 装载")
    print("=" * 60)

    ddl_content = """
    CREATE TABLE bank_customer (
        customer_id BIGINT PRIMARY KEY,
        customer_name VARCHAR(100),
        id_card VARCHAR(18),
        phone VARCHAR(20)
    ) COMMENT='客户信息表';

    CREATE TABLE deposit_account (
        account_id VARCHAR(32) PRIMARY KEY,
        customer_id BIGINT,
        account_type VARCHAR(10),
        balance DECIMAL(18,2)
    ) COMMENT='存款账户表';
    """

    ddl_path = Path("/tmp/test_neo4j.sql")
    ddl_path.write_text(ddl_content, encoding="utf-8")

    try:
        # 已废弃的全局单例 get_neo4j_client 已移除；测试自行管理客户端生命周期
        neo4j_client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        neo4j_client.connect()

        stats = run_pipeline(
            source_type="offline",
            source_config={
                "ddl_path": str(ddl_path),
                "database_name": "bank_db"
            },
            neo4j_client=neo4j_client,
            llm_provider=LLM_PROVIDER,
            llm_model=LLM_MODEL,
            enable_enrichment=False
        )

        print("\n流水线完成！")
        print(f"   抽取统计：{stats['extract']}")
        print(f"   装载统计：{stats['load']}")

        print("\nNeo4j 图谱统计:")
        result = neo4j_client.execute_query("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
        for row in result:
            print(f"   - {row['label']}: {row['count']}")

        assert stats["extract"]["tables"] == 2
        assert stats["load"]["tables"] >= 2

    except Exception as e:
        print(f"Neo4j 测试失败：{e}")
    finally:
        if ddl_path.exists():
            ddl_path.unlink()


def test_live_extract_sqlite(tmp_path):
    """活体抽取 SQLite：db_type='sqlite'，仅业务表（排除 6 应用表），列元数据正确。"""
    db_path = tmp_path / "text2sql.db"
    _seed_sqlite_file(db_path)

    extractor = LiveDBExtractor(db_uri=f"sqlite:///{db_path}", db_type="sqlite")
    try:
        result = extractor.extract()
    finally:
        extractor.close()

    assert result.metadata["source_type"] == "live_db"
    assert len(result.databases) == 1
    db = result.databases[0]
    assert db.db_type == "sqlite"
    assert db.name == "main"

    names = {t.name for t in result.tables}
    assert {"users", "risk_blacklist"} <= names
    assert names == BUSINESS_TABLES
    assert not (names & APP_TABLES)
    assert all(t.database == "main" for t in result.tables)

    users = next(t for t in result.tables if t.name == "users")
    cols = {c.name: c for c in users.columns}
    assert cols["user_id"].is_primary_key is True
    assert cols["user_id"].is_nullable is False
    assert cols["user_id"].data_type == "INTEGER"
    assert cols["rfm_score"].data_type == "REAL"
    assert cols["event_date"].data_type == "TEXT"

    # INTEGER PRIMARY KEY AUTOINCREMENT：PRAGMA notnull=0 但主键语义不可空
    account = next(t for t in result.tables if t.name == "user_account")
    account_cols = {c.name: c for c in account.columns}
    assert account_cols["id"].is_primary_key is True
    assert account_cols["id"].is_nullable is False
    assert account_cols["remark"].is_nullable is True

    # 命名启发式关系（与 MySQL 路径一致）：user_account.user_id → users
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert (rel.from_table, rel.from_column, rel.to_table, rel.to_column) == (
        "user_account", "user_id", "users", "user_id"
    )


def test_live_extract_sqlite_schema_override(tmp_path):
    """显式 schema 名覆盖默认的 main（DatabaseIR 与 TableIR 一致）。"""
    db_path = tmp_path / "named.db"
    _seed_sqlite_file(db_path)

    extractor = LiveDBExtractor(db_uri=f"sqlite:///{db_path}", db_type="sqlite", schema="business_db")
    try:
        result = extractor.extract()
    finally:
        extractor.close()

    assert result.databases[0].name == "business_db"
    assert all(t.database == "business_db" for t in result.tables)


def test_live_extract_sqlite_fk_relationships(tmp_path):
    """声明外键优先成为关系；与启发式去重；指向应用表的外键被排除。"""
    db_path = tmp_path / "fk.db"
    _seed_sqlite_file(db_path, extra_ddl="""
        CREATE TABLE probe_child (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            remark TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE TABLE probe_pk_ref (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users
        );
        CREATE TABLE probe_app_ref (
            id INTEGER PRIMARY KEY,
            history_id INTEGER,
            FOREIGN KEY (history_id) REFERENCES sql_generation_history (id)
        );
    """)

    extractor = LiveDBExtractor(db_uri=f"sqlite:///{db_path}", db_type="sqlite")
    try:
        result = extractor.extract()
    finally:
        extractor.close()

    rels = {
        (r.from_table, r.from_column, r.to_table, r.to_column)
        for r in result.relationships
    }
    assert ("probe_child", "user_id", "users", "user_id") in rels
    # 省略被引用列的 FK 回退到对方主键
    assert ("probe_pk_ref", "user_id", "users", "user_id") in rels
    # 指向应用表的外键不建模
    assert not any(r.from_table == "probe_app_ref" for r in result.relationships)
    # FK 与启发式推断去重：同一 (from_table, from_column) 只保留一条
    assert sum(1 for r in result.relationships if r.from_table == "probe_child") == 1
    assert sum(
        1 for r in result.relationships
        if r.from_table == "user_account" and r.from_column == "user_id"
    ) == 1


def test_live_extract_sqlite_excludes_uppercase_app_tables(tmp_path):
    """SQLite 标识符大小写不敏感：大写应用表同样被排除，大写业务表正常抽取。"""
    db_path = tmp_path / "case.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SEED_BUSINESS.read_text(encoding="utf-8"))
        conn.executescript("""
            CREATE TABLE SQL_GENERATION_HISTORY (id INTEGER PRIMARY KEY, user_query TEXT);
            CREATE TABLE EXTRA_BIZ (id INTEGER PRIMARY KEY, note TEXT);
        """)
    finally:
        conn.close()

    extractor = LiveDBExtractor(db_uri=f"sqlite:///{db_path}", db_type="sqlite")
    try:
        result = extractor.extract()
    finally:
        extractor.close()

    names = {t.name for t in result.tables}
    assert "SQL_GENERATION_HISTORY" not in names
    assert names == BUSINESS_TABLES | {"EXTRA_BIZ"}


def test_live_extract_sqlite_missing_file(tmp_path):
    """缺文件直接报错，只读抽取不得静默创建空库文件。"""
    missing = tmp_path / "nope.db"
    extractor = LiveDBExtractor(db_uri=f"sqlite:///{missing}", db_type="sqlite")
    with pytest.raises(FileNotFoundError, match="不存在"):
        extractor.extract()
    assert not missing.exists()


def test_live_extract_unsupported_db_type():
    """sqlite 之外的方言一律拒绝（含 mysql——活体抽取已 SQLite-only；离线 DDL/JSON 通道不变）。"""
    extractor = LiveDBExtractor(db_uri="oracle://unused", db_type="oracle")
    with pytest.raises(ValueError, match="暂不支持"):
        extractor.extract()

    mysql_extractor = LiveDBExtractor(db_uri="mysql://unused", db_type="mysql")
    with pytest.raises(ValueError, match="暂不支持"):
        mysql_extractor.extract()


def test_extract_from_db_default_sqlite(tmp_path):
    """流水线 extract_from_db 默认 db_type 已切到 sqlite（不显式传参）。"""
    db_path = tmp_path / "default.db"
    _seed_sqlite_file(db_path)

    pipeline = GraphBuilderPipeline()
    result = pipeline.extract_from_db(db_uri=f"sqlite:///{db_path}")

    assert result.databases[0].db_type == "sqlite"
    assert {t.name for t in result.tables} == BUSINESS_TABLES


def test_neo4j_database_metadata_reflects_sqlite():
    """R3 运行时已将 Database.db_type 外科式更新为 sqlite；此处为可选活体核实。

    默认跳过（单测不依赖活体 Neo4j）；TEXT2SQL_RUN_DB_TESTS=1 且 NEO4J_ENABLED=true
    时核实迁移后的元数据状态。
    """
    if os.getenv("TEXT2SQL_RUN_DB_TESTS") != "1" or not NEO4J_ENABLED:
        pytest.skip("设置 TEXT2SQL_RUN_DB_TESTS=1 且 NEO4J_ENABLED=true 后运行真实 Neo4j 核实")

    client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    assert client.connect()
    try:
        rows = client.execute_query(
            "MATCH (d:Database) RETURN d.name AS name, d.db_type AS db_type",
            raise_on_error=True,
        )
        assert rows, "Neo4j 中应存在 Database 节点"
        assert all(r["db_type"] == "sqlite" for r in rows)
    finally:
        client.close()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("知识图谱构建模块 - 测试套件")
    print("=" * 60)

    # 测试 1: 离线抽取
    test_offline_extractor()

    # 测试 2: 完整流水线（如果 Neo4j 可用）
    try:
        if NEO4J_URI and NEO4J_USER:
            test_full_pipeline_with_neo4j()
        else:
            print("\nNeo4j 配置缺失，跳过测试 2")
    except Exception as e:
        print(f"\nNeo4j 测试失败：{e}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
