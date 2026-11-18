# CHANGELOG

本项目的所有重要变更记录于此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
