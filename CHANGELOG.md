# CHANGELOG

本项目的所有重要变更记录于此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased] - 2026-11-20（MySQL → SQLite 存储迁移）

### Changed

- **存储后端 MySQL → SQLite**：`core/history/sqlite_client.py` `SQLiteClient` 成为唯一
  应用存储客户端（`ApplicationContext.db_client`）；单文件嵌入式库 `data/text2sql.db`
  （`SQLITE_PATH` 可配），6 应用表与 8 业务表同库。首次连接幂等建表 + 治理列迁移 +
  原子种子加载（历史 50 行 / 业务 30 行；`PRAGMA user_version` 完成门防已初始化库重放）。
  文件库 NullPool、`:memory:` StaticPool + per-client RLock；每连接 `PRAGMA foreign_keys=ON`。
- **默认方言 mysql → sqlite**：`SQL_DIALECT` 默认 sqlite；生成方言仍由 Neo4j
  `Database.db_type` 驱动（多 dialect 生成保留），执行目标为 SQLite 业务库。
- **超时机制**：SQLite 无 `MAX_EXECUTION_TIME` hint；`execute_query_limited` 改用
  `threading.Timer` + `Connection.interrupt` 看门狗（保留 `SQL_QUERY_TIMEOUT_MS` 预算，
  仅精确匹配 `interrupted` 才转超时异常）。
- **安全边界**：`get_table_schema`/`get_column_schema` 仅返回业务表
  （sqlite_master/PRAGMA，大小写归一）；6 应用表全部进入 `SQL_BLOCKED_TABLES` 黑名单，
  无条件生效（独立于 `SQL_SCOPE_ENFORCEMENT` 开关）。
- **few-shot 按方言过滤**：按当前生成方言筛选历史示例；新行 `sql_dialect` 默认 sqlite，
  迁移保留的 50 行 mysql 旧历史不注入 SQLite 提示。
- **KG 活体抽取改 SQLite**：`live_db_extractor` 仅支持 sqlite（原生反射，排除 6 应用表，
  声明外键优先于启发式推断）；kg_builder 活体构建页改填 SQLite 文件路径；
  Neo4j `Database` 节点 `db_type` 更新为 sqlite（如实反映配置库）。
- **UI 文案**：侧栏/系统信息存储状态与统计 MySQL→SQLite（文件路径/表数/历史数）；
  治理面板注明语义治理仅支持 MySQL（SQLite 模式不可用）。
- **配置/artifacts/文档同步**：config `MYSQL_*`→`SQLITE_PATH`；`env.example`、
  `schema.sql`（镜像 seed_history.sql 的 SQLite DDL）、`requirements.txt`、
  README 架构/环境/存储/测试章节基于实际代码更新。
- 治理（语义治理 + EXPLAIN 预检）保持 **mysql-only 休眠**：内核与闸门未扩展，
  SQLite 模式下不可启用；治理路径测试显式使用 mysql dialect。

### Removed

- `core/history/mysql_client.py`（`MySQLClient`）与 `mysql-connector-python` 依赖
  （SQLAlchemy 保留，SQLite 经其访问）；KG 活体抽取的 MySQL 分支
  （`mysql+mysqlconnector` URI / INFORMATION_SCHEMA 查询）。
- MySQL 专属测试（SQLite 侧覆盖已在 `test_sqlite_client.py` 等存在）：
  `test_regressions.py` 的 `stream_results` 流式截断测试；`tests/sql/test_preflight.py`
  的 4 个 `MySQLClient` EXPLAIN 适配器测试（hinted EXPLAIN / timeout 校验 /
  非 SELECT 拒绝 / 连接 invalidate）；`test_sqlite_client.py` 的签名 parity 测试
  （parity 使命随 MySQLClient 移除结束；墙钟 deadline 属性断言保留并入 explain 测试）；
  `test_graph_builder.py` 的 MySQL 活体抽取路径测试（活体抽取已 SQLite-only，
  不支持方言拒绝测试扩展覆盖 mysql）。
  另 3 个 `test_regressions.py` MySQL 内部测试**适配**为 SQLiteClient（迁移幂等 /
  并发重复容忍 / connect 迁移时序），断言语义不变。

### Added

- `scripts/migrate_mysql_to_sqlite.py` 一次性迁移脚本（源 MySQL 只读 introspect →
  种子，逐表行数对账；历史工具，重跑需手工安装 mysql-connector-python）与
  `data/seed_business.sql` / `data/seed_history.sql` 部署种子。
- `tests/test_sqlite_client.py`（DDL/种子门控/schema 迁移/看门狗/治理往返）、
  `tests/test_migration_reconciliation.py`（迁移对账）、
  `tests/test_sqlite_execution_security.py`（应用表禁查边界）、
  `tests/test_few_shot_dialect_filter.py`（方言过滤）。

### Verified

- 全量回归：`1067 passed, 9 skipped, 0 failed`
  （`.venv/bin/python -m pytest tests -q`，Python 3.12.10；基线 1074 passed / 9 skipped，
  差值 7 = 上述移除的 MySQL 专属测试数）。
