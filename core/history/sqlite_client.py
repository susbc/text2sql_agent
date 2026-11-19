"""
SQLite 数据库客户端（MySQLClient 的 drop-in 替代）
负责元数据存储、历史记录管理；应用表与业务表同处一个嵌入式 SQLite 文件库。

设计决策（spec §5.1/§5.2/§5.3，Task 2）：
- 引擎：create_engine("sqlite:///<path>", connect_args={"check_same_thread": False})。
  文件库用 NullPool（每次 checkout 新建连接、归还即关闭）——嵌入式单文件库并发低，
  避免池化连接残留 progress_handler/interrupt 状态；:memory: 用 StaticPool 保持单连接。
  每连接 PRAGMA foreign_keys=ON（user_feedback→history 的 ON DELETE CASCADE 依赖它）。
- 初始化：6 应用表 DDL 内联幂等创建（逐字镜像 data/seed_history.sql 的 canonical DDL，
  索引名按表命名空间化）。种子仅在 fresh 初始化加载：seed_history.sql 要求空库
  （无任何表），seed_business.sql 要求 8 业务表全缺——显式 id INSERT 对已填充库重放
  会主键冲突，故严格门控（spec §5.2）。
- 超时看门狗（Q4）：SQLite 无 MAX_EXECUTION_TIME hint；execute_query_limited 用
  threading.Timer 调 Connection.interrupt + progress_handler 双保险实现 timeout_ms。
  默认预算惰性读取 config.SQL_QUERY_TIMEOUT_MS（不改构造签名），失败回退 10s。
- database 属性＝"main"（SQLite 真实 schema 名；spec §5.3 allowed_schemas 按 main 处理）。
- get_table_schema/get_column_schema 改查 sqlite_master + PRAGMA table_info，仅返回
  业务表（排除 6 应用表），供安全边界（Task 4）；返回键形与 MySQLClient 对齐。
- ON UPDATE CURRENT_TIMESTAMP 已去除：所有应用 UPDATE 显式置 updated_at（行为不变）。
"""
import json
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from threading import Timer
from time import monotonic
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.pool import NullPool, StaticPool
from sqlglot import exp, parse_one

from ..config_validation import validate_history_max_records
from ..sql.preflight import ExplainDeadlineExceeded, run_with_wall_clock_deadline
from ..utils.log_sanitizer import log_safe_exception, text_fingerprint
from .proof import (
    GovernedHistoryFinalization,
    GovernedHistorySave,
    HistoryMutationProof,
    HistoryProofVerifier,
)

_SEMANTIC_CONTENT_SHA256 = re.compile(r"[0-9a-f]{64}")
_HISTORY_GOVERNANCE_COLUMNS = (
    ("semantic_datasource", "TEXT"),
    ("semantic_dialect", "TEXT"),
    ("semantic_version", "TEXT"),
    ("semantic_content_sha256", "TEXT"),
    ("governance_validated", "INTEGER NOT NULL DEFAULT 0"),
)
# SQLite 索引名全库唯一：沿用 Task 1 命名空间化后的名字（<table>_<源索引名>）。
_GOVERNED_FEW_SHOT_INDEX = "sql_generation_history_idx_governed_few_shot"
_DUPLICATE_SCHEMA_MARKERS = ("duplicate column name", "already exists")

_APP_TABLES = frozenset(
    (
        "knowledge_metadata", "table_schema", "column_schema",
        "sql_generation_history", "retrieval_terms", "user_feedback",
    )
)
_BUSINESS_TABLES = frozenset(
    (
        "users", "transaction_record", "user_account", "risk_blacklist",
        "prediction_results", "account_freeze_log", "daily_account_check",
        "fee_rate_config",
    )
)
_SEED_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_QUERY_TIMEOUT_MS = 10_000

