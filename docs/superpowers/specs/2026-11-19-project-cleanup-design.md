# 项目整理与架构规范 设计文档

日期：2026-11-19
状态：**已确认**（用户 2026-11-19 回复"确认"批准本设计与 §5 删除清单；执行方式选定子代理逐任务）。
验证：15 代理对抗验证工作流 `wf_bd31cc53-762` 已完成；builder-check 审查已完成。
下列修订已并入：验证判定的政策细化、Neon 组处置、传递性孤儿、builder 纠错、版本/部署文档决策。

## 1. 意图与背景

项目约 4 万行 Python。用户反馈"代码写得太乱"，要求：

1. 检查并删除死代码 —— **先列清单确认，再删除**；
2. 规范程序架构（行为不变）；
3. 把程序架构写入 README；
4. 基于实际代码更新 README 内容。

摸底结论：**乱集中在 UI 层**。`core/` 业务层已按 sql / semantic / retrieval /
graph_builder / history / knowledge / evaluation / chain / utils 等子包模块化，
结构合理，不动。`app.py` 是 1492 行单文件：CSS、会话状态、系统初始化、
模型配置面板（~190 行）、侧栏（~280 行内联代码）、4 个 Tab 全部堆在一起。
项目已有 `app/pages/` 抽取先例（kg_builder、governance_settings），本次把
剩余部分按同一模式拆完。

## 2. 方案选择

| 方案 | 内容 | 取舍 |
|---|---|---|
| **A（已选定）** | 拆 UI 层，不动 core；删死代码；补 ruff 配置；重写 README | 风险低、收益集中；测试全量回归验证 |
| B | A + 重排 core 结构 | core 现状问题不大，几十个测试 import 要跟着改，收益有限 |
| C | 只删死代码 + 更新 README | 不解决"乱"的主要来源 app.py |

用户已选 A。

## 3. 目标 / 非目标

**目标**
- 删除经确认的死代码（清单见 §5），git 瘦身为约 -1900 行。
- `app.py` 变为 ~150 行薄入口；UI 代码按职责落入 `app/` 模块。
- 行为完全不变：widget key、session state key、渲染顺序、CSS 全部保持。
- 补 `pyproject.toml`（ruff 配置，README 提到的 ruff 门禁落地）。
- README 基于实际代码重写：新增架构章节（分层图 + 目录树 + 请求数据流），
  修正环境说明（Python 3.12，机器上无 3.11），功能/测试描述与代码对齐。

**非目标**
- 不改 `core/` 的模块划分与公开 API（仅删除 §5 确认的死方法）。
- 不改任何业务逻辑、SQL 生成链路、治理规则。
- 不升级依赖、不换 Streamlit 版本。
- 不动用户未跟踪的备份 zip（`text2sql_agent_server_*.zip`）。
- 不重启正在运行的 8501 服务（PID 4155）；验证用 8502 端口另起实例。

**反目标（做了即失败）**
- 删掉测试仍在使用的"疑似死代码"（测试即规格）。
- 拆分后 AppTest 集成测试因 widget key / 渲染顺序变化而失败。
- README 描述与代码不符（写架构图时凭印象而非实际代码）。

## 4. 约束

- 测试耦合（builder-check 纠正）：**只有 test_model_config_panel 用
  `AppTest.from_file("app.py")` 整文件执行**；test_governance_panel 用临时
  脚本单测 app/pages/governance_settings；test_regressions / test_graph_builder
   monkeypatch core 模块，不用 AppTest。整 app 渲染保护来自
  test_model_config_panel + 新增 test_architecture::test_custom_css_injected
  + widget key 清单 diff。拆分仍透明，前提不变。
- 唯一源码级断言：`test_model_config_panel.py:425`
  `test_no_stale_1536_embedding_dim_fallback` 读 app.py 源码断言
  `'"dimensions", 1536' not in source`。模型面板搬出 app.py 后，该测试改为
  读新模块源码（保持守护意图不变）。
- `st.set_page_config` 必须是 app.py 中第一个 st 调用。
- 验证环境：`.venv`（Python 3.12.10，含 pytest 7.4.3 / ruff 0.15.20 /
  streamlit 1.29.0 / sqlfluff / neo4j / SQLAlchemy）。README 现写"验证过的
  Python 3.11"与机器不符，改为 3.12。
- 真实数据库/LLM 测试由各文件内 `TEXT2SQL_RUN_DB_TESTS=1` 开关 gating
  （默认关；conftest.py 只做 sys.path 设置——builder-check 纠正）。
  基线实测：934 passed, 16 skipped, 0 failed（含 .env 真实配置也如此）。

## 5. 死代码清单（先确认再删）

