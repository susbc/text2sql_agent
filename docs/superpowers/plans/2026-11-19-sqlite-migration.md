# MySQL → SQLite 彻底迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底去掉本地 MySQL 服务依赖——应用存储、知识元数据、生成 SQL 的执行全部落到嵌入式 SQLite 文件库；迁移现有数据；Neo4j Database 元数据如实反映 SQLite；语义治理保持 mysql-only 休眠。

**Architecture:** drop-in SQLiteClient 沿用 MySQLClient 公开接口（SQLAlchemy-SQLite 引擎），上游 generator/app_context/UI/测试改动最小。单文件 data/text2sql.db（应用表+业务表同库）。一次性迁移脚本生成入库种子。默认方言 SQLite，KG 构建器改从 SQLite 抽取重建图谱元数据。

**Tech Stack:** Python 3.12（.venv：pytest 7.4.3 / ruff 0.15.20 / streamlit 1.29.0 / SQLAlchemy 2.0.48 / sqlglot / sqlfluff）、SQLite（stdlib + SQLAlchemy sqlite 方言）、Neo4j（保留）。

**Spec:** `docs/superpowers/specs/2026-11-19-sqlite-migration-design.md`（权威，含 §5 翻译细节与 §8 裁决）

## Global Constraints

- 基线：当前 main `.venv/bin/python -m pytest tests -q` → **938 passed, 14 skipped, 0 failed**；ruff check . 零告警。每任务结束跑全量，既有覆盖不丢（适配而非删除测试）。
- 彻底去 MySQL：完成后 requirements 无 mysql-connector-python，代码无 mysql 服务连接残留（mysql_client.py 删除）。
- 迁移数据保真：逐表行数对账==源（业务 8 表 31 行、历史 50 行）；DECIMAL→NUMERIC 浮点亲和接受，对账以行数为准。
- 安全边界：get_table_schema 仅返回业务表；6 张应用表（knowledge_metadata/table_schema/column_schema/sql_generation_history/retrieval_terms/user_feedback）入 SQL_BLOCKED_TABLES；生成 SQL 不得查应用表。
- 语义治理/EXPLAIN 内核保持 mysql-only（Literal["mysql"] pin、default.yaml、golden、config_validation 闸门不动）；SQLite 下休眠，UI 注明仅 MySQL。不扩展内核。
- Neo4j 检索链路结构/算法不动；仅 Database 节点 db_type 随实际配置库更新为 sqlite。
- few-shot 加方言过滤（明确豁免"不动检索"，仅此过滤）：新行 sql_dialect 默认 sqlite，旧 mysql 行不注入 SQLite 提示。
- 执行超时 SQL_QUERY_TIMEOUT_MS 用 sqlite3 interrupt 看门狗保留（不静默失效）。
- 时序：先迁移（源 MySQL 在跑、.env 已授权只读）→验证→最后去 mysql-connector。
- 隔离 worktree 执行（保护 8501）；worktree 内 cp 主仓 .env；用主仓 .venv/bin/python 绝对路径。8501 不动；冒烟 8502 用后即停。
- 提交：中文 conventional commits + Co-Authored-By: Claude Code <noreply@anthropic.com>。
- 行号为快照，按函数名/section 标记定位。

## Review Focus

1. **迁移数据保真**：行数对账 + 抽样值比对（货币列 NUMERIC）→ T1 对账测试。
2. **安全边界放宽**：应用表被生成 SQL 查询 → T4 安全测试（应用表拒绝、业务表放行、schema 限定）。
3. **方言不一致**：生成 MySQL SQL 却在 SQLite 执行 → T3/T4 端到端冒烟（Neo4j db_type=sqlite + 默认 dialect）。
4. **超时静默失效**：SQLite 无 MAX_EXECUTION_TIME → T2 看门狗测试（慢查询被 interrupt）。
5. **few-shot 污染**：旧 mysql 历史注入 SQLite 提示 → T5 过滤测试。

---

### Task 1: 迁移脚本 + 种子文件 + 行数对账

**Files:**
- Create: `scripts/migrate_mysql_to_sqlite.py`、`data/seed_business.sql`（8 业务表 DDL+31 行）、`data/seed_history.sql`（6 应用表 DDL+50 行历史）、`tests/test_migration_reconciliation.py`
- 源：只读连 MySQL business_db（.env）