# 应用表幂等建表语句：逐字镜像 data/seed_history.sql 的 canonical DDL（Task 1 report §3）。
# sql_dialect 新行默认 'sqlite'；索引名按表命名空间化。
# 表与索引分两阶段执行（先建表→列迁移→再建索引）：MySQL 的 CREATE TABLE IF NOT EXISTS
# 对已存在旧表整体 no-op（内联 INDEX 子句不执行），SQLite 独立 CREATE INDEX 若先于
# 治理列迁移会因缺列失败，故索引必须在 _migrate_history_schema 之后创建。
_APP_TABLE_DDL = (
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_id INTEGER NOT NULL,
        feedback_type TEXT NOT NULL,
        feedback_content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (history_id) REFERENCES sql_generation_history (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS table_schema (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        table_comment TEXT,
        properties TEXT,
        database_name TEXT DEFAULT 'text2sql_db',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uk_table_name UNIQUE (table_name, database_name)
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieval_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT NOT NULL,
        node_id TEXT NOT NULL,
        term_type TEXT,
        weight REAL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
)

# 12 条命名空间化索引（canonical，镜像 seed_history.sql）；列迁移完成后幂等创建。
_APP_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_created_at "
    "ON sql_generation_history (created_at)",
    "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_execution_status "
    "ON sql_generation_history (execution_status)",
    "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_governed_few_shot "
    "ON sql_generation_history (governance_validated, semantic_datasource, "
    "semantic_dialect, semantic_version, semantic_content_sha256, "
    "validation_status, execution_status, created_at)",
    "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_session "
    "ON sql_generation_history (session_id)",
    "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_validation_status "
    "ON sql_generation_history (validation_status)",
    "CREATE INDEX IF NOT EXISTS user_feedback_idx_history_id "
    "ON user_feedback (history_id)",
    "CREATE INDEX IF NOT EXISTS column_schema_idx_table_id ON column_schema (table_id)",
    "CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_label "
    "ON knowledge_metadata (node_label)",
    "CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_node_type "
    "ON knowledge_metadata (node_type)",
    "CREATE INDEX IF NOT EXISTS knowledge_metadata_idx_related_tables "
    "ON knowledge_metadata (related_tables)",
    "CREATE INDEX IF NOT EXISTS retrieval_terms_idx_node_id ON retrieval_terms (node_id)",
    "CREATE INDEX IF NOT EXISTS retrieval_terms_idx_term ON retrieval_terms (term)",
)


class QueryTimeoutExceeded(TimeoutError):
    """查询超过 wall-clock 预算，被看门狗 interrupt 取消。"""


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    """每个新建 DBAPI 连接开启外键（SQLite 默认关闭，须每连接设置）。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


class SQLiteClient:
    """SQLite 数据库客户端 - 沿用 MySQLClient 公开接口（SQLAlchemy-SQLite 引擎）"""

    explain_query_enforces_wall_clock_deadline = True

    def __init__(self, path: str, *, history_max_records: int = 1000,
                 governance_proof_verifier: HistoryProofVerifier | None = None):
        """
        初始化 SQLite 客户端

        Args:
            path: SQLite 文件路径（":memory:" 为内存库，StaticPool 单连接）
            history_max_records: 历史上限（pruning 保留条数）
            governance_proof_verifier: 治理凭证校验器（None 时治理路径 fail-closed）
        """
        self.path = str(path)
        # SQLite 无 MySQL 式 database 名；真实 schema 恒为 "main"（spec §5.3）。
        self.database = "main"
        self.history_max_records = validate_history_max_records(
            history_max_records, key="history_max_records"
        )
        self._governance_proof_verifier = governance_proof_verifier
        self.engine = None

    def connect(self) -> bool:
        """
        连接 SQLite 文件库并幂等初始化（应用表 DDL + schema 迁移 + fresh 种子）。

        Returns:
            bool: 连接是否成功
        """
        try:
            if self.engine is not None:
                self.engine.dispose()
            memory = self.path == ":memory:"
            if memory:
                db_url = "sqlite://"
                poolclass = StaticPool
            else:
                path = Path(self.path).expanduser().resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                db_url = f"sqlite:///{path}"
                poolclass = NullPool
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=poolclass,
                echo=False,
            )
            event.listen(self.engine, "connect", _enable_foreign_keys)
            # 验证连接，并在任何 DDL 之前快照已有表（种子门控依据）。
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                existing_tables = {
                    row[0]
                    for row in conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                }
            self._ensure_app_tables()
            self._migrate_history_schema()
            self._migrate_table_schema()
            self._ensure_app_indexes()
            self._load_seeds(existing_tables=existing_tables)
            logger.info(
                "SQLite 初始化成功：path_id={}, database={}",
                text_fingerprint(self.path),
                self.database,
            )
            return True
        except Exception as exc:
            log_safe_exception("sqlite_connect", exc)
            failed_engine = self.engine
            self.engine = None
            if failed_engine is not None:
                try:
                    failed_engine.dispose()
                except Exception as cleanup_exc:
                    log_safe_exception(
                        "sqlite_connect_cleanup", cleanup_exc, level="warning"
                    )
            return False

    def _ensure_app_tables(self) -> None:
        """幂等创建 6 应用表（canonical DDL 镜像 seed_history.sql）。"""
        for statement in _APP_TABLE_DDL:
            self.execute_update(statement, raise_on_error=True)

    def _ensure_app_indexes(self) -> None:
        """列迁移完成后幂等创建 12 条命名空间化索引（旧库缺列时先迁移再建索引）。"""
        for statement in _APP_INDEX_DDL:
            self.execute_update(statement, raise_on_error=True)

    def _load_seeds(self, *, existing_tables: set) -> None:
        """fresh-init-only 种子加载（显式 id INSERT 不可对已填充库重放）。

        - seed_history.sql：仅空库（初始化前无任何表）加载，忠实迁移 50 行历史。
        - seed_business.sql：仅 8 业务表全缺时加载（覆盖空库与仅有应用表的库）；
          部分业务表已存在则整体跳过，避免显式 id 主键冲突。
        """
        if not existing_tables:
            self._execute_seed_file(
                _SEED_DIR / "seed_history.sql", stage="sqlite_seed_history"
            )
        if not (existing_tables & _BUSINESS_TABLES):
            self._execute_seed_file(
                _SEED_DIR / "seed_business.sql", stage="sqlite_seed_business"
            )

    def _execute_seed_file(self, seed_path: Path, *, stage: str) -> None:
        if not seed_path.is_file():
            logger.warning("种子文件缺失，跳过初始化：stage={}", stage)
            return
        script = seed_path.read_text(encoding="utf-8")
        with self.get_connection() as conn:
            # executescript 用 SQLite 自身解析器处理多语句脚本（含字符串内分号）。
            dbapi_connection = conn.connection.dbapi_connection
            dbapi_connection.executescript(script)
        logger.info("种子初始化完成：stage={}", stage)

    def _migrate_history_schema(self) -> None:
        """Idempotently add governed-history identity columns to an existing table."""
        column_rows = self.execute_query(
            "PRAGMA table_info(sql_generation_history)", raise_on_error=True
        )
        existing_columns = {
            row.get("name") for row in column_rows if row.get("name")
        }
        for column_name, definition in _HISTORY_GOVERNANCE_COLUMNS:
            if column_name not in existing_columns:
                self._apply_history_schema_change(
                    "ALTER TABLE sql_generation_history "
                    f"ADD COLUMN {column_name} {definition}",
                )

        index_rows = self.execute_query(
            "PRAGMA index_list(sql_generation_history)", raise_on_error=True
        )
        existing_indexes = {
            row.get("name") for row in index_rows if row.get("name")
        }
        if _GOVERNED_FEW_SHOT_INDEX not in existing_indexes:
            self._apply_history_schema_change(
                "CREATE INDEX IF NOT EXISTS sql_generation_history_idx_governed_few_shot "
                "ON sql_generation_history "
                "(governance_validated, semantic_datasource, semantic_dialect, "
                "semantic_version, semantic_content_sha256, "
                "validation_status, execution_status, created_at)"
            )

    def _migrate_table_schema(self) -> None:
        """为已存在的 table_schema 表幂等补齐 properties 列（旧库缺该列会导致 upsert 静默失败）。"""
        column_rows = self.execute_query(
            "PRAGMA table_info(table_schema)", raise_on_error=True
        )
        existing_columns = {
            row.get("name") for row in column_rows if row.get("name")
        }
        if "properties" not in existing_columns:
            # SQLite ALTER ADD COLUMN 只能追加到末尾（MySQL 的 AFTER 仅影响列序，无语义）。
            self._apply_history_schema_change(
                "ALTER TABLE table_schema ADD COLUMN properties TEXT"
            )

    def _apply_history_schema_change(self, query: str) -> None:
        """Apply a migration DDL statement while tolerating only a concurrent winner."""
        try:
            self.execute_update(query, raise_on_error=True)
        except Exception as exc:
            duplicate = self._is_duplicate_schema_change(exc)
            log_safe_exception(
                "sqlite_history_schema_migration",
                exc,
                fingerprint_source=query,
                level="warning" if duplicate else "error",
            )
            if not duplicate:
                raise
            logger.info("历史治理迁移已由并发启动完成")

    @staticmethod
    def _is_duplicate_schema_change(error: Exception) -> bool:
        """Recognize SQLite's duplicate-column / duplicate-index error messages."""
        pending = [error]
        seen = set()
        while pending:
            current = pending.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            message = str(current).lower()
            if any(marker in message for marker in _DUPLICATE_SCHEMA_MARKERS):
                return True
            pending.extend(
                (
                    getattr(current, "orig", None),
                    getattr(current, "__cause__", None),
                    getattr(current, "__context__", None),
                )
            )
        return False

    def close(self):
        """关闭引擎（NullPool 下归还连接即关闭，dispose 释放引擎资源）"""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("SQLite 引擎已关闭")

    @contextmanager
    def get_connection(self):
        """
        获取数据库连接（上下文管理器）

        Yields:
            SQLAlchemy Connection
        """
        if not self.engine:
            logger.error("SQLite 未连接")
            raise RuntimeError("SQLite 未连接")

        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            log_safe_exception("sqlite_transaction", exc)
            try:
                conn.rollback()
            except Exception as rollback_exc:
                log_safe_exception(
                    "sqlite_transaction_rollback", rollback_exc, level="warning"
                )
            raise
        finally:
            conn.close()

    def execute_query(self, query: str, params: Optional[dict] = None,
                      raise_on_error: bool = False) -> List[Dict]:
        """
        执行查询

        Args:
            query: SQL 查询语句
            params: 查询参数（字典格式）
            raise_on_error: 失败时是否显式抛错

        Returns:
            List[Dict]: 查询结果
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result]
        except Exception as exc:
            log_safe_exception("sqlite_query", exc, fingerprint_source=query)
            if raise_on_error:
                raise
            return []

    def execute_query_limited(self, query: str, max_rows: int,
                              params: Optional[dict] = None, *,
                              timeout_ms: Optional[int] = None) -> tuple[List[Dict], bool]:
        """流式获取有限结果，避免将无界结果集一次性载入内存。

        超时看门狗（spec §5.1 Q4）：threading.Timer 到期调 Connection.interrupt，
        progress_handler 每 1000 个 VM opcode 复核 deadline 作同线程双保险；
        被取消的查询抛 QueryTimeoutExceeded（TimeoutError 子类）。
        LIMIT 注入仍由上游 constrain_read_query 完成（与 MySQL 路径一致）。
        """
        if max_rows <= 0:
            raise ValueError("max_rows 必须大于 0")
        budget_ms = self._resolve_query_timeout_ms(timeout_ms)
        with self.get_connection() as conn:
            dbapi_connection = conn.connection.dbapi_connection
            deadline = monotonic() + budget_ms / 1000
            watchdog = Timer(budget_ms / 1000, dbapi_connection.interrupt)
            watchdog.daemon = True
            dbapi_connection.set_progress_handler(
                lambda: 1 if monotonic() >= deadline else 0, 1000
            )
            watchdog.start()
            try:
                result = conn.execute(text(query), params or {})
                rows = result.mappings().fetchmany(max_rows + 1)
            except SQLAlchemyOperationalError as exc:
                message = str(getattr(exc, "orig", exc)).lower()
                if "interrupt" in message:
                    raise QueryTimeoutExceeded(
                        f"查询执行超过 {budget_ms}ms 超时预算，已被看门狗取消"
                    ) from exc
                raise
            finally:
                watchdog.cancel()
                dbapi_connection.set_progress_handler(None, 0)
            truncated = len(rows) > max_rows
            return [dict(row) for row in rows[:max_rows]], truncated

    def _resolve_query_timeout_ms(self, timeout_ms: Optional[int]) -> int:
        """显式 timeout_ms 优先；缺省惰性读取 config.SQL_QUERY_TIMEOUT_MS。"""
        if timeout_ms is not None:
            if (
                isinstance(timeout_ms, bool)
                or not isinstance(timeout_ms, int)
                or timeout_ms <= 0
            ):
                raise ValueError("timeout_ms 必须大于 0")
            return timeout_ms
        try:
            import config

            budget = int(config.SQL_QUERY_TIMEOUT_MS)
        except Exception:
            return _DEFAULT_QUERY_TIMEOUT_MS
        return budget if budget > 0 else _DEFAULT_QUERY_TIMEOUT_MS

    def explain_query(self, query: str, timeout_ms: int) -> List[Dict]:
        """Run EXPLAIN QUERY PLAN on a disposable checkout within a wall-clock deadline."""
        if timeout_ms <= 0:
            raise ValueError("timeout_ms 必须大于 0")

        statement = parse_one(query, read="sqlite")
        if not isinstance(statement, exp.Select):
            raise ValueError("仅支持 SELECT 预检")

        explain_sql = f"EXPLAIN QUERY PLAN {statement.sql(dialect='sqlite')}"
        if self.engine is None:
            raise RuntimeError("SQLite 未连接")

        def execute(cancelled) -> List[Dict]:
            conn = self.engine.connect()
            try:
                if cancelled.is_set():
                    raise ExplainDeadlineExceeded("EXPLAIN deadline exceeded")
                result = conn.execute(text(explain_sql))
                rows = [dict(row._mapping) for row in result]
                if cancelled.is_set():
                    raise ExplainDeadlineExceeded("EXPLAIN deadline exceeded")
                return rows
            finally:
                if cancelled.is_set():
                    try:
                        conn.invalidate()
                    except Exception as exc:
                        log_safe_exception(
                            "sqlite_explain_invalidate", exc, level="warning"
                        )
                conn.close()

        return run_with_wall_clock_deadline(execute, timeout_ms)

    def execute_update(self, query: str, params: Optional[dict] = None,
                       raise_on_error: bool = False) -> int:
        """
        执行更新操作

        Args:
            query: SQL 语句
            params: 参数（字典格式）
            raise_on_error: 失败时是否显式抛错

        Returns:
            int: 受影响的行数
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params or {})
                return result.rowcount
        except Exception as exc:
            log_safe_exception("sqlite_update", exc, fingerprint_source=query)
            if raise_on_error:
                raise
            return 0

    def upsert_table_schema(self, table_name: str, table_comment: str = "",
                           properties: Optional[Dict] = None) -> bool:
        """
        插入或更新表结构信息（ON DUPLICATE KEY → ON CONFLICT(table_name, database_name)）

        Args:
            table_name: 表名
            table_comment: 表注释
            properties: 额外属性

        Returns:
            bool: 是否成功
        """
        query = """
        INSERT INTO table_schema (table_name, table_comment, properties)
        VALUES (:table_name, :table_comment, :properties)
        ON CONFLICT(table_name, database_name) DO UPDATE SET
            table_comment = excluded.table_comment,
            properties = excluded.properties,
            updated_at = CURRENT_TIMESTAMP
        """
        params = {
            "table_name": table_name,
            "table_comment": table_comment,
            "properties": json.dumps(properties) if properties else None
        }
        # raise_on_error=True：写失败必须显式抛错，
        # 否则返回 0 会被 >= 0 吞掉，造成同步静默丢失
        result = self.execute_update(query, params, raise_on_error=True)
        return result >= 0

    def upsert_column_schema(self, table_name: str, column_name: str,
                            column_type: str = "VARCHAR", column_comment: str = "",
                            is_nullable: bool = True, is_primary_key: bool = False) -> bool:
        """
        插入或更新字段信息

        忠实 port 注记：canonical column_schema 除自增 PK 外无任何唯一键（与 MySQL
        活体库一致），MySQL 的 ON DUPLICATE KEY UPDATE 永不触发、实为纯插入；
        SQLite 侧以 ON CONFLICT(id) DO UPDATE 忠实对译（id 从不显式提供 → 亦纯插入）。
        不新增唯一约束（canonical DDL 冻结，Task 1 report §3）。

        Args:
            table_name: 表名
            column_name: 字段名
            column_type: 字段类型
            column_comment: 字段注释
            is_nullable: 是否可为空
            is_primary_key: 是否主键

        Returns:
            bool: 是否成功
        """
        # 先获取表 ID
        table_query = "SELECT id FROM table_schema WHERE table_name = :table_name"
        table_results = self.execute_query(table_query, {"table_name": table_name})

        if not table_results:
            logger.warning("表不存在：table_id={}", text_fingerprint(table_name))
            return False

        table_id = table_results[0]['id']

        query = """
        INSERT INTO column_schema (table_id, column_name, column_type, column_comment,
                                   is_nullable, is_primary_key)
        VALUES (:table_id, :column_name, :column_type, :column_comment, :is_nullable, :is_primary_key)
        ON CONFLICT(id) DO UPDATE SET
            column_type = excluded.column_type,
            column_comment = excluded.column_comment,
            is_nullable = excluded.is_nullable,
            is_primary_key = excluded.is_primary_key,
            updated_at = CURRENT_TIMESTAMP
        """
        params = {
            "table_id": table_id,
            "column_name": column_name,
            "column_type": column_type,
            "column_comment": column_comment,
            "is_nullable": 1 if is_nullable else 0,
            "is_primary_key": 1 if is_primary_key else 0
        }
        result = self.execute_update(query, params, raise_on_error=True)
        return result >= 0

    def save_sql_history(self, user_query: str, generated_sql: str,
                        session_id: Optional[str] = None,
                        matched_knowledge: Optional[List] = None,
                        retrieval_query: Optional[str] = None,
                        validation_status: str = "pending",
                        validation_error: Optional[str] = None,
                        *,
                        semantic_datasource: Optional[str] = None,
                        semantic_dialect: Optional[str] = None,
                        semantic_version: Optional[str] = None,
                        semantic_content_sha256: Optional[str] = None,
                        governance_validated: bool = False) -> Optional[int]:
        """
        保存 SQL 生成历史

        Args:
            user_query: 用户查询
            generated_sql: 生成的 SQL
            session_id: 会话 ID
            matched_knowledge: 匹配的知识
            retrieval_query: 检索查询
            validation_status: 验证状态
            validation_error: 验证错误

        Returns:
            Optional[int]: 插入的记录 ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        # This is the legacy/public writer. Persisted governance claims are audit
        # metadata issued by the governed pipeline, never caller assertions.
        semantic_datasource = None
        semantic_dialect = None
        semantic_version = None
        semantic_content_sha256 = None
        governance_validated = False
        self._validate_governance_identity(
            semantic_datasource=semantic_datasource,
            semantic_dialect=semantic_dialect,
            semantic_version=semantic_version,
            semantic_content_sha256=semantic_content_sha256,
            governance_validated=governance_validated,
        )

        query = """
        INSERT INTO sql_generation_history
        (session_id, user_query, generated_sql, matched_knowledge, retrieval_query,
         validation_status, validation_error, semantic_datasource, semantic_dialect,
         semantic_version, semantic_content_sha256, governance_validated)
        VALUES (:session_id, :user_query, :generated_sql, :matched_knowledge, :retrieval_query,
         :validation_status, :validation_error, :semantic_datasource, :semantic_dialect,
         :semantic_version, :semantic_content_sha256, :governance_validated)
        """
        params = {
            "session_id": session_id,
            "user_query": user_query,
            "generated_sql": generated_sql,
            "matched_knowledge": json.dumps(matched_knowledge, ensure_ascii=False) if matched_knowledge else None,
            "retrieval_query": retrieval_query,
            "validation_status": validation_status,
            "validation_error": validation_error,
            "semantic_datasource": semantic_datasource,
            "semantic_dialect": semantic_dialect,
            "semantic_version": semantic_version,
            "semantic_content_sha256": semantic_content_sha256,
            "governance_validated": governance_validated,
        }

        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params)
                history_id = result.lastrowid
                logger.info(f"保存 SQL 历史记录，ID={history_id}")
            self._prune_history()
            return history_id
        except Exception as exc:
            log_safe_exception(
                "sqlite_history_save", exc, fingerprint_source=generated_sql
            )
            return None

    def save_governed_sql_history(
        self,
        command: GovernedHistorySave,
        proof: HistoryMutationProof,
    ) -> Optional[int]:
        """Persist governed audit identity only with a matching one-use proof."""
        verifier = self._governance_proof_verifier
        if verifier is None or not verifier.consume(command, proof):
            logger.warning("governed_history_save_rejected reason=invalid_proof")
            return None
        self._validate_governance_identity(
            semantic_datasource=command.semantic_datasource,
            semantic_dialect=command.semantic_dialect,
            semantic_version=command.semantic_version,
            semantic_content_sha256=command.semantic_content_sha256,
            governance_validated=False,
        )
        params = {
            "session_id": command.session_id,
            "user_query": command.user_query,
            "generated_sql": command.generated_sql,
            "matched_knowledge": command.matched_knowledge_json,
            "retrieval_query": command.retrieval_query,
            "validation_status": command.validation_status,
            "validation_error": command.validation_error,
            "semantic_datasource": command.semantic_datasource,
            "semantic_dialect": command.semantic_dialect,
            "semantic_version": command.semantic_version,
            "semantic_content_sha256": command.semantic_content_sha256,
            "governance_validated": False,
        }
        query = """
        INSERT INTO sql_generation_history
        (session_id, user_query, generated_sql, matched_knowledge, retrieval_query,
         validation_status, validation_error, semantic_datasource, semantic_dialect,
         semantic_version, semantic_content_sha256, governance_validated)
        VALUES (:session_id, :user_query, :generated_sql, :matched_knowledge, :retrieval_query,
         :validation_status, :validation_error, :semantic_datasource, :semantic_dialect,
         :semantic_version, :semantic_content_sha256, :governance_validated)
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params)
                history_id = result.lastrowid
                logger.info("保存受治理 SQL 历史记录，ID={}", history_id)
            self._prune_history()
            return history_id
        except Exception as exc:
            log_safe_exception(
                "sqlite_governed_history_save",
                exc,
                fingerprint_source=command.generated_sql,
            )
            return None

    def finalize_governed_sql_execution(
        self,
        command: GovernedHistoryFinalization,
        proof: HistoryMutationProof,
    ) -> bool:
        """Consume proof and CAS one pending governed audit row to a final state."""
        verifier = self._governance_proof_verifier
        if verifier is None or not verifier.consume(command, proof):
            logger.warning("governed_history_update_rejected reason=invalid_proof")
            return False
        if command.execution_status not in {"success", "fail"}:
            return False
        self._validate_governance_identity(
            semantic_datasource=command.semantic_datasource,
            semantic_dialect=command.semantic_dialect,
            semantic_version=command.semantic_version,
            semantic_content_sha256=command.semantic_content_sha256,
            governance_validated=False,
        )
        governance_validated = command.execution_status == "success"
        query = """
        UPDATE sql_generation_history
        SET execution_status = :execution_status,
            execution_error = :execution_error,
            execution_result = :execution_result,
            governance_validated = :governance_validated,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = :history_id
          AND session_id = :session_id
          AND user_query = :user_query
          AND generated_sql = :generated_sql
          AND validation_status = 'success'
          AND execution_status = 'pending'
          AND governance_validated = 0
          AND semantic_datasource = :semantic_datasource
          AND semantic_dialect = :semantic_dialect
          AND semantic_version = :semantic_version
          AND semantic_content_sha256 = :semantic_content_sha256
        """
        params = {
            "history_id": command.history_id,
            "session_id": command.session_id,
            "user_query": command.user_query,
            "generated_sql": command.generated_sql,
            "execution_status": command.execution_status,
            "execution_error": command.execution_error,
            "execution_result": command.execution_result_json,
            "semantic_datasource": command.semantic_datasource,
            "semantic_dialect": command.semantic_dialect,
            "semantic_version": command.semantic_version,
            "semantic_content_sha256": command.semantic_content_sha256,
            "governance_validated": governance_validated,
        }
        try:
            return self.execute_update(query, params, raise_on_error=True) > 0
        except Exception as exc:
            log_safe_exception(
                "sqlite_governed_history_finalize",
                exc,
                fingerprint_source=command.generated_sql,
            )
            return False

    @staticmethod
    def _validate_governance_identity(
        *,
        semantic_datasource: Optional[str],
        semantic_dialect: Optional[str],
        semantic_version: Optional[str],
        semantic_content_sha256: Optional[str],
        governance_validated: bool,
    ) -> None:
        identity = (
            semantic_datasource,
            semantic_dialect,
            semantic_version,
            semantic_content_sha256,
        )
        if type(governance_validated) is not bool:
            raise ValueError("governance_validated must be a boolean")
        if all(value is None for value in identity):
            if governance_validated:
                raise ValueError("governed history requires a semantic identity")
            return
        if (
            not all(isinstance(value, str) and value for value in identity)
            or len(semantic_datasource or "") > 191
            or len(semantic_dialect or "") > 32
            or len(semantic_version or "") > 64
            or _SEMANTIC_CONTENT_SHA256.fullmatch(semantic_content_sha256 or "") is None
        ):
            raise ValueError("semantic history identity is invalid")

    def _prune_history(self) -> None:
        """保留最新的有限条历史，避免数据表无限增长。

        MySQL 多表 DELETE → SQLite 子查询（LIMIT 可用于子查询）；
        user_feedback 外键 ON DELETE CASCADE 随 PRAGMA foreign_keys=ON 自动级联。
        """
        self.execute_update(
            """
            DELETE FROM sql_generation_history
            WHERE id NOT IN (
                SELECT id FROM sql_generation_history
                ORDER BY created_at DESC, id DESC
                LIMIT :history_limit
            )
            """,
            {"history_limit": self.history_max_records},
        )

    def update_sql_execution(self, history_id: int, execution_status: str,
                            execution_error: Optional[str] = None,
                            execution_result: Optional[Any] = None,
                            session_id: Optional[str] = None,
                            generated_sql: Optional[str] = None,
                            require_validation_success: bool = False,
                            *,
                            expected_user_query: Optional[str] = None,
                            expected_semantic_datasource: Optional[str] = None,
                            expected_semantic_dialect: Optional[str] = None,
                            expected_semantic_version: Optional[str] = None,
                            expected_semantic_content_sha256: Optional[str] = None,
                            require_governance_validated: bool = False) -> bool:
        """
        更新 SQL 执行结果

        Args:
            history_id: 历史记录 ID
            execution_status: 执行状态
            execution_error: 执行错误
            execution_result: 执行结果

        Returns:
            bool: 是否成功
        """
        expected_identity = (
            expected_semantic_datasource,
            expected_semantic_dialect,
            expected_semantic_version,
            expected_semantic_content_sha256,
        )
        if require_governance_validated or any(
            value is not None for value in expected_identity
        ):
            logger.warning("legacy_history_update_rejected reason=governed_arguments")
            return False
        predicates = [
            "id = :history_id",
            "(governance_validated = 0 OR governance_validated IS NULL)",
            "semantic_datasource IS NULL",
            "semantic_dialect IS NULL",
            "semantic_version IS NULL",
            "semantic_content_sha256 IS NULL",
        ]
        if session_id is not None:
            predicates.append("session_id = :session_id")
        if generated_sql is not None:
            predicates.append("generated_sql = :generated_sql")
        if expected_user_query is not None:
            predicates.append("user_query = :expected_user_query")
        if require_validation_success:
            predicates.append("validation_status = 'success'")
        where_clause = " AND ".join(predicates)
        query = f"""
        UPDATE sql_generation_history
        SET execution_status = :execution_status,
            execution_error = :execution_error,
            execution_result = :execution_result,
            updated_at = CURRENT_TIMESTAMP
        WHERE {where_clause}
        """
        params = {
            "execution_status": execution_status,
            "execution_error": execution_error,
            "execution_result": json.dumps(execution_result, ensure_ascii=False, default=str)
            if execution_result is not None else None,
            "history_id": history_id,
        }
        if session_id is not None:
            params["session_id"] = session_id
        if generated_sql is not None:
            params["generated_sql"] = generated_sql
        if expected_user_query is not None:
            params["expected_user_query"] = expected_user_query
        result = self.execute_update(query, params, raise_on_error=True)
        return result > 0

    def get_history_list(self, session_id: Optional[str] = None,
                        limit: int = 50, offset: int = 0,
                        status_filter: Optional[str] = None) -> List[Dict]:
        """
        获取历史记录列表

        Args:
            session_id: 会话 ID 过滤
            limit: 限制数量
            offset: 偏移量
            status_filter: 状态过滤 (success/fail/pending)

        Returns:
            List[Dict]: 历史记录列表
        """
        conditions = []
        params = {}

        if session_id:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id

        if status_filter:
            conditions.append("execution_status = :status_filter")
            params["status_filter"] = status_filter

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT id, session_id, user_query, generated_sql, validation_status,
               execution_status, execution_error, execution_result, created_at
        FROM sql_generation_history
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset

        return self.execute_query(query, params)

    def get_successful_history_for_few_shot(
        self,
        limit: int = 100,
        *,
        semantic_datasource: Optional[str] = None,
        semantic_dialect: Optional[str] = None,
        semantic_version: Optional[str] = None,
        semantic_content_sha256: Optional[str] = None,
        governance_validated: Optional[bool] = None,
    ) -> List[Dict]:
        """
        获取成功的历史记录用于 Few-Shot 检索

        Args:
            limit: 限制数量

        Returns:
            List[Dict]: 成功历史记录列表
        """
        identity = (
            semantic_datasource,
            semantic_dialect,
            semantic_version,
            semantic_content_sha256,
        )
        governed = governance_validated is not None or any(
            value is not None for value in identity
        )
        conditions = [
            "validation_status = 'success'",
            "execution_status = 'success'",
        ]
        params = {"limit": limit}
        if governed:
            if governance_validated is not True:
                raise ValueError("governed Few-Shot retrieval requires validation")
            self._validate_governance_identity(
                semantic_datasource=semantic_datasource,
                semantic_dialect=semantic_dialect,
                semantic_version=semantic_version,
                semantic_content_sha256=semantic_content_sha256,
                governance_validated=True,
            )
            conditions.extend(
                (
                    "governance_validated = :governance_validated",
                    "semantic_datasource = :semantic_datasource",
                    "semantic_dialect = :semantic_dialect",
                    "semantic_version = :semantic_version",
                    "semantic_content_sha256 = :semantic_content_sha256",
                )
            )
            params.update(
                {
                    "semantic_datasource": semantic_datasource,
                    "semantic_dialect": semantic_dialect,
                    "semantic_version": semantic_version,
                    "semantic_content_sha256": semantic_content_sha256,
                    "governance_validated": True,
                }
            )
        where_clause = " AND ".join(conditions)
        query = f"""
        SELECT id, user_query, generated_sql, validation_status, execution_status,
               semantic_datasource, semantic_dialect, semantic_version,
               semantic_content_sha256, governance_validated
        FROM sql_generation_history
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
        """
        return self.execute_query(query, params)

    def get_history_detail(self, history_id: int) -> Optional[Dict]:
        """
        获取历史记录详情

        Args:
            history_id: 历史记录 ID

        Returns:
            Optional[Dict]: 历史记录详情
        """
        query = "SELECT * FROM sql_generation_history WHERE id = :history_id"
        results = self.execute_query(query, {"history_id": history_id})
        return results[0] if results else None

    def get_table_schema(self, table_name: Optional[str] = None) -> List[Dict]:
        """
        获取表结构信息（仅业务表，排除 6 应用表——spec §5.3 安全边界）。

        MySQL 版查 table_schema/column_schema 注册表；SQLite 单文件库改查
        sqlite_master + PRAGMA table_info（注册表已退化、全 0 行）。返回键形与
        MySQL 对齐：table_name/table_comment/properties/database_name/created_at/
        updated_at/columns（逗号拼接列名，按 ordinal 序，对应 GROUP_CONCAT ORDER BY cs.id）。
        SQLite 无表/列注释来源：table_comment 恒 ""、properties/时间戳恒 None。

        Args:
            table_name: 表名过滤

        Returns:
            List[Dict]: 表结构信息
        """
        rows = self.execute_query(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        names = [row["name"] for row in rows if row["name"] not in _APP_TABLES]
        if table_name:
            names = [name for name in names if name == table_name]
        schemas = []
        for name in names:
            columns = self._pragma_table_info(name)
            schemas.append(
                {
                    "id": None,
                    "table_name": name,
                    "table_comment": "",
                    "properties": None,
                    "database_name": self.database,
                    "created_at": None,
                    "updated_at": None,
                    "columns": ",".join(column["name"] for column in columns),
                }
            )
        return schemas

    def get_column_schema(self, table_name: str) -> List[Dict]:
        """
        获取字段信息（仅业务表；应用表/不存在表返回 []，与 get_table_schema 边界一致）。

        PRAGMA table_info → MySQL 注册表键形：column_name/column_type/is_nullable/
        is_primary_key/column_comment/default_value/table_name；id 取列 ordinal（cid），
        table_id/时间戳无注册表对应物恒 None。按 cid 序（对应 MySQL ORDER BY cs.id）。

        Args:
            table_name: 表名

        Returns:
            List[Dict]: 字段信息
        """
        if not table_name or table_name in _APP_TABLES:
            return []
        exists = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = :name",
            {"name": table_name},
        )
        if not exists:
            return []
        columns = self._pragma_table_info(table_name)
        return [
            {
                "id": column["cid"],
                "table_id": None,
                "column_name": column["name"],
                "column_type": column["type"],
                "is_nullable": 0 if column["notnull"] else 1,
                "is_primary_key": 1 if column["pk"] else 0,
                "column_comment": "",
                "default_value": column["dflt_value"],
                "created_at": None,
                "updated_at": None,
                "table_name": table_name,
            }
            for column in columns
        ]

    def _pragma_table_info(self, table_name: str) -> List[Dict]:
        """PRAGMA table_info（表名来自 sqlite_master 校验后的标识符，双引号转义）。"""
        quoted = table_name.replace('"', '""')
        return self.execute_query(f'PRAGMA table_info("{quoted}")')

    def get_statistics(self) -> Dict:
        """
        获取统计信息（合并为单次查询，减少数据库往返；SQLite 兼容直接 port）

        Returns:
            Dict: 统计数据
        """
        query = """
            SELECT
                (SELECT COUNT(*) FROM sql_generation_history) AS total_history,
                (SELECT CASE WHEN COUNT(*) = 0 THEN NULL
                        ELSE SUM(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                   END
                 FROM sql_generation_history WHERE execution_status != 'pending') AS success_rate,
                (SELECT AVG(feedback_score) FROM sql_generation_history WHERE feedback_score IS NOT NULL) AS avg_feedback_score,
                (SELECT COUNT(*) FROM table_schema) AS total_tables,
                (SELECT COUNT(*) FROM column_schema) AS total_columns
        """
        results = self.execute_query(query)
        if results:
            row = results[0]
            return {
                'total_history': row.get('total_history', 0),
                'success_rate': row.get('success_rate'),
                'avg_feedback_score': row.get('avg_feedback_score'),
                'total_tables': row.get('total_tables', 0),
                'total_columns': row.get('total_columns', 0),
            }
        return {}