验证方法：vulture（min-confidence 60）+ ruff F401/F811/F841 + 逐名 grep
全仓交叉验证，再经 15 代理对抗验证工作流复核。
**删除判据：定义之外零引用（含测试）。有测试引用的一律保留。**

**政策细化（orchestrator 决策，回应 critic 第 7 条）**：历史文档叙述
（README 版本历史段落、CHANGELOG 条目）提及某符号 ≠ 使用引用——那是
对过去变更的记录，不是调用。使用型文档（运行命令、环境变量表、部署
指引）才是活引用。据此，工作流中 4 个仅因历史叙述被判 alive 的成员
（`get_all_nodes`、`get_node_by_name`、`save_feedback`、`self.linter`）
重新归类为 dead——四者代码/测试调用方均为零（双重 grep 确认），且
本就在用户批准的 §5.2 清单内。

**Neon 组处置**：工作流按字面规则判 qwen_generator / neon_knowledge /
两个测试文件 alive（互引 + README 提及 + pytest 收集），但验证 notes
明确：两测试文件对活模块零覆盖损失，整组可删——这正是用户批准的
§5.1 整组删除。附加条件：README.md:153-154、250-254 的 Neon 测试引用
必须同步清除（Task 1 外科式编辑），299-302 的 NEON_DB_URL 表项改写。
**NEON_DB_URL 保留**：发现真实活消费者 `core/sql/field_validator.py:374`
的 `__main__` 演示 `test_validator()` 经 `os.getenv` 读取（绕过 config.py，
原"死配置"判断无效）。

### 5.1 整条 Neon/Qwen 旧实验链（主链路零引用，整组删除）

| 文件 | 行数 | 说明 |
|---|---|---|
| `app_neon.py` | 378 | 旧备用入口，全仓无任何引用 |
| `core/llm/qwen_generator.py` | 272 | 仅被 app_neon 与下列死测试引用；`core/llm/` 整目录删除（无 `__init__.py`） |
| `core/knowledge/neon_knowledge.py` | 333 | 同上 |
| `tests/test_neon_text2sql.py` | 317 | Neon PostgreSQL 实验测试 |
| `tests/test_llm_integration.py` | 268 | Qwen+Neon 旧链路测试，产出 llm_test_report.json |
| `llm_test_report.json` | — | 2026-03-22 测试产物，已被 .gitignore 覆盖但仍在 git 跟踪中，`git rm --cached` |
| `env.example` 中 `NEON_DB_URL=` | — | **保留**（验证发现活消费者：field_validator.py `__main__` 演示） |
| `README.md` Neon 测试引用 | 若干行 | 153-154（tests 树）、250-254（运行命令/迁移注记）随组删除；299-302  env 表项改写为 field_validator 演示用途 |

### 5.2 零引用死方法/死函数（逐个 grep 确认，含测试零引用）

| 文件 | 成员 |
|---|---|
| `core/knowledge/neo4j_client.py` | `execute_query_async`、`get_all_nodes`、`get_table_nodes`、`get_column_nodes`、`get_node_by_name`、`sync_metadata_to_mysql` |
| `core/history/mysql_client.py` | `save_feedback` |
| `core/retrieval/bm25_tfidf.py` | `preprocess`、`retrieve_tables`、`retrieve_columns` |
| `core/sql/field_validator.py` | `suggest_fix`、`_get_column_name`、`_get_table_name`（删除前再确认本文件内无自调用） |
| `core/sql/validator.py` | `get_violation_types`、`_extract_tables` |
| `core/sql/dialect_detector.py` | `get_all_databases`、`refresh_metadata` |
| `core/graph_builder/models.py` | `get_tables_by_database`、`get_columns_by_table`、`to_dict` |
| `core/graph_builder/loader/neo4j_writer.py` | `clear_graph`、`get_table_details` |
| `core/embedding_factory.py` | `get_cache_size` |
| `core/history/identity.py` | `retrieval_fields` |
| `core/chain/prompts.py` | `create_validation_messages`；`sql_generation_template` / `knowledge_format_template` / `query_rewrite_template` 三个只赋值从未读取的属性（连同 `__init__` 中的构造语句） |

疑似死存储——**验证已确认零读取，升级为确定删除**：
`bm25_tfidf.py:518 node_index` 赋值、`validator.py:167 self.linter` 赋值
（实际 lint 走 `sqlfluff.lint()` 顶层 API，validator.py:188；删除后
`from sqlfluff.core import Linter` import 若搁浅一并清理）。

