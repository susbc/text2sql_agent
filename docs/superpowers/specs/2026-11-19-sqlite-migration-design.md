# MySQL → SQLite 彻底迁移 设计文档

日期：2026-11-19
状态：待确认（v2：并入 builder-check 7 项裁决 + 用户澄清）

## 1. 意图与背景

用户要求："将保存记录从 MySQL 换成 SQLite，不保存到本地数据库"。目标＝**彻底去掉
本地 MySQL 服务依赖**，改用嵌入式 SQLite 文件库（持久化在 `.db` 文件，无需服务）。
Neo4j 知识图谱服务保留。用户澄清：**Neo4j 的 Database 节点须如实反映实际配置的
数据库**（迁移后＝SQLite），元数据与真实后端一致，而非硬编码假值。

MySQL 当前三职责（同处 business_db 库）：
1. 应用存储：sql_generation_history(50 行)、user_feedback(0)、治理凭证。
2. 知识元数据：table_schema/column_schema/knowledge_metadata/retrieval_terms
   ——全 0 行、upsert 无调用方（已退化）；知识实际来自 Neo4j。迁移只需建表。
3. 执行目标：生成 SQL 经 execute_sql→mysql_client.execute_query_limited 在
   business_db 执行；字段校验查 MySQL 表结构 + allowed_schemas。

业务表 8 张共 31 行：users(12)/transaction_record(8)/user_account(6)/
risk_blacklist(3)/prediction_results(1)/account_freeze_log/daily_account_check/
fee_rate_config(0)。客户端基于 SQLAlchemy（mysql+mysqlconnector+QueuePool）。

## 2. 用户已决策

- 范围：彻底去 MySQL（存储+元数据+执行全迁 SQLite）。
- 数据来源：迁移现有 MySQL 数据（业务结构+31 行、历史 50 行）→ SQLite 种子入库；
  授权只读 introspect（已完成）。
- 持久化：嵌入式 SQLite 文件（非内存），重启不丢。
- **语义治理（Q2）**：内核保持 mysql-only，SQLite 模式下不可用（默认本就关闭）；
  UI 注明"语义治理仅支持 MySQL"。**不扩展内核**（Literal["mysql"] pin、语义模型、
  golden 数据集、config 闸门均不动）。
- **方言杠杆（Q1+澄清）**：Neo4j Database 节点 db_type 更新为实际配置库（sqlite）；
  KG 构建器活体抽取改从 SQLite 重建图谱元数据。放宽"不动 Neo4j"为"不动检索链路
  结构/算法，但 Database 元数据随实际配置库更新"。

## 3. 方案选择

A（选定）：drop-in SQLiteClient 沿用 MySQLClient ~20 公开方法签名（SQLAlchemy-SQLite
引擎）+ 一次性数据迁移种子 + 默认 SQLite + 换 wiring/config/UI/测试。接口不变→上游
改动最小。B 裸 sqlite3 重写（收益低，弃）；C 多后端抽象（YAGNI，弃）。

## 4. 目标 / 非目标 / 反目标

**目标**
- 去 MySQL 服务依赖：应用存储+业务数据/执行落到单文件 data/text2sql.db（应用表+
  业务表同库，忠实当前布局）。
- 迁移数据行数对账一致（业务 31、历史 50）。
- 默认 SQLite；生成 SQL 在 SQLite 业务库端到端可执行；Neo4j Database 元数据＝sqlite。
- config MYSQL_*→SQLITE_PATH；去池参数；env.example/schema.sql/requirements
  （去 mysql-connector-python，留 SQLAlchemy）同步。
- UI MySQL→SQLite；测试适配全量绿。

**非目标**
- 不动 Neo4j 检索链路结构/算法（BM25/FAISS）；仅 Database 元数据随配置更新。
- 不扩展语义治理/正确性内核（保持 mysql-only，SQLite 下休眠）。
- 不改 SQL 生成/治理业务逻辑（仅存储与执行后端替换）。
- 不保留 MySQL 后端选项；不升级无关依赖。

**反目标**
- 迁移行数/数据与源不一致。
- 生成 SQL 无法在 SQLite 执行（方言/校验/allowed_schemas 未 reconcile）。
- 破坏既有 938 测试覆盖（适配而非删除）。
- 残留 MySQL 服务依赖。
- 安全边界放宽致应用表可被生成 SQL 查询。

