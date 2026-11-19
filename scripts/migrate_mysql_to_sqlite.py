"""MySQL → SQLite 一次性迁移：只读 introspect 源库，生成 SQLite 种子文件。

历史工具（迁移已完成，种子已提交入库）：应用运行时不再依赖 MySQL；
mysql-connector-python 已从 requirements.txt 移除，如需对源库重跑本脚本，
须先手工安装该连接器（pip install mysql-connector-python==8.2.0）。

用法（源 MySQL 需在运行，连接取自项目根 .env 的 MYSQL_*）：
    .venv/bin/python scripts/migrate_mysql_to_sqlite.py

产出（提交入库的部署种子，供 SQLiteClient 首次初始化）：
    data/seed_business.sql  —— 8 业务表 DDL + 数据
    data/seed_history.sql   —— 6 应用表 DDL + sql_generation_history 历史

保证：
    * 只读：对 MySQL 仅 inspect / SELECT，绝不写入。
    * 幂等可重跑：表/列/行/索引顺序固定，文件头不含时间戳，
      源数据不变时重复运行产出字节一致的文件。
    * 索引名按表命名空间化（<table>_<源索引名>）：SQLite 索引名全库唯一，
      MySQL 索引名按表唯一；跨表同名索引（如 idx_account_no）若直接沿用，
      CREATE INDEX IF NOT EXISTS 会静默丢弃后者。
    * 行数对账：生成后自动把种子加载进 sqlite3 :memory:，逐表 COUNT==源，
      不一致则非零退出。

类型映射（spec §5.1）：
    BIGINT/INT/TINYINT（含 unsigned/显示宽度）→ INTEGER
    自增整型单列主键                        → INTEGER PRIMARY KEY AUTOINCREMENT
    VARCHAR/CHAR/TEXT/JSON                  → TEXT（去 COLLATE）
    DECIMAL                                 → NUMERIC
    DATETIME/TIMESTAMP/DATE                 → TEXT（ISO 文本）
    FLOAT/DOUBLE                            → REAL
    去 ENGINE/MySQL COMMENT；ON UPDATE CURRENT_TIMESTAMP 去除
    （应用层 UPDATE 已显式置 updated_at=CURRENT_TIMESTAMP，行为不变）。

数据忠实：显式保留源主键（含空洞）；sql_generation_history.sql_dialect
DDL 默认值改为 'sqlite'（新行默认，spec §5.4），但迁移旧行保留源值 'mysql'。
"""
import json
import re
import sqlite3
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SEED_BUSINESS_PATH = DATA_DIR / "seed_business.sql"
SEED_HISTORY_PATH = DATA_DIR / "seed_history.sql"

# 应用表固定输出顺序：sql_generation_history 必须先于 user_feedback（外键依赖），
# 其余与原 MySQL 客户端管理表 DDL 顺序一致。Task 2 的内联 DDL 以
# data/seed_history.sql 为规范（canonical）镜像。
APP_TABLE_ORDER = (
    "sql_generation_history",
    "user_feedback",
    "table_schema",
    "column_schema",
    "knowledge_metadata",
    "retrieval_terms",
)
APP_TABLES = frozenset(APP_TABLE_ORDER)

# spec §5.1 类型映射（按 MySQL COLUMN_TYPE 的基础类型词）
TYPE_MAP = {
    "bigint": "INTEGER", "int": "INTEGER", "integer": "INTEGER",
    "tinyint": "INTEGER", "smallint": "INTEGER", "mediumint": "INTEGER",
    "varchar": "TEXT", "char": "TEXT", "text": "TEXT", "tinytext": "TEXT",
    "mediumtext": "TEXT", "longtext": "TEXT", "json": "TEXT",
    "enum": "TEXT", "set": "TEXT",
    "decimal": "NUMERIC", "numeric": "NUMERIC",
    "datetime": "TEXT", "timestamp": "TEXT", "date": "TEXT", "time": "TEXT",
    "float": "REAL", "double": "REAL", "real": "REAL",
    "blob": "BLOB", "tinyblob": "BLOB", "mediumblob": "BLOB", "longblob": "BLOB",
    "binary": "BLOB", "varbinary": "BLOB",
}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMERIC_DEFAULT_RE = re.compile(r"^-?\d+(\.\d+)?$")


class MigrationError(RuntimeError):
    """迁移过程中的结构性错误（未知类型/非法默认值/对账失败）。"""