**Interfaces:**
- Produces: 种子 SQL 文件（SQLite DDL+INSERT，供 T2 SQLiteClient 首次初始化）；迁移脚本 `main()` 可重跑幂等。
- Consumes: .env MYSQL_*（源连接）；schema 类型映射按 spec §5.1。

- [ ] **Step 1: 写迁移脚本**

只读 introspect 源 MySQL 14 表（sqlalchemy inspect）；按 spec §5.1 类型映射生成 SQLite DDL（INTEGER PRIMARY KEY AUTOINCREMENT、TEXT/NUMERIC/INTEGER、去 COLLATE/ENGINE）；导出业务表 31 行 + sql_generation_history 50 行为 INSERT（参数化/转义）；写 data/seed_business.sql + data/seed_history.sql。脚本打印逐表行数。

- [ ] **Step 2: 写对账测试（先失败）**

```python
# tests/test_migration_reconciliation.py
def test_seed_row_counts_match_source():
    # 用 sqlite3 内存库执行种子文件，逐表 COUNT 断言：
    # users=12, transaction_record=8, user_account=6, risk_blacklist=3,
    # prediction_results=1, account_freeze_log=0, daily_account_check=0,
    # fee_rate_config=0, sql_generation_history=50, 其余应用表=0
    ...
def test_seed_business_schema_types():
    # PRAGMA table_info(users) 含 id INTEGER PK；货币列 NUMERIC 亲和
    ...
```

- [ ] **Step 3: 跑测试确认失败→运行迁移脚本生成种子→跑测试确认通过**

Run: `.venv/bin/python scripts/migrate_mysql_to_sqlite.py`（源 MySQL 在跑）
Run: `.venv/bin/python -m pytest tests/test_migration_reconciliation.py -q` → PASS

- [ ] **Step 4: 全量回归 + Commit**

Run: `.venv/bin/python -m pytest tests -q` → 938+新增 passed, 14 skipped。
```bash
git add scripts/migrate_mysql_to_sqlite.py data/seed_business.sql data/seed_history.sql tests/test_migration_reconciliation.py
git commit -m "feat: MySQL→SQLite 迁移脚本与种子数据（行数对账）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: SQLiteClient（完整接口）+ 单测

**Files:**
- Create: `core/history/sqlite_client.py`、`tests/test_sqlite_client.py`
- 参照: `core/history/mysql_client.py`（逐方法 port，签名不变）

**Interfaces:**
- Produces: `SQLiteClient(path: str, *, history_max_records: int = 1000, governance_proof_verifier=None)`，公开方法与 MySQLClient 同名同签名：connect()->bool / close() / get_connection() / execute_query(query, params=None, ...)->List[Dict] / execute_query_limited(query, max_rows, ...)->(List[Dict], bool) / explain_query(query, timeout_ms)->List[Dict] / execute_update(query, params=None, ...)->int / upsert_table_schema(...) / upsert_column_schema(...) / save_sql_history(user_query, generated_sql, session_id=None, matched_knowledge=None, retrieval_query=None, validation_status="pending", validation_error=None, *, ...)->int / save_governed_sql_history(command, proof)->int / finalize_governed_sql_execution(command, proof) / update_sql_execution(history_id, execution_status, ...) / get_history_list(session_id=None, ...) / get_successful_history_for_few_shot(limit=100, *, semantic_datasource=None, semantic_dialect=None, semantic_version=None) / get_history_detail(history_id) / get_table_schema(table_name=None) / get_column_schema(table_name) / get_statistics()->Dict。属性 `database`（SQLite 返回 "main" 或文件名 stem，供 allowed_schemas）。
- Consumes: T1 种子文件（connect 时库不存在→幂等初始化）。

- [ ] **Step 1: 写单测（先失败）**

覆盖：connect 幂等建表+种子初始化；execute_query/execute_update 命名参数；execute_query_limited LIMIT 注入+truncated 标志；upsert ON CONFLICT；save_sql_history/get_history_list/get_history_detail 往返；get_statistics 计数；explain_query 返回 EXPLAIN QUERY PLAN 行；**超时看门狗**（注册慢函数或大递归 CTE，timeout_ms 小→抛超时/被 interrupt）；get_table_schema 仅业务表（排除应用表）。用临时文件库 fixture。

- [ ] **Step 2: 实现 SQLiteClient**

SQLAlchemy `create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})`；PRAGMA foreign_keys=ON。逐方法 port mysql_client，翻译 spec §5.1 所列 MySQL-isms：DDL AUTO_INCREMENT→AUTOINCREMENT；ON DUPLICATE KEY→ON CONFLICT DO UPDATE；_migrate_*_schema 的 information_schema→PRAGMA table_info + ALTER TABLE ADD COLUMN；GROUP_CONCAT(... ORDER BY)→SQLite group_concat（有序需子查询）；_prune_history 多表 DELETE→子查询；NOW()→CURRENT_TIMESTAMP；sql_dialect 列默认 'sqlite'。explain_query→EXPLAIN QUERY PLAN（sqlglot dialect='sqlite'）。execute_query_limited 用 sqlite3 progress_handler/interrupt 看门狗实现 timeout_ms（spec §5.1 Q4）。get_table_schema 查 sqlite_master 业务表（排除 6 应用表）+ PRAGMA table_info 列。get_statistics 子 select COUNT/CASE 直接 port。

- [ ] **Step 3: 跑单测确认通过 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_sqlite_client.py -q` → PASS
Run: `.venv/bin/python -m pytest tests -q` → 既有 938 不变 + 新增。