**传递性孤儿（批准删除的直接后果，critic 确认死链，随 Task 2 一并删除）**：
- `core/chain/prompts.py`：删 `create_validation_messages` 后 orphan 的
  `sql_validation_template` 赋值、`_get_validation_template`、
  `_get_knowledge_format`、`_get_rewrite_template`（死-to-死链，已读码确认）。
  注意 `tests/test_offline.py:115-121` 对 prompts.py 的 5 个字面量断言
  全部存活（critic 已核），删除后该文件必须仍绿。
- `core/knowledge/neo4j_client.py`：删 `execute_query_async` 后 vestigial 的
  async-driver 机制——`self.async_driver` 初始化(:68)、AsyncGraphDatabase
  创建(:91-100)、teardown(:128-136)、async import(:15-17 区域)。
  读取方仅剩 teardown 与已删方法，整体移除。

### 5.3 未使用 import（ruff F401，共 6 处，自动修复）

- `app.py:24` `icon`
- `app/pages/governance_settings.py:7` `icon`、`icon_line`、`inject_icon_styles`
- `app/pages/kg_builder.py:8` `icon_line`、`inject_icon_styles`

### 5.4 仓库垃圾（git 瘦身）

- `git rm --cached`（保留本地文件）：`logs/app.log`、
  `logs/app.2026-03-21_21-24-09_820214.log`、`llm_test_report.json`、
  `.idea/` 下 6 个文件 —— 均已被 .gitignore 覆盖但历史上被跟踪。
- **安全项（扫描新发现）**：`.env` 被 git 跟踪（含 4 处 PASSWORD/API_KEY），
  远程为 GitHub。`git rm --cached .env` 停止跟踪；**历史中的凭据不会因此
  消失**——需向用户单独报告：建议轮换凭据，历史清除（filter-repo/BFG）
  属破坏性操作，不在本次范围，须用户另行批准。
- 删除 `tmp_smoke/`（未跟踪临时冒烟脚本目录）。
- `docs/project_overview.html`：2026-05-18 的项目全景页，已过时（早于 v1.4），
  README 重写后成为唯一权威文档 → 建议删除（待确认）。

### 5.5 明确保留（不是死代码）

- **仅测试引用的公开 API**：`fix_sql_async`、`get_history_list`、
  `add_document`、`remove_document`、`extract_columns_from_sql`、
  `process` / `process_async`、`generate_sql_async`、`create_sql_generator`、
  `create_app_context_from_env`、`outstanding_size`、`confirm_clear_kg`
  等 —— 测试即规格，保留。（critic 纠错：`get_next_db_id` 原误列于此——
  extractor 用的是自己的私有 `_get_next_db_id`，模型上的公开方法实为
  零引用；因批准清单将其列为保留，移入 §5.6 待确认，本次不删。）
- **vulture 误报**：pydantic 校验器（golden.py / semantic/models.py 的
  `validate_*`，框架动态调用）、dataclass 字段、`ui_icons.icon` 的
  `color` / `stroke_width` 参数（文档注明"兼容签名"，刻意保留）。

### 5.6 扫描新发现——待用户另行确认，本次不删

- 依赖（requirements.txt，零 import 但需防传递依赖误判）：裸 `langchain==0.1.0`、
  `nltk`、`sqlparse`、`pydantic-settings`、`simple-ddl-parser`、`typer`。
  （langchain-community/core、rank-bm25、scikit-learn、faiss-cpu、dashscope 等确认保留。）
- `numpy` 被一方代码直接 import 但未声明（现靠传递依赖可用）→ 建议补声明。
- `config.py:138 STREAMLIT_SERVER_PORT`（删除需 config.py:138/202 +
  config_validation.py:57 三处联动）；`STREAMLIT_HEAD` 有测试引用，**保留**。
- `core/utils/__init__.py:5-7` re-export 块（可能是公开 API 面）。
- `core/sql/field_validator.py:371-374` `test_validator()` + `__main__` 演示
  （Neon 残留；若确认删除，NEON_DB_URL 随之完全死亡）。
- `core/graph_builder/models.py:84-89` `SchemaExtractResult._db_id_counter`
  字段 + `get_next_db_id` 方法（零引用，原误列保留清单）。

## 6. 目标 UI 架构（方案 A 落地）

```
app.py                  # 薄入口 ~150 行：page_config → 样式/状态/初始化
                        # → 侧栏 → 4 Tab 分发 → footer
app/
  ui_icons.py           # （已有）Fluent Color 内联 SVG 图标
  styles.py             # 全局 CSS 注入（原 app.py 260-330）
  state.py              # session state 初始化（原 331-350）
  bootstrap.py          # initialize_system（原 352-414）
  sidebar.py            # 品牌 logo + 侧栏（原 716-1026）
  model_config.py       # 模型配置面板 + _apply_* / _active_model_config /
                        # _reseed_model_widgets（原 415-714）
  pages/
    sql_generation.py   # Tab 1 SQL 生成（原 1036-1279）
    history.py          # Tab 2 执行历史（原 1280-1368）
    kg_builder.py       # （已有）Tab 3 知识图谱构建
    system_info.py      # Tab 4 系统信息（模型面板/治理/统计/日志）
    governance_settings.py  # （已有）治理设置
```