- `.venv/bin/python -m ruff check .` 零告警（ruff 0.15.20）。
- 依赖核查：mysql import 阻断器下 `core.app_context` / `core.graph_builder.main` /
  `app.pages.kg_builder` 导入全部通过；代码零活
  `mysql_client`/`MySQLClient`/`mysql+mysqlconnector`/`MYSQL_` 引用
  （治理内核方言字符串、历史 CHANGELOG/文档、一次性迁移脚本除外）。

## [Unreleased] - 2026-11-19

### Removed

- **Neon/Qwen 旧实验链整组删除**（主链路零引用）：`app_neon.py`、
  `core/llm/qwen_generator.py`（`core/llm/` 整目录）、
  `core/knowledge/neon_knowledge.py`、`tests/test_neon_text2sql.py`、
  `tests/test_llm_integration.py`。
  `NEON_DB_URL` 环境变量保留：仍有活消费者
  `core/sql/field_validator.py` 的 `__main__` 手动演示。
- **core 层 28 个零引用死方法/死函数**（含 3 个传递性孤儿方法）、
  3 个只赋值从未读取的属性、2 处死存储（`node_index`、`self.linter`），
  以及 Neo4j async driver 残留（`execute_query_async` 及其初始化/teardown）。
  清单见设计文档 §5.2；删除前逐名 grep 确认含测试在内零引用。
- **过时项目全景页** `docs/project_overview.html`（早于 v1.4；
  README 重写后为唯一权威文档）。
- **停止跟踪运行时产物**：`logs/` 下 2 个日志、`.idea/` 下 6 个文件、
  `llm_test_report.json`（`git rm --cached`，本地文件保留，均已被 .gitignore 覆盖）。

### Changed

- **UI 分层**：`app.py` 由 1492 行收敛为 110 行薄入口
  （页面配置 → 样式/状态 → 侧栏 → 4 Tab 分发 → footer）；
  新增 `app/styles.py`、`app/state.py`、`app/bootstrap.py`、`app/sidebar.py`、
  `app/model_config.py` 与 `app/pages/sql_generation.py`、`app/pages/history.py`、
  `app/pages/system_info.py`。纯搬运 + 最小胶水：widget key、session state key、
  渲染顺序、CSS 全部保持不变。
- **README 基于实际代码重写**：新增架构章节（分层图、逐包目录树、
  自然语言查询数据流）；环境说明改为"在 Python 3.12 上开发验证"、
  部署示例版本中性（`PYTHON_BIN=/path/to/python3`），删除未核实的
  "Python 3.9+" 最低版本声明；功能/配置/测试描述与代码对齐
  （默认 LLM 模型 `gemma4:E4B`、治理面板 16 项可编辑配置等）。
  版本号保持 v1.4（housekeeping，不 bump）。

### Added

- `pyproject.toml`：ruff 门禁（target py312、line-length 100、
  select E4/E7/E9/F，排除 python_deps/.venv/data/logs）+
  `[tool.pytest.ini_options] testpaths=["tests"]`。
- `tests/test_architecture.py`：4 项架构守护测试
  （app.py 薄入口行数上限、UI 模块入口函数可调用、app/ 无循环 import、
  自定义 CSS 注入生效）。

### Security

- **`.env` 停止跟踪**（`git rm --cached`；曾含 4 处 PASSWORD/API_KEY，远程为 GitHub）。
  停止跟踪不会清除 git 历史中的凭据：**建议轮换相关凭据**；
  历史清除（filter-repo/BFG）属破坏性操作，不在本次范围，须用户另行批准。

### Verified

- 全量回归：`938 passed, 14 skipped, 0 failed`
  （`.venv/bin/python -m pytest tests -q`，Python 3.12.10）。
- `.venv/bin/python -m ruff check .` 零告警（ruff 0.15.20）。

## [Unreleased] - 2026-10-29

### Fixed

- **图谱状态页"关系边"恒为 0**（`app/pages/kg_builder.py`）
  统计 Cypher 只匹配 `[r:CONNECTS]` 一种关系类型，而实际装载产生的是
  `HAS_TABLE` / `HAS_COLUMN`，导致关系边计数永远显示 0。
  修复：改为统计所有关系类型 `()-[r]->()`。

### Docs

- README 新增"功能展示"小节：自然语言查询全链路、查询输入、执行历史、
  知识图谱构建、Neo4j 图谱状态、系统信息共 6 张真实运行截图
  （`docs/screenshots/`）。

## [Unreleased] - 2026-10-25

### Fixed

- **模型配置面板：连续保存静默丢失用户输入**（`app.py` `_reseed_model_widgets`）
  上一次保存/恢复成功后设置的 reseed 标记，会在下一次保存按钮触发的 rerun 里
  先清掉 `cfg_llm_model` 再用旧配置重新播种，导致用户新输入的模型名被静默丢弃、
  界面却显示保存成功（连续第二次保存永远写回旧值）。
  修复：保存/恢复按钮触发的本轮 rerun 不清除控件状态，标记留到下一轮消费。