- [ ] **Step 4: Commit**

```bash
git add core/history/sqlite_client.py tests/test_sqlite_client.py
git commit -m "feat: SQLiteClient 存储后端（沿用 MySQLClient 接口 + 超时看门狗）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 配置 + wiring 切换（db_client 更名，默认 dialect sqlite）

**Files:**
- Modify: `config.py`（MYSQL_*→SQLITE_PATH，去池参数，SQL_DIALECT 默认 sqlite）、`core/config_validation.py`（mysql_* 键→sqlite_path；治理 mysql-only 闸门保留）、`app/bootstrap.py`（config dict 键）、`core/app_context.py`（MySQLClient→SQLiteClient，property mysql_client→db_client，_mysql_client→_db_client，sql_dialect 默认 sqlite 各处 :386/407/660/767/770/1028）、`core/sql/generator.py`（self.mysql_client→self.db_client 引用）
- 适配: 直接耦合 mysql_client 的测试

**Interfaces:**
- Produces: `ApplicationContext.db_client` property（SQLiteClient）；config `SQLITE_PATH`（默认 data/text2sql.db）、`SQL_DIALECT` 默认 "sqlite"。
- Consumes: T2 SQLiteClient。

- [ ] **Step 1: 改 config + validation + bootstrap**

config.py：删 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE/POOL_SIZE/MAX_OVERFLOW/POOL_TIMEOUT，加 SQLITE_PATH=os.getenv("SQLITE_PATH", "data/text2sql.db")；SQL_DIALECT 默认 "sqlite"。config_validation：mysql_* 校验→sqlite_path（路径可写）；治理/EXPLAIN mysql-only 闸门原样保留。bootstrap config dict：mysql_* 键→sqlite_path。

- [ ] **Step 2: 改 app_context + generator 引用**

app_context：import SQLiteClient；构造 SQLiteClient(path=config.sqlite_path, history_max_records=..., governance_proof_verifier=...)；property/字段更名 db_client/_db_client；sql_dialect 默认值各处 'mysql'→'sqlite'（治理 reload 路径仍按 candidate config）。generator：self.mysql_client→self.db_client（构造参数名 mysql_client→db_client，同步 app_context:505 传参）。

- [ ] **Step 3: 适配直接耦合测试 + 全量回归**

把 mock MySQLClient/断言 mysql_client 的测试改为 db_client/SQLiteClient（临时文件库）；治理路径测试显式 dialect='mysql'。
Run: `.venv/bin/python -m pytest tests -q` → 既有覆盖保持（适配）+ 新增；ruff check . 零。

- [ ] **Step 4: Commit**

```bash
git add -A  # 精确 staging：仅本任务触及文件，排除 logs churn
git commit -m "refactor: 存储 wiring 切换 SQLiteClient，默认方言 sqlite

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 执行/方言/安全边界 reconciliation

**Files:**
- Modify: `core/sql/generator.py`（_get_query_safety_error：allowed_schemas 按 SQLite main；allowed_tables fallback 仅业务表）、`core/sql/validator.py`（SQL_BLOCKED_TABLES 加 6 应用表；constrain_read_query sqlite 分支不注 MAX_EXECUTION_TIME——超时由 T2 看门狗）、`core/sql/dialect_detector.py`（默认随配置 sqlite）、`core/sql/field_validator.py`（SQLite 字段校验适配如需）
- Create: `tests/test_sqlite_execution_security.py`