规则：
- 每个模块暴露 `render_*()` / `show_*()` 入口函数，与已有
  `show_kg_builder` / `show_governance_settings` 命名一致。
- 纯搬运 + 最小胶水：不改逻辑、不改 key、不改文案；模块级常量
  （LOGO_PATH、project_root 等）随使用方迁移。
- `core/` 不动（除 §5.2 死方法删除）。
- 拆分顺序：先 styles/state/bootstrap（无 UI 依赖）→ sidebar/model_config
  → 三个 Tab → app.py 收尾。每步跑一次相关 AppTest。

## 7. 工具链规范

- 新增 `pyproject.toml`：仅 `[tool.ruff]`（target py312，line-length 100，
  select = E4/E7/E9/F 起步，排除 python_deps/.venv/data/logs），让 README
  声称的 ruff 门禁真实可跑；不引入大规模风格整改（现有代码过不了严格规则
  的部分不在本次范围）。`[tool.pytest.ini_options]` 仅 testpaths=["tests"]。
- 修复 §5.3 的 6 处 F401 后，`ruff check` 对 select 范围内应零告警；
  若 E7 产生大量告警，则首版只启用 E4/E9/F，其余留待后续。

## 8. README 重写计划（基于实际代码）

1. **架构章节（新增）**：分层图（UI 层 app.py+app/ → 应用层
   core/app_context → 领域层 core 各子包 → 基础设施 config.py +
   MySQL/Neo4j/LLM/Embedding），目录树逐包一句话职责，自然语言查询
   数据流（检索 → 提示词 → LLM → SQLFluff 校验 → 正确性内核 → 执行 → 历史）。
   全部内容从实际代码核对，不凭印象。
2. **环境说明修正**：本机开发/验证环境 Python 3.12（.venv 实测 3.12.10）。
   部署示例改为版本中性（`PYTHON_BIN=/path/to/python3` 展示覆盖能力，不
   断言生产机版本——builder-check 问题 3，orchestrator 决策：不写无法
   核实的事实）；删除未经核实的"Python 3.9+"最低版本声明，改述为
   "在 Python 3.12 上开发验证，部署可经 PYTHON_BIN 指定解释器"。
3. **功能/版本描述对齐**：以 CHANGELOG 与代码为准核对 v1.4 特性表；
   删除对已删死代码的引用。**版本元数据决策（builder-check 问题 2，
   orchestrator 决策）**：本次为 housekeeping，不 bump 版本（README 保持
   v1.4）；CHANGELOG 追加 [Unreleased] 条目记录 Removed/Changed（CHANGELOG
   现仅有 Unreleased 段，无 v1.4 历史条目——README 版本历史段是 v1.4 的
   唯一记录，保留不动）。
4. **测试章节**：按实际 tests/ 结构更新（离线单测 + 缺配置自动跳过的
   集成测试），给出 `.venv` 下的 pytest / ruff 命令。
5. 保留现有截图（docs/screenshots/ 与代码现状一致）。

## 9. 验证计划

1. **基线**：改动前 `.venv/bin/python -m pytest tests -q` 记录
   pass/skip/fail；`.venv/bin/python -m ruff check` 记录现状。
2. 死代码删除后：pytest 计数与基线一致（除去被删的 Neon 测试）；
   `grep -rn` 确认被删名字全仓零残留。
3. UI 拆分后：pytest 全量一致；AppTest 四文件全绿；
   `.venv/bin/python -m streamlit run app.py --server.port 8502
   --server.headless true` 冒烟：`/_stcore/health` = ok，首页 200。
4. ruff check 零告警（select 范围内）。
5. README 逐节对照代码人工核对。
6. 不触碰 8501 运行实例；8502 验证实例用后即停。

## 10. 留给实现者的决策

- 模块内函数拆分粒度（如 system_info 内统计/日志是否再拆小函数）以
  可读性为准，不强制。
- §5.2 两处疑似死存储的最终取舍（复核零读取才删）。
- ruff 首版规则集若与现有代码冲突过大，按 §7 降级。
- git 提交切分（建议：死代码一刀、UI 拆分一刀、工具链+README 一刀），
  提交信息用中文 conventional commits。