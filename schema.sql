-- ==========================================
-- Text2SQL 智能体应用表建表语句（SQLite）
-- ==========================================
-- 应用存储为单文件嵌入式 SQLite 库（默认 data/text2sql.db，SQLITE_PATH 可配）。
-- 本文件是 6 张应用表的参考 DDL，逐字镜像 data/seed_history.sql 的 canonical DDL
-- （与 core/history/sqlite_client.py 的内联建表语句一致）：
--   * INTEGER PRIMARY KEY AUTOINCREMENT 自增主键；TEXT/INTEGER/REAL 类型亲和；
--   * 索引名按表命名空间化（SQLite 索引名全库唯一）；
--   * sql_generation_history.sql_dialect 新行默认 'sqlite'（迁移旧行保留 'mysql'）；
--   * 去 MySQL ENGINE/CHARSET/COMMENT/ON UPDATE CURRENT_TIMESTAMP
--     （应用层 UPDATE 显式置 updated_at=CURRENT_TIMESTAMP，行为不变）。
-- 无需手工执行：应用首次连接即幂等自动建表（CREATE TABLE IF NOT EXISTS）、
-- 执行治理列迁移并原子加载 data/seed_business.sql / data/seed_history.sql 种子。
-- 业务表（users/transaction_record/risk_blacklist 等 8 表）DDL 与数据见
-- data/seed_business.sql，不在本文件范围。
-- 如需手工建库：sqlite3 data/text2sql.db < schema.sql

-- ==========================================
-- 1. SQL 生成历史表
-- 存储 SQL 生成和使用历史
-- ==========================================
CREATE TABLE IF NOT EXISTS sql_generation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_query TEXT NOT NULL,
    generated_sql TEXT,
    sql_dialect TEXT DEFAULT 'sqlite',
    semantic_datasource TEXT,
    semantic_dialect TEXT,
    semantic_version TEXT,
    semantic_content_sha256 TEXT,
    governance_validated INTEGER NOT NULL DEFAULT 0,
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
);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_created_at ON sql_generation_history (created_at);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_execution_status ON sql_generation_history (execution_status);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_governed_few_shot ON sql_generation_history (governance_validated, semantic_datasource, semantic_dialect, semantic_version, semantic_content_sha256, validation_status, execution_status, created_at);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_session ON sql_generation_history (session_id);
CREATE INDEX IF NOT EXISTS sql_generation_history_idx_validation_status ON sql_generation_history (validation_status);

-- ==========================================
-- 2. 用户反馈表
-- 存储用户对生成 SQL 的反馈
-- ==========================================
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    feedback_content TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (history_id) REFERENCES sql_generation_history (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS user_feedback_idx_history_id ON user_feedback (history_id);

-- ==========================================
-- 3. 数据表信息表
-- 存储业务数据库的表结构元数据
-- ==========================================
CREATE TABLE IF NOT EXISTS table_schema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    table_comment TEXT,
    properties TEXT,
    database_name TEXT DEFAULT 'text2sql_db',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_table_name UNIQUE (table_name, database_name)
);

-- ==========================================
-- 4. 字段信息表
-- 存储业务数据库的字段结构元数据
-- ==========================================
CREATE TABLE IF NOT EXISTS column_schema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT NOT NULL,
    is_nullable INTEGER DEFAULT 1,
    is_primary_key INTEGER DEFAULT 0,
    column_comment TEXT,
    default_value TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS column_schema_idx_table_id ON column_schema (table_id);

-- ==========================================
-- 5. 知识库元数据表
-- 存储从 Neo4j 同步的图节点元数据
-- ==========================================
CREATE TABLE IF NOT EXISTS knowledge_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    node_label TEXT NOT NULL,
    description TEXT,
    properties TEXT,
    related_tables TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_label ON knowledge_metadata (node_label);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_type ON knowledge_metadata (node_type);
CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_related_tables ON knowledge_metadata (related_tables);

-- ==========================================
-- 6. 检索词表
-- 存储用于 BM25+TF-IDF 检索的分词
-- ==========================================
CREATE TABLE IF NOT EXISTS retrieval_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    node_id TEXT NOT NULL,
    term_type TEXT,
    weight REAL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS retrieval_terms_idx_node_id ON retrieval_terms (node_id);
CREATE INDEX IF NOT EXISTS retrieval_terms_idx_term ON retrieval_terms (term);