**Interfaces:**
- Consumes: T2 SQLiteClient.get_table_schema（业务表）、T3 db_client/dialect。
- Produces: 生成 SQL 在 SQLite 端到端执行；应用表被拒。

- [ ] **Step 1: 写安全/执行测试（先失败）**

```python
def test_app_tables_blocked():
    # is_safe_read_query/validate_query_scope 拒绝 SELECT * FROM sql_generation_history 等 6 应用表
def test_business_tables_allowed():
    # SELECT * FROM users 放行；schema 限定 main.users 处理正确
def test_execute_sql_on_sqlite_end_to_end():
    # 临时 SQLite 业务库（种子）→execute_sql("SELECT ... FROM risk_blacklist")→返回 3 行
```

- [ ] **Step 2: 实现 reconciliation**

SQL_BLOCKED_TABLES 增 6 应用表名。_get_query_safety_error：allowed_schemas None→["main"]（或按 db_client.database）；allowed_tables None→get_table_schema() 业务表名。constrain_read_query：dialect=='sqlite' 不注 hint（看门狗在客户端）。dialect_detector 默认 sqlite。field_validator 若查 information_schema→PRAGMA table_info。

- [ ] **Step 3: 跑测试通过 + 全量回归 + Commit**

Run: `.venv/bin/python -m pytest tests/test_sqlite_execution_security.py tests -q` → PASS，既有保持。
```bash
git commit -m "feat: SQLite 执行/方言/安全边界 reconciliation（应用表禁查）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: few-shot 方言过滤

**Files:**
- Modify: `core/history/sqlite_client.py`（get_successful_history_for_few_shot 按 dialect 过滤；save_sql_history 新行 sql_dialect='sqlite'）、`core/retrieval/bm25_tfidf.py`（build_few_shot_index :548 传入/过滤 dialect）、`core/app_context.py`（:852/931 调用传当前 dialect）
- Create: `tests/test_few_shot_dialect_filter.py`

**Interfaces:**
- Consumes: T3 sql_dialect 默认 sqlite。
- Produces: few-shot 仅注入匹配当前方言的历史。

- [ ] **Step 1: 写过滤测试（先失败）**

```python
def test_mysql_history_excluded_from_sqlite_few_shot():
    # 库含 mysql 方言旧行 + sqlite 新行；dialect='sqlite' 查询仅返回 sqlite 行
def test_new_history_defaults_sqlite():
    # save_sql_history 不显式传 dialect→sql_dialect='sqlite'
```

- [ ] **Step 2: 实现过滤**

get_successful_history_for_few_shot 增 dialect 过滤（WHERE sql_dialect=:dialect，兼容 semantic_dialect 治理路径）；build_few_shot_index/调用方传当前 dialect；save_sql_history 默认 sql_dialect='sqlite'。

- [ ] **Step 3: 跑测试通过 + 全量回归 + Commit**

```bash
git commit -m "feat: few-shot 按方言过滤，新历史默认 sqlite

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: KG 构建器 SQLite 抽取 + Neo4j 元数据

**Files:**
- Modify: `core/graph_builder/extractors/live_db_extractor.py`（db_type='sqlite' 支持，_extract_sqlite，db_uri sqlite）、`core/graph_builder/main.py`（db_type 默认 sqlite）、`app/pages/kg_builder.py`（活体抽取改 SQLite 文件源；:113 selectbox 语义）、`tests/test_graph_builder.py`（适配）
- 数据: 重建/更新 Neo4j Database 节点 db_type='sqlite'（从 SQLite schema 抽取）

**Interfaces:**
- Consumes: T1 种子业务库 / data/text2sql.db。
- Produces: 活体抽取从 SQLite；Neo4j Database.db_type='sqlite'（如实反映配置）。

- [ ] **Step 1: 写抽取测试（先失败）**

```python
def test_live_extract_sqlite():
    # LiveDBExtractor(db_uri="sqlite:///data/text2sql.db", db_type="sqlite").extract()
    # → DatabaseIR.db_type=='sqlite'，含 users/risk_blacklist 等表
```

- [ ] **Step 2: 实现 SQLite 抽取**

live_db_extractor：放开 db_type=='sqlite'，_extract_sqlite 用 sqlite_master/PRAGMA table_info 抽表/列→SchemaExtractResult；db_uri sqlite 连接。main.py db_type 默认 sqlite。kg_builder 活体抽取 UI 改 SQLite 文件源（路径输入/默认 data/text2sql.db）。

