"""
活体数据库抽取器
"""
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from loguru import logger

from .base import BaseExtractor
from ..models import SchemaExtractResult, DatabaseIR, TableIR, ColumnIR, RelationshipIR


# 应用存储表（spec §5.3）：KG 只建模业务数据，不建模应用自身存储。
# 与 core/history/sqlite_client._APP_TABLES、config.SQL_BLOCKED_TABLES 默认名单对齐；
# SQLite 标识符 ASCII 大小写不敏感，排除前统一 lower() 归一。
_APP_TABLES = frozenset({
    "knowledge_metadata", "table_schema", "column_schema",
    "sql_generation_history", "retrieval_terms", "user_feedback",
})


class LiveDBExtractor(BaseExtractor):
    """活体数据库抽取器（支持 sqlite/mysql）"""

    def __init__(self, db_uri: str, db_type: str = "sqlite", schema: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.db_uri = db_uri
        self.db_type = db_type
        self.schema = schema
        self.engine = None

    def connect(self) -> bool:
        try:
            self.engine = create_engine(self.db_uri, pool_pre_ping=True)
            logger.info(f"成功连接到 {self.db_type} 数据库")
            return True
        except Exception as e:
            if self.engine is not None:
                self.engine.dispose()
                self.engine = None
            logger.error(f"数据库连接失败：{e}")
            return False

    def close(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def extract(self) -> SchemaExtractResult:
        if self.db_type not in ("mysql", "sqlite"):
            raise ValueError(f"活体数据库抽取暂不支持 {self.db_type}，当前支持 mysql/sqlite")

        if self.db_type == "sqlite":
            self._ensure_sqlite_file_exists()

        if not self.engine and not self.connect():
            raise ConnectionError(f"无法连接到 {self.db_type} 数据库")

        result = SchemaExtractResult()
        result.metadata["source_type"] = "live_db"

        # SQLite 单文件库的 schema 恒为 main（与 SQLiteClient.database 一致）；
        # MySQL 保持原有 default 占位（实际 schema 由 _extract_mysql 解析）。
        default_name = "main" if self.db_type == "sqlite" else "default"
        db = DatabaseIR(name=self.schema or default_name, db_type=self.db_type)
        result.databases.append(db)

        if self.db_type == "sqlite":
            self._extract_sqlite(result)
        else:
            self._extract_mysql(result)
            result.relationships = self._infer_relationships_from_schema(result)
        return result

    def _ensure_sqlite_file_exists(self):
        """文件型 SQLite URI 必须指向已存在的库文件。

        抽取是只读操作：缺文件时直接报错，避免连接时静默创建空库文件。
        :memory: 与 file: URI（如 file::memory:?uri=true）不做文件检查。
        """
        database = make_url(self.db_uri).database
        if not database or database == ":memory:" or database.startswith("file:"):
            return
        if not Path(database).is_file():
            raise FileNotFoundError(f"SQLite 数据库文件不存在：{database}")

    def _extract_sqlite(self, result: SchemaExtractResult):
        """SQLite 活体抽取：SQLAlchemy inspect 原生反射（sqlite_master/PRAGMA）。

        仅抽取业务表（排除 6 应用表，大小写归一）；SQLite 无表/列注释来源，
        description 留空。主键列强制 NOT NULL：INTEGER PRIMARY KEY 是 rowid 别名，
        PRAGMA notnull 可能为 0，但语义上不可空（与 MySQL IS_NULLABLE 对齐）。
        关系：优先采用声明的外键，其余沿用与 MySQL 一致的命名启发式推断。
        """
        inspector = inspect(self.engine)
        db_name = result.databases[0].name

        table_names = [n for n in inspector.get_table_names() if n.lower() not in _APP_TABLES]
        for table_name in table_names:
            pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
            table = TableIR(name=table_name, database=db_name)
            for col in inspector.get_columns(table_name):
                is_pk = col["name"] in pk_cols
                table.columns.append(ColumnIR(
                    name=col["name"],
                    data_type=str(col["type"]).split("(")[0].strip().upper(),
                    is_nullable=False if is_pk else bool(col.get("nullable", True)),
                    is_primary_key=is_pk,
                ))
            result.tables.append(table)

        fk_relationships = self._sqlite_fk_relationships(inspector, result)
        inferred = self._infer_relationships_from_schema(result)
        # 声明外键是其源列的权威关系；启发式只补充没有声明外键的列
        fk_columns = {(r.from_table, r.from_column) for r in fk_relationships}
        result.relationships = fk_relationships + [
            r for r in inferred if (r.from_table, r.from_column) not in fk_columns
        ]

    def _sqlite_fk_relationships(self, inspector, result: SchemaExtractResult):
        """声明外键 → RelationshipIR；仅保留指向已抽取业务表的外键（排除应用表/自环）。"""
        db_name = result.databases[0].name
        extracted = {t.name.lower(): t for t in result.tables}
        relationships = []
        for table in result.tables:
            for fk in inspector.get_foreign_keys(table.name):
                referred = fk.get("referred_table")
                if not referred or referred.lower() == table.name.lower():
                    continue
                target = extracted.get(referred.lower())
                if target is None:  # 指向应用表或未抽取的表
                    continue
                constrained = fk.get("constrained_columns") or []
                # SQLite 允许省略被引用列（默认指向对方主键）
                referred_cols = fk.get("referred_columns") or [
                    c.name for c in target.columns if c.is_primary_key
                ]
                for from_col, to_col in zip(constrained, referred_cols):
                    relationships.append(RelationshipIR(
                        from_database=db_name,
                        from_table=table.name,
                        from_column=from_col,
                        to_database=db_name,
                        to_table=target.name,
                        to_column=to_col,
                        relationship_type="foreign_key",
                        join_type="LEFT JOIN",
                    ))
        return relationships

    def _extract_mysql(self, result: SchemaExtractResult):
        with self.engine.connect() as conn:
            schema_name = self.schema
            if not schema_name:
                schema_name = conn.execute(text("SELECT DATABASE()")).scalar()
            if not schema_name:
                raise ValueError("未指定 MySQL schema，且连接未选择默认数据库")

            tables = conn.execute(text("""
                SELECT TABLE_NAME, TABLE_COMMENT, TABLE_SCHEMA
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = :schema_name
            """), {"schema_name": schema_name}).fetchall()

            for row in tables:
                table = TableIR(name=row[0], database=row[2], description=row[1])
                result.tables.append(table)

            columns = conn.execute(text("""
                SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, IS_NULLABLE, COLUMN_KEY, TABLE_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :schema_name
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """), {"schema_name": schema_name}).fetchall()

            for row in columns:
                table = next((t for t in result.tables if t.name == row[5]), None)
                if table:
                    column = ColumnIR(
                        name=row[0], data_type=row[1].split('(')[0],
                        description=row[2], is_nullable=row[3] == 'YES',
                        is_primary_key=row[4] == 'PRI'
                    )
                    table.columns.append(column)