def load_env(path: Path) -> dict:
    """解析 .env（K=V，忽略注释/空行，去除成对引号）。"""
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def mysql_url(env: dict) -> str:
    return (
        f"mysql+mysqlconnector://{env['MYSQL_USER']}:{env['MYSQL_PASSWORD']}"
        f"@{env['MYSQL_HOST']}:{env['MYSQL_PORT']}/{env['MYSQL_DATABASE']}"
    )


def ident(name: str) -> str:
    """标识符安全引用（源库均为常规标识符，异常时双引号兜底）。"""
    if _IDENT_RE.match(name):
        return name
    return '"' + name.replace('"', '""') + '"'


def sql_quote(value: str) -> str:
    if "\x00" in value:
        raise MigrationError("字符串含 NUL，SQLite 文本无法忠实承载")
    return "'" + value.replace("'", "''") + "'"


def map_type(column_type_raw: str) -> str:
    base = re.match(r"[a-z]+", column_type_raw.lower())
    if not base or base.group(0) not in TYPE_MAP:
        raise MigrationError(f"未知 MySQL 类型: {column_type_raw!r}")
    return TYPE_MAP[base.group(0)]


def render_default(table: str, column: str, sqlite_type: str, raw) -> str | None:
    """MySQL COLUMN_DEFAULT（information_schema 原值）→ SQLite DEFAULT 子句。"""
    if table == "sql_generation_history" and column == "sql_dialect":
        return "'sqlite'"  # 新行默认方言（spec §5.4）；旧行数据仍忠实保留
    if raw is None:
        return None
    if str(raw).upper() == "CURRENT_TIMESTAMP":
        return "CURRENT_TIMESTAMP"
    if sqlite_type == "TEXT":
        return sql_quote(str(raw))
    if _NUMERIC_DEFAULT_RE.match(str(raw)):
        return str(raw)
    raise MigrationError(f"{table}.{column}: 无法映射默认值 {raw!r}")