## 5. 设计细节

### 5.1 SQLiteClient（core/history/sqlite_client.py）
- 沿用 MySQLClient 全部公开方法签名（connect/close/get_connection/execute_query/
  execute_query_limited/explain_query/execute_update/upsert_*/save_sql_history/
  save_governed_sql_history/finalize_governed_sql_execution/update_sql_execution/
  get_history_list/get_successful_history_for_few_shot/get_history_detail/
  get_table_schema/get_column_schema/get_statistics）。
- 引擎 create_engine("sqlite:///<path>", connect_args={"check_same_thread":False})；
  PRAGMA foreign_keys=ON；文件库池按实现者权衡（WAL 可选）。
- DDL 翻译：BIGINT AUTO_INCREMENT PK→INTEGER PRIMARY KEY AUTOINCREMENT；
  VARCHAR/TEXT→TEXT、DECIMAL→NUMERIC、DATETIME/TIMESTAMP→TEXT、TINYINT/INT→INTEGER、
  JSON→TEXT；去 COLLATE/ENGINE/MySQL 注释。
- **MySQL 专有语法翻译项（builder 列出）**：ON DUPLICATE KEY UPDATE→ON CONFLICT
  DO UPDATE；_prune_history 多表 DELETE→SQLite 子查询/分步；information_schema
  迁移逻辑→sqlite_master/PRAGMA；GROUP_CONCAT(... ORDER BY)→SQLite 语法；
  ON UPDATE CURRENT_TIMESTAMP→触发器或应用层时间戳；NOW()→CURRENT_TIMESTAMP。
- EXPLAIN：explain_query 实现 EXPLAIN QUERY PLAN（接口 parity）；**但预检 preflight
  保持 mysql-only 闸门，SQLite 下不启用**（Q2 裁决——避免死代码）。
- 执行超时（Q4）：SQLite 无 MAX_EXECUTION_TIME hint→用 sqlite3 progress_handler/
  Connection.interrupt 看门狗保留 SQL_QUERY_TIMEOUT_MS 控制（行为保持）。
- execute_query_limited：LIMIT/OFFSET 注入保留。
- DECIMAL→NUMERIC 为浮点亲和（货币列 SUM 可能有浮点伪影）——接受，对账以行数为准
  （builder  borderline 注记，用户范围未要求值级对账）。

### 5.2 数据迁移（scripts/migrate_mysql_to_sqlite.py + 种子）
- 只读连源 MySQL（.env），introspect 14 表结构+数据。
- 生成入库种子：data/seed_business.sql（8 业务表 DDL+31 行）+ 历史迁移（50 行）。
- SQLiteClient.connect() 库不存在→种子幂等初始化。
- 行数对账：逐表 COUNT==源（业务 31、历史 50）。
- **时序（Q5）**：先迁移（源 MySQL 在跑、已授权）→验证→再移除 mysql-connector。

### 5.3 方言 / 执行 / 安全边界
- 方言杠杆（Q1）：生成方言来自 Neo4j Database.db_type；迁移后该节点＝sqlite
  （KG 构建器从 SQLite 重建，见 5.6）。dialect_detector 默认随实际配置。
- allowed_schemas（Q3）：SQLite 无 schema 前缀，按 main 处理；get_table_schema 改查
  sqlite_master/PRAGMA table_info 返回**业务表**（排除 6 应用表）；应用表补进
  SQL_BLOCKED_TABLES，杜绝 allow-all 误放（knowledge_metadata/retrieval_terms 原不在
  黑名单）。allowed_tables fallback 仅业务表。
- _is_safe_query/validator：sqlglot/sqlfluff 原生 sqlite 方言（无 postgres/spark 缺口）。
- 治理/EXPLAIN（Q2）：config_validation mysql-only 闸门保留（诚实）；governance/
  EXPLAIN 默认关闭，SQLite 下不可启用；治理面板 UI 注明仅 MySQL。