- [ ] **Step 3: 重建 Neo4j Database 元数据**

用 SQLite 抽取结果重建图谱（或更新现有 Database 节点 db_type='sqlite' + 表/字段元数据）；检索链路结构/算法不动。核实 Neo4j Database.db_type=='sqlite'。

- [ ] **Step 4: 跑测试通过 + 全量回归 + Commit**

```bash
git commit -m "feat: KG 活体抽取改 SQLite，Neo4j Database 元数据反映 sqlite

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: UI 更新（MySQL→SQLite）

**Files:**
- Modify: `app/sidebar.py`（连接状态/统计 MySQL→SQLite：文件路径/表数/历史数）、`app/pages/system_info.py`（存储信息文案）、`app/pages/sql_generation.py`（执行目标注明 SQLite、默认 dialect）、`app/pages/governance_settings.py`（注明"语义治理仅支持 MySQL，SQLite 模式不可用"）
- 适配: AppTest（test_model_config_panel/test_governance_panel 等涉及文案断言）

**Interfaces:**
- Consumes: T3 db_client、T4 执行目标。

- [ ] **Step 1: 改 UI 文案/状态**

sidebar/system_info：MySQL 连接状态→SQLite（文件存在/表数/历史数）；"MySQL 存储"→"SQLite 存储"。sql_generation：执行目标 SQLite 提示。governance 面板：mysql-only 注明。widget key 不变（行为保持）。

- [ ] **Step 2: 适配 AppTest + 全量回归**

Run: `.venv/bin/python -m pytest tests -q` → 既有保持；整 app AppTest 渲染无异常。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(ui): 存储状态/文案 MySQL→SQLite，治理 mysql-only 注明

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: artifacts + 依赖移除 + 文档

**Files:**
- Modify: `schema.sql`（SQLite DDL 6 应用表）、`env.example`（MYSQL_*→SQLITE_PATH）、`requirements.txt`（删 mysql-connector-python）、`core/config_validation.py`（如有 mysql 残留键）、`README.md`（架构/环境/存储章节 MySQL→SQLite）、`CHANGELOG.md`（[Unreleased] 记录）
- Delete: `core/history/mysql_client.py`（确认零引用后）

**Interfaces:**
- Consumes: T1-T7 完成（迁移已验证、KG 已 off connector）。

- [ ] **Step 1: 改 artifacts**

schema.sql→SQLite DDL；env.example MYSQL_* 段→SQLITE_PATH；requirements 删 mysql-connector-python（SQLAlchemy 留）。

- [ ] **Step 2: 删 mysql_client.py + 零残留核查**

grep mysql_client/MySQLClient/mysql+mysqlconnector/MYSQL_ 全仓→零活引用（治理内核 Literal["mysql"] 字符串保留——那是方言名非依赖）。删 core/history/mysql_client.py。

- [ ] **Step 3: README/CHANGELOG**

README 架构/环境/存储/测试章节基于实际代码更新（SQLite 单文件、去 MySQL 服务、治理 mysql-only 休眠、Neo4j 保留）；CHANGELOG [Unreleased] 记录 Changed/Removed/Added。

- [ ] **Step 4: 全量回归 + ruff + 依赖核查 + Commit**

Run: `.venv/bin/python -m pytest tests -q` → 绿；ruff check . 零；`grep -i mysql requirements.txt` 零。
```bash
git commit -m "chore: 移除 MySQL 依赖与客户端，schema/env/文档同步 SQLite

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: 终验 + 整支审查 + 合并（控制器）

**Files:** 无新改动（验证任务）。

- [ ] **Step 1: 全量终验**

pytest 全量绿（既有+新增）；ruff 零；迁移对账复核（业务 31/历史 50）；Neo4j Database.db_type==sqlite。
端到端冒烟（8502）：自然语言"查询所有黑名单用户及其加入时间"→生成 SQLite SQL→执行返回 risk_blacklist 3 行→历史落 SQLite；应用表查询被拒。8501 不动；8502 验后即停。

- [ ] **Step 2: 整支对抗审查工作流**

Workflow 按维度（数据保真/安全边界/方言一致/超时/few-shot/依赖清除/文档准确）并行审查 + 逐条对抗验证。confirmed 问题单一修复波 + scoped re-review。

- [ ] **Step 3: 合并回 main**

superpowers:finishing-a-development-branch：备份主仓 .env/logs/.idea→合并→恢复→测试→清理 worktree/分支。向用户报告最终状态与裁决清单。