def sql_literal(value) -> str:
    """Python 驱动值 → SQLite SQL 字面量（忠实、可确定性复现）。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return sql_quote(value.isoformat(sep=" "))
    if isinstance(value, (date, time)):
        return sql_quote(value.isoformat())
    if isinstance(value, (bytes, bytearray)):
        return "X'" + value.hex() + "'"
    if isinstance(value, str):
        return sql_quote(value)
    if isinstance(value, (dict, list)):
        return sql_quote(json.dumps(value, ensure_ascii=False, sort_keys=True))
    raise MigrationError(f"无法序列化的值类型: {type(value)!r}")


def collect_source(engine) -> dict:
    """只读 introspect + SELECT，采集 14 表结构与全部行（固定顺序）。"""
    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    business = [t for t in tables if t not in APP_TABLES]
    app = [t for t in APP_TABLE_ORDER if t in tables]
    missing = APP_TABLES - set(tables)
    if missing:
        raise MigrationError(f"源库缺少应用表: {sorted(missing)}")

    source = {}
    with engine.connect() as conn:
        raw_meta = {}
        rows = conn.execute(text(
            "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, EXTRA "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :db "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        ), {"db": engine.url.database}).mappings().all()
        for r in rows:
            raw_meta.setdefault(r["TABLE_NAME"], {})[r["COLUMN_NAME"]] = dict(r)

        for table in business + app:
            columns = []
            for c in insp.get_columns(table):
                meta = raw_meta.get(table, {}).get(c["name"], {})
                columns.append({
                    "name": c["name"],
                    "sqlite_type": map_type(meta.get("COLUMN_TYPE") or str(c["type"])),
                    "nullable": c["nullable"],
                    "default_raw": meta.get("COLUMN_DEFAULT"),
                    "autoincrement": bool(c.get("autoincrement")),
                })
            pk = insp.get_pk_constraint(table)["constrained_columns"]
            col_names = [c["name"] for c in columns]
            select_cols = ", ".join(ident(n) for n in col_names)
            order_by = ", ".join(ident(n) for n in (pk or col_names))
            data = conn.execute(text(
                f"SELECT {select_cols} FROM {ident(table)} ORDER BY {order_by}"
            )).all()
            source[table] = {
                "kind": "APP" if table in APP_TABLES else "BUSINESS",
                "columns": columns,
                "pk": pk,
                "uniques": sorted(insp.get_unique_constraints(table),
                                  key=lambda u: u["name"] or ""),
                "indexes": sorted(insp.get_indexes(table), key=lambda i: i["name"] or ""),
                "fks": insp.get_foreign_keys(table),
                "comment": insp.get_table_comment(table).get("text"),
                "rows": [tuple(r) for r in data],
            }
    return source


def render_table_ddl(table: str, info: dict) -> str:
    pk = info["pk"]
    single_auto_pk = (
        len(pk) == 1 and info["columns"]
        and info["columns"][0]["name"] == pk[0]
        and info["columns"][0]["sqlite_type"] == "INTEGER"
        and info["columns"][0]["autoincrement"]
    )
    lines = []
    for col in info["columns"]:
        if single_auto_pk and col["name"] == pk[0]:
            lines.append(f"    {ident(col['name'])} INTEGER PRIMARY KEY AUTOINCREMENT")
            continue
        parts = [ident(col["name"]), col["sqlite_type"]]
        if not col["nullable"]:
            parts.append("NOT NULL")
        default = render_default(table, col["name"], col["sqlite_type"], col["default_raw"])
        if default is not None:
            parts.append(f"DEFAULT {default}")
        if len(pk) == 1 and col["name"] == pk[0]:
            parts.append("PRIMARY KEY")
        lines.append("    " + " ".join(parts))
    if len(pk) > 1:
        lines.append("    PRIMARY KEY (" + ", ".join(ident(c) for c in pk) + ")")
    for uq in info["uniques"]:
        cols = ", ".join(ident(c) for c in uq["column_names"])
        if uq["name"]:
            lines.append(f"    CONSTRAINT {ident(uq['name'])} UNIQUE ({cols})")
        else:
            lines.append(f"    UNIQUE ({cols})")
    for fk in info["fks"]:
        cols = ", ".join(ident(c) for c in fk["constrained_columns"])
        ref_cols = ", ".join(ident(c) for c in fk["referred_columns"])
        clause = f"    FOREIGN KEY ({cols}) REFERENCES {ident(fk['referred_table'])} ({ref_cols})"
        if fk.get("options", {}).get("ondelete"):
            clause += f" ON DELETE {fk['options']['ondelete']}"
        if fk.get("options", {}).get("onupdate"):
            clause += f" ON UPDATE {fk['options']['onupdate']}"
        lines.append(clause)
    return f"CREATE TABLE IF NOT EXISTS {ident(table)} (\n" + ",\n".join(lines) + "\n);"


def index_name(table: str, source_name: str) -> str:
    """SQLite 索引名全库唯一 → 按表命名空间化，杜绝跨表同名碰撞。"""
    return f"{table}_{source_name}"


def expected_index_inventory(source: dict) -> dict:
    """源非唯一索引的期望清单：{命名空间化索引名: (表, 列)}。"""
    expected = {}
    for table, info in source.items():
        unique_names = {u["name"] for u in info["uniques"]}
        for idx in info["indexes"]:
            if idx["name"] in unique_names:
                continue  # 唯一约束已承载（sqlite_autoindex_*），不计入显式索引
            expected[index_name(table, idx["name"])] = (table, list(idx["column_names"]))
    return expected


def render_index_ddl(table: str, info: dict) -> list:
    unique_names = {u["name"] for u in info["uniques"]}
    statements = []
    for idx in info["indexes"]:
        if idx["name"] in unique_names:
            continue  # 唯一约束已承载，避免重复索引
        cols = ", ".join(ident(c) for c in idx["column_names"])
        name = ident(index_name(table, idx["name"]))
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {name} ON {ident(table)} ({cols});"
        )
    return statements


def render_inserts(table: str, info: dict) -> list:
    col_names = ", ".join(ident(c["name"]) for c in info["columns"])
    statements = []
    for row in info["rows"]:
        values = ", ".join(sql_literal(v) for v in row)
        statements.append(f"INSERT INTO {ident(table)} ({col_names}) VALUES ({values});")
    return statements


def render_seed(source: dict, tables: list, title: str, extra_notes: str = "") -> str:
    total_rows = sum(len(source[t]["rows"]) for t in tables)
    header = (
        "-- ============================================================\n"
        f"-- {title}（{len(tables)} 表，{total_rows} 行）\n"
        "-- 源：MySQL business_db（只读迁移）。\n"
        "-- 由 scripts/migrate_mysql_to_sqlite.py 生成；请勿手工编辑，重跑脚本可再生成。\n"
        "-- 类型映射（spec §5.1）：INTEGER/TEXT/NUMERIC/REAL；去 COLLATE/ENGINE/COMMENT。\n"
    )
    if extra_notes:
        header += extra_notes
    header += "-- ============================================================\n"
    blocks = [header]
    for table in tables:
        info = source[table]
        comment = f" — {info['comment']}" if info["comment"] else ""
        block = [
            "-- ------------------------------------------------------------\n"
            f"-- {table}{comment}（{len(info['rows'])} 行）\n"
            "-- ------------------------------------------------------------"
        ]
        block.append(render_table_ddl(table, info))
        block.extend(render_index_ddl(table, info))
        block.extend(render_inserts(table, info))
        blocks.append("\n".join(block))
    return "\n\n".join(blocks) + "\n"


def verify_seeds(source: dict, business_sql: str, history_sql: str) -> list:
    """把种子加载进 :memory:，逐表 COUNT 对账源行数 + 全量索引清单对账。"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(business_sql)
        conn.executescript(history_sql)
        seeded = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if seeded != set(source):
            raise MigrationError(f"种子表集合不一致: {sorted(seeded ^ set(source))}")
        results = []
        for table, info in source.items():
            seed_count = conn.execute(f"SELECT COUNT(*) FROM {ident(table)}").fetchone()[0]
            src_count = len(info["rows"])
            if seed_count != src_count:
                raise MigrationError(f"{table}: 种子 {seed_count} 行 != 源 {src_count} 行")
            results.append((table, info["kind"], src_count, seed_count))

        # 索引全量对账：声明 vs 实际（防全局索引名碰撞被 IF NOT EXISTS 静默吞掉）
        expected = expected_index_inventory(source)
        actual = {}
        for table in source:
            for row in conn.execute(f"PRAGMA index_list({ident(table)})"):
                # row=(seq, name, unique, origin, partial)；origin 'c'=CREATE INDEX，
                # 'u'/'pk' 为 UNIQUE/PRIMARY KEY 自动索引，不在显式清单内
                if row[3] != "c":
                    continue
                cols = [r[2] for r in conn.execute(f"PRAGMA index_info({ident(row[1])})")]
                actual[row[1]] = (table, cols)
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            mismatch = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
            raise MigrationError(
                f"索引清单不一致: 缺失={missing} 多余={extra} 表/列不符={mismatch}"
            )
        return results
    finally:
        conn.close()