### 5.4 few-shot 方言过滤（Q6）
- get_successful_history_for_few_shot/build_few_shot_index 加方言过滤：按当前生成
  方言筛选；新行 sql_dialect 默认 sqlite；旧 50 行 mysql 历史不注入 SQLite 提示。
  这是为正确性必需的最小检索改动（明确豁免"不动检索"非目标，仅此过滤）。

### 5.5 配置 / wiring / UI
- config.py MYSQL_*→SQLITE_PATH（默认 data/text2sql.db）；去池参数；
  config_validation/bootstrap config dict 键替换。
- app_context.py MySQLClient→SQLiteClient；property 彻底更名 db_client（去 mysql
  命名），改上游引用（generator/sidebar/system_info/bootstrap）。
- sidebar/system_info：MySQL 状态/统计→SQLite（文件路径/表数/历史数）；文案更新。
- sql_generation：执行目标注明 SQLite；默认选 SQLite dialect。
- governance 面板：注明"语义治理仅支持 MySQL（SQLite 模式不可用）"。
- env.example MYSQL_*→SQLITE_PATH；requirements 去 mysql-connector-python；
  schema.sql→SQLite DDL（6 应用表）。

### 5.6 KG 构建器 + Neo4j 元数据（Q7+Q1）
- app/pages/kg_builder.py 活体抽取：mysql+mysqlconnector URI→改从 SQLite 文件抽取
  （graph_builder/main.py db_type 默认 sqlite；live_db_extractor 适配 SQLite）。
- 重建/更新 Neo4j Database 节点 db_type='sqlite'（如实反映配置库）；表/字段元数据
  从 SQLite schema 抽取。检索链路结构/算法不动。
- test_graph_builder 适配 SQLite 抽取。

### 5.7 测试适配
- MySQL mock/fixture（test_comprehensive/test_regressions/test_history_governance_proof/
  tests/sql/*）→SQLiteClient（临时文件库或 :memory:）；断言语义不变。
- 治理路径测试显式用 mysql dialect（内核仍 mysql-only），不依赖 app 默认 sqlite。
- 新增：SQLiteClient 单测（DDL/upsert/execute_limited/超时看门狗/历史读写）、迁移
  行数对账测试、端到端生成→SQLite 执行冒烟、few-shot 方言过滤测试、安全边界测试
  （应用表被拒）。
- 全量回归：既有覆盖不丢+新增。

## 6. 验证计划
1. 基线 938/14（迁移前）。
2. 迁移对账：逐表 COUNT==源（业务 31、历史 50）。
3. 全量测试绿（既有+新增）；ruff 零。
4. 端到端冒烟（8502）：自然语言→生成 SQLite SQL→执行返回业务数据（"查询黑名单
   用户"→risk_blacklist 3 行）→历史落 SQLite；应用表查询被安全边界拒绝。
5. 依赖核查：requirements 无 mysql-connector；代码无 mysql 服务连接残留。
6. Neo4j Database.db_type==sqlite 核实。
7. 8501 不动；8502 验后即停。

## 7. 实现者决策（builder-decidable）
- 种子文件格式/首次初始化触发点；测试 fixture :memory: vs 文件；WAL/池选择。
- MySQL 专有 SQL 改写具体形式（5.1 已列项）。
- 多 dialect 生成 vs SQLite 单一执行的 UI 措辞。
- git 提交切分（迁移脚本+种子 / SQLiteClient+wiring / 方言执行+安全边界 /
  few-shot 过滤 / KG+Neo4j 元数据 / UI+config / 治理 gating 文案 / 测试 / 文档）。

## 8. 控制器裁决记录（builder-check 7 项）
- Q1 方言杠杆：更新 Neo4j Database 元数据为实际配置库（用户澄清）+KG 改 SQLite 抽取。
- Q2 治理：mysql-only 休眠，不扩展内核；弃 SQLite EXPLAIN 预检（死代码）。
- Q3 安全边界：get_table_schema 仅业务表，应用表入黑名单，allowed_schemas 按 main。
- Q4 超时：sqlite3 interrupt 看门狗保留 SQL_QUERY_TIMEOUT_MS。
- Q5 时序：先迁移后去 connector，源库可用。
- Q6 few-shot：加方言过滤，新行默认 sqlite，旧 mysql 行不注入。
- Q7 KG 构建器：活体抽取改 SQLite。