- **检索元数据缺少 `database_id`，按库过滤后零命中**
  （`core/app_context.py` `_populate_retriever` / `_load_knowledge_from_neo4j`，
  `core/sql/generator.py` `create_sql_generator`）
  索引元数据未携带 `database_id`，检索过滤后无任何命中。已在所有索引入口补齐。

- **MySQL 管理表不会自动创建，新库指向即全线瘫痪**
  （`core/history/mysql_client.py` 新增 `_ensure_management_tables`）
  代码中原本没有任何建表语句，6 张管理表依赖手工执行 `schema.sql`。
  现改为连接验证成功后幂等自动创建（`CREATE TABLE IF NOT EXISTS`），
  随后照常执行治理列迁移。首次指向新数据库（如 `business_db`）开箱可用。

### Changed

- **默认 LLM 模型**：`gemma3:e4b` → `gemma4:E4B`
  （`config.py` 环境变量兜底值、`core/provider_catalog.py` ollama 提供商推荐模型）。
  旧默认值在本地 ollama 不存在，导致 `OllamaEndpointNotFoundError`。

- **测试断言同步**：`tests/test_comprehensive.py` 的 `MYSQL_DATABASE`
  断言由 `text2sql_db` 更新为 `business_db`。

### Environment（配置与数据，非代码）

- `.env`：`LLM_MODEL=gemma4:E4B`、`MYSQL_HOST=127.0.0.1`、`MYSQL_DATABASE=business_db`。
  - `MYSQL_HOST` 改 `127.0.0.1`：本机 MySQL 运行在 Docker 容器中，`localhost`
    连接经 NAT 回环被识别为 `root'@'192.168.97.1`，触发 Access denied。
  - `MYSQL_DATABASE` 改 `business_db`：应用单一 MySQL 连接同时承担业务执行与
    历史存储，原指向的 `text2sql_db` 只有管理表，业务 SQL 执行必然失败。

- **Neo4j 知识图谱库名统一**：`legacy_db` → `business_db`（Database 节点 name 属性，
  全图扫描确认无残留；101 节点 / 100 边无损）。

- **历史记录迁移**：`text2sql_db.sql_generation_history` 的 39 条记录迁入
  `business_db`（含 4 月旧记录），未丢失。

### Verified

- 全量回归：`934 passed, 16 skipped`。
- MySQL 真实集成测试（`TEXT2SQL_RUN_DB_TESTS=1`）：6 个全绿，
  跑后 `table_schema`/`column_schema`/`sql_generation_history` 零测试残留。
- 端到端：检索（命中 risk_blacklist）→ SQL 生成 → 执行 → 历史回写，
  在干净图谱 + 新配置下全链路通过。

### Fixed（本轮补充）

- `fix(mysql)`：`table_schema` 建表 DDL 缺失 `properties` 列，
  新增幂等迁移 `_migrate_table_schema()` 为旧库补列；
  `upsert_table_schema` 失败时不再静默返回 True（`raise_on_error=True`）。
- `fix(mysql)`：其余 4 处 `execute_update` 失败静默写法统一改 `raise_on_error=True`
  （`upsert_column_schema`、`update_sql_execution`、`save_feedback`×2、
  `generator.fix_sql` 历史更新），写失败立即显式报错。
- `feat(ui)`：侧栏品牌 logo 换新（`assets/logo.png` 缩至 480 宽，
  `assets/logo_icon.png` 由新图徽标区重裁 128×128 页签图标，
  `assets/logo_full.png` 保留全分辨率原图）；
  透明底（RGBA）处理，侧栏白底正常融合；
  logo 点击放大全屏、再点击缩小（components.html 同源 iframe
  内通过 frameElement 撑满视口实现，全屏态用全分辨率图）。
- `fix(ui)`：侧栏知识库统计 Cypher 把关系与节点行做笛卡尔积
  （`OPTIONAL MATCH ()-[r]-()` 未绑定节点），显示值 = 节点数 × 关系数；
  改为 `OPTIONAL MATCH (n)-[r]-()` + `count(DISTINCT r)`，
  真实 101 节点 / 100 关系不再显示为 20200。
- `feat(ui)`：图标体系从 emoji 升级为 Fluent Color 内联 SVG
  （新增 `app/ui_icons.py`，19 个图标，MIT 协议，零外部请求，
  https://github.com/microsoft/fluentui-system-icons ，
  微软 Fluent UI 彩色圆角风格，经 Iconify 抓取 24px 版本）；
  彩色固定配色，不再继承文本色；
  节标题 / 侧栏状态行换 SVG 图标（UIkit iconnav 的等距排列风格），
  按钮、页签、反馈消息去除装饰 emoji；kg_builder hero 徽章同步换图标。
- `test(mysql)`：集成测试连接串改读 `config`，
  自带夹具播种/清理，不再硬编码 `localhost`/`text2sql_db`。