def main() -> int:
    env = load_env(PROJECT_ROOT / ".env")
    engine = create_engine(mysql_url(env))
    try:
        source = collect_source(engine)  # 只读：inspect + SELECT
    finally:
        engine.dispose()

    business_tables = [t for t in source if source[t]["kind"] == "BUSINESS"]
    app_tables = [t for t in APP_TABLE_ORDER if t in source]
    history_notes = (
        "-- 注：sql_generation_history.sql_dialect 新行默认 'sqlite'（spec §5.4），\n"
        "--     迁移旧行忠实保留源值 'mysql'。\n"
        "-- 注：ON UPDATE CURRENT_TIMESTAMP 已去除；应用层 UPDATE 显式置\n"
        "--     updated_at=CURRENT_TIMESTAMP（行为不变）。\n"
    )
    business_sql = render_seed(source, business_tables, "seed_business.sql — 业务表种子")
    history_sql = render_seed(source, app_tables, "seed_history.sql — 应用表种子", history_notes)

    results = verify_seeds(source, business_sql, history_sql)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEED_BUSINESS_PATH.write_text(business_sql, encoding="utf-8", newline="\n")
    SEED_HISTORY_PATH.write_text(history_sql, encoding="utf-8", newline="\n")

    print(f"源库: {env['MYSQL_DATABASE']}（只读） → 种子对账通过")
    for table, kind, src_count, seed_count in results:
        print(f"  [{kind}] {table}: 源={src_count} 种子={seed_count} OK")
    biz_total = sum(r[2] for r in results if r[1] == "BUSINESS")
    hist_total = len(source["sql_generation_history"]["rows"])
    print(f"业务表合计 {biz_total} 行；历史 {hist_total} 行")
    print(f"已写入: {SEED_BUSINESS_PATH}")
    print(f"已写入: {SEED_HISTORY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
