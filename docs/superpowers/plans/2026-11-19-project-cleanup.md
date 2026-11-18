# 项目整理与架构规范 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除经确认的死代码、把 1492 行的 app.py 拆成薄入口 + 职责模块（行为不变）、落地 ruff 门禁、基于实际代码重写 README（含架构章节）。

**Architecture:** 方案 A——只动 UI 层。core/ 已模块化，仅删其中零引用死方法。app.py 按已有 app/pages/ 模式拆为 styles/state/bootstrap/sidebar/model_config + 三个 Tab 页。934 个既有测试是行为不变的 characterization 安全网。

**Tech Stack:** Python 3.12（.venv：pytest 7.4.3 / ruff 0.15.20 / streamlit 1.29.0）、Streamlit AppTest、vulture/grep 死代码验证。

**Spec:** `docs/superpowers/specs/2026-11-19-project-cleanup-design.md`

## Global Constraints

- 行为完全不变：widget key、session_state key、渲染顺序、CSS、文案逐字保持；代码搬运不做任何"顺手改进"。
- 删除判据：定义之外零引用（含测试、脚本、YAML/JSON/MD/SH）。**验证工作流 `wf_bd31cc53-762` 判为 alive/uncertain 的候选一律不删**；执行 Task 1/2 前必须先读该工作流结果并据此裁剪清单。
- 基线：`.venv/bin/python -m pytest tests -q` → **934 passed, 16 skipped, 0 failed**。每个 Task 结束跑全量，计数只允许按该 Task 明确删除的测试数减少。
- `st.set_page_config` 必须是 app.py 第一个 st 调用；`inject_icon_styles()` 紧随其后（原 258 行位置）。
- 在隔离 worktree 中执行（保护 8501 运行实例）；worktree 内先 `cp /Users/rgj/PycharmProjects/text2sql_agent/.env .`；用主仓 `.venv/bin/python` 绝对路径跑测试。不重启/不触碰 8501；冒烟用 8502，用后即停。
- 不动 `text2sql_agent_server_*.zip` 用户备份；不升级依赖。
- app.py 行号均指原始 HEAD（ed2eab7a）版本，随任务推进会漂移——**用 section 注释标记和函数名定位，不要信行号**。
- 提交信息：中文 conventional commits，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## Review Focus

1. **搬运中 widget key / 渲染顺序漂移** → Task 4 第一步存 key 清单，Task 6 末 diff 必须为空（步骤内有脚本）。
2. **被删名字存在动态/字符串引用**（getattr、dispatch、配置）→ Task 1/2 的零残留 grep + 工作流验证闸门。
3. **新 app 模块反向 import app.py 造成循环** → Task 6 `tests/test_architecture.py::test_no_cycle_to_entry`。
4. **page_config 顺序 / 自定义 CSS 丢失**（测试不直接断言视觉）→ Task 6 `test_custom_css_injected` + 四个 AppTest 文件全绿。
5. **README 描述与代码分叉** → Task 8 的 claim-check 工作流逐节对照代码。

---

### Task 1: 删除 Neon/Qwen 旧实验链

**Files:**
- Delete: `app_neon.py`、`core/llm/qwen_generator.py`（连同 `core/llm/` 目录）、`core/knowledge/neon_knowledge.py`、`tests/test_neon_text2sql.py`、`tests/test_llm_integration.py`
- Modify: `README.md`（外科式：删 153-154 tests 树中两个 Neon 测试行、250-254 Neon 运行命令/迁移注记；299-302 NEON_DB_URL 表项改写为"field_validator.py 手动演示用"）
- **保留 `env.example` 的 NEON_DB_URL**（验证发现活消费者：`core/sql/field_validator.py:374` `__main__` 演示经 os.getenv 读取）
- Untrack: `llm_test_report.json`（`git rm --cached`，本地保留）

**整组删除依据**：工作流按字面规则判两测试文件 alive（README 提及 + pytest 收集），但验证 notes 确认其对活模块零覆盖损失，且用户已批准 §5.1 整组删除；README 引用同步清除后条件满足。

**Interfaces:**
- Consumes: 工作流 `wf_bd31cc53-762` 的 `neon-chain` 组 verdicts（执行闸门）
- Produces: 无（纯删除）

- [ ] **Step 1: 读验证工作流结果，裁剪清单**

读工作流返回的 `verified` 中 group="neon-chain" 的 verdicts 与 notes。任何 alive/uncertain 项移出本任务。特别核对 notes：两个死测试文件是否含对活模块的测试（若有，把那些测试函数迁到合适的活测试文件再删文件）。

- [ ] **Step 2: 记录被删测试的基线状态**

Run: `.venv/bin/python -m pytest tests/test_neon_text2sql.py tests/test_llm_integration.py -q`
Expected: 2 个测试，记录 passed/skipped 各几个（预期 2 skipped）。记 `P0/S0`。

- [ ] **Step 3: 删除文件 + README 外科编辑**

`git rm app_neon.py core/llm/qwen_generator.py core/knowledge/neon_knowledge.py tests/test_neon_text2sql.py tests/test_llm_integration.py`；删 `core/llm/` 残留目录（含 __pycache__）；按 Files 节编辑 README.md 三处；`git rm --cached llm_test_report.json`。**不动 env.example。**

- [ ] **Step 4: 零残留 grep**

Run: `grep -rn "app_neon\|qwen_generator\|neon_knowledge\|QwenMaxLLM\|generate_sql_with_qwen\|Neo4jKnowledgeRetriever\|build_dynamic_prompt\|test_neon_text2sql\|test_llm_integration" --include="*.py" --include="*.sh" --include="*.md" --include="*.yaml" --include="*.json" app.py app/ core/ config.py scripts/ tests/ eval/ env.example semantic_models/ README.md CHANGELOG.md`
Expected: 零命中（docs/superpowers/ 历史设计文档除外；NEON_DB_URL 不在检查范围——它保留）。

- [ ] **Step 5: 全量回归**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `934-P0 passed, 16-S0 skipped, 0 failed`（预期 934 passed, 14 skipped）。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: 删除 Neon/Qwen 旧实验链死代码

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 删除 core 层零引用死成员

**Files:**
- Modify: `core/knowledge/neo4j_client.py`、`core/history/mysql_client.py`、`core/retrieval/bm25_tfidf.py`、`core/sql/field_validator.py`、`core/sql/validator.py`、`core/sql/dialect_detector.py`、`core/graph_builder/models.py`、`core/graph_builder/loader/neo4j_writer.py`、`core/embedding_factory.py`、`core/history/identity.py`、`core/chain/prompts.py`

**Interfaces:**
- Consumes: 工作流各组 verdicts（闸门）；spec §5.2 清单
- Produces: 无公开 API 变化（被删成员全部零引用）

- [ ] **Step 1: 按工作流 verdicts + 政策细化裁剪清单**

工作流最终判定已并入 spec §5.2：4 个仅因历史文档叙述被判 alive 的成员（`get_all_nodes`、`get_node_by_name`、`save_feedback`、`self.linter`）经 orchestrator 政策细化（历史叙述≠使用引用，代码/测试调用方双重 grep 为零）重新归类 dead，**纳入删除**。其余 alive/uncertain 一律保留并在完成报告列出。两处死存储（`node_index`、`self.linter`）验证确认零读取，删除。

- [ ] **Step 2: 逐文件删除成员**

清单（以裁剪后为准）：
- neo4j_client.py: `execute_query_async`、`get_all_nodes`、`get_table_nodes`、`get_column_nodes`、`get_node_by_name`、`sync_metadata_to_mysql`；**传递性孤儿**：删 execute_query_async 后 vestigial 的 async-driver 机制（`self.async_driver` 初始化 ~:68、AsyncGraphDatabase 创建 ~:91-100、teardown ~:128-136、async import ~:15-17）——读取方仅剩 teardown 与已删方法，整体移除
- mysql_client.py: `save_feedback`
- bm25_tfidf.py: `preprocess`、`retrieve_tables`、`retrieve_columns`、`node_index` 赋值（验证确认零读取）
- field_validator.py: `suggest_fix`、`_get_column_name`、`_get_table_name`（先确认本文件内无自调用；勿与 join_extractor 的 `_get_table_name_from_node` 混淆；**不动 `test_validator()`/`__main__` 演示**——它是 NEON_DB_URL 的活消费者，属 §5.6 待确认项）
- validator.py: `get_violation_types`、`_extract_tables`、`self.linter` 赋值（验证确认零读取，实际 lint 走 sqlfluff.lint() 顶层 API ~:188）；搁浅的 `from sqlfluff.core import Linter` import 一并清理（先确认无其他使用）
- dialect_detector.py: `get_all_databases`、`refresh_metadata`
- graph_builder/models.py: `get_tables_by_database`、`get_columns_by_table`、`to_dict`（**不动 `get_next_db_id`/`_db_id_counter` 字段**——批准清单列为保留，属 §5.6 待确认项）
- neo4j_writer.py: `clear_graph`、`get_table_details`
- embedding_factory.py: `get_cache_size`
- history/identity.py: `retrieval_fields`
- chain/prompts.py: `create_validation_messages`；`sql_generation_template`/`knowledge_format_template`/`query_rewrite_template` 三属性及 `__init__` 中对应构造语句；**传递性孤儿**（critic 确认死链）：`sql_validation_template` 赋值、`_get_validation_template`、`_get_knowledge_format`、`_get_rewrite_template`

删除方法时连同其 docstring/装饰器整体删除；产生的未使用 import 一并清理。**prompts.py 删除后 `tests/test_offline.py` 必须仍绿**（其对 5 个字面量的断言 critic 已核全部存活）。

- [ ] **Step 3: 零残留 grep + 全量回归**

对每个被删名字跑全仓 grep（范围同 Task 1 Step 4），零命中。
Run: `.venv/bin/python -m pytest tests -q`
Expected: 与 Task 1 结束时计数完全一致。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: 删除 core 层零引用死方法

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 仓库卫生

**Files:**
- Untrack（本地保留）: `logs/app.log`、`logs/app.2026-03-21_21-24-09_820214.log`、`.idea/` 下全部 6 个跟踪文件、**`.env`（安全项：含 4 处凭据却被 git 跟踪，远程 GitHub）**
- Delete: `tmp_smoke/`（未跟踪）、`docs/project_overview.html`（git rm，2026-05-18 过时全景页）

**Interfaces:** 无代码依赖。

- [ ] **Step 1: 执行清理**

`git rm --cached .env logs/app.log "logs/app.2026-03-21_21-24-09_820214.log" .idea/.gitignore .idea/inspectionProfiles/profiles_settings.xml .idea/misc.xml .idea/modules.xml .idea/text2sql_agent.iml .idea/vcs.xml`；`git rm docs/project_overview.html`；`rm -rf tmp_smoke/`。确认 .gitignore 已覆盖 .env、logs/*.log、.idea/（现状已覆盖，不改）。**注意：untrack 不消除 git 历史中的凭据——完成报告必须向用户提示轮换凭据；历史清除（filter-repo/BFG）属破坏性操作，须用户另行批准，本次不做。**

- [ ] **Step 2: 验证**

Run: `git status --porcelain` → 无 logs/.idea 跟踪残留；`.venv/bin/python -m pytest tests -q` → 计数不变。
Run: `grep -rn "project_overview" --include="*.md" --include="*.py" . | grep -v .venv | grep -v python_deps` → 零命中（有引用则先改引用）。

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: 清理 git 跟踪的运行时产物与过时文档

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 抽取 styles / state / bootstrap

**Files:**
- Create: `app/styles.py`、`app/state.py`、`app/bootstrap.py`
- Modify: `app.py`（原 260-330 CSS 段、331-349 会话状态段、352-413 `initialize_system` 定义）

**Interfaces:**
- Produces:
  - `app.styles.inject_global_styles() -> None`
  - `app.state.init_session_state() -> None`
  - `app.bootstrap.initialize_system() -> bool | None`（原签名原返回值：成功 True 并写 session_state.app_context/initialized；失败 None 并写 initialization_error）
- Consumes: config 常量（bootstrap 需要 MYSQL_*、MYSQL_POOL_SIZE、FEW_SHOT_*）、`core.app_context.ApplicationContext`、loguru logger

- [ ] **Step 1: 存 widget key 基线清单（Review Focus #1）**

在 worktree 根目录运行，输出存 `/tmp/keys_before.json`：

```python
# /tmp/dump_keys.py —— 在 worktree 根目录用主仓 .venv/bin/python 运行
# 复用 test_model_config_panel 的密封启动模式（FakeContext 预播种，不触真实 DB）
import json, sys
sys.path.insert(0, ".")
from tests.test_model_config_panel import FakeContext, _base_config, _launch
at = _launch(FakeContext(_base_config()))
keys = []
for kind in ("button","checkbox","radio","selectbox","multiselect","slider",
             "text_input","text_area","number_input","date_input","time_input",
             "file_uploader","color_picker","toggle"):
    els = getattr(at, kind, None)
    if els is not None:
        keys += [f"{kind}:{el.key}" for el in els]
print(json.dumps(sorted(keys), ensure_ascii=False))
```

- [ ] **Step 2: 创建三个模块（纯搬运）**

- styles.py：原"自定义 CSS 样式"段整段 st.markdown(`<style>…`) 包进 `inject_global_styles()`。`inject_icon_styles()` 调用**留在 app.py 原位**（page_config 之后）。
- state.py：6 个 `if 'X' not in st.session_state` 块（initialized/session_id/app_context/history/last_sql/last_result）原样包进 `init_session_state()`，uuid import 随迁。
- bootstrap.py：`initialize_system()` 函数体逐字搬运，所需 config import 随迁。
- app.py：三段原位替换为 import + 调用（`inject_global_styles()`、`init_session_state()`；initialize_system 的调用点在侧栏内，Task 5 处理，本任务 app.py 顶部 `from app.bootstrap import initialize_system` 保持侧栏代码可用）。

- [ ] **Step 3: 回归**

Run: `.venv/bin/python -m pytest tests -q` → 计数不变；整 app AppTest（test_model_config_panel）与页面级 AppTest（test_governance_panel）全绿（builder-check 纠正：test_regressions/test_graph_builder 不用 AppTest，monkeypatch core）。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(ui): 抽取样式/会话状态/系统初始化模块

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 抽取 sidebar / model_config

**Files:**
- Create: `app/sidebar.py`、`app/model_config.py`
- Modify: `app.py`（原 415-714 模型配置段、716-1026 侧栏段）、`tests/test_model_config_panel.py`（源码断言改读新模块）

**Interfaces:**
- Produces:
  - `app.sidebar.render_sidebar() -> None`（内含私有 `_render_sidebar_logo()`、`get_knowledge_graph_template() -> dict`——后者仅侧栏下载按钮使用，随迁保持原名）
  - `app.model_config.render_model_config_panel() -> None`（原 `_render_model_config_panel` 去下划线公开化；私有 helper `_apply_llm_config(provider, model, api_key, base_url) -> tuple[bool, str]`、`_apply_embedding_config(provider, model, api_key) -> tuple[bool, str]`、`_active_model_config() -> dict`、`_reseed_model_widgets(prefix) -> None` 与常量 `_CONFIG_LOG_HINT` 原名随迁）
- Consumes: `app.bootstrap.initialize_system`（侧栏 801 行调用点）；config 常量（NEO4J_ENABLED、LLM_*、EMBEDDING_* 等按实际使用随迁）；`app.ui_icons`；LOGO_PATH/project_root 常量随侧栏迁移（app/ 下用 `Path(__file__).resolve().parent.parent`）

- [ ] **Step 1: 搬运侧栏段**

`_render_sidebar_logo` + `get_knowledge_graph_template` + 整个 `with st.sidebar:` 块 → `render_sidebar()` 函数体（with 块保留）。app.py 原位替换为 `from app.sidebar import render_sidebar` + `render_sidebar()`。LOGO_ICON_PATH 留在 app.py（page_config 用）。

- [ ] **Step 2: 搬运模型配置段**

415-714 整段 → app/model_config.py；入口改名 `render_model_config_panel`；tab4 内调用点（原 1446）改为 `from app.model_config import render_model_config_panel` + 调用。

- [ ] **Step 3: 更新源码级断言测试**

`tests/test_model_config_panel.py` 的 `test_no_stale_1536_embedding_dim_fallback`：`APP_PY.read_text` 改为 `(PROJECT_ROOT / "app" / "model_config.py").read_text(encoding="utf-8")`，断言内容不变。APP_PY 常量保留（_launch 仍用）。

- [ ] **Step 4: 回归**

Run: `.venv/bin/python -m pytest tests -q` → 计数不变。重点：test_model_config_panel.py 全绿（密钥不回显、恢复默认、状态卡片）。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(ui): 抽取侧栏与模型配置面板

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 拆分三个 Tab，app.py 收敛为薄入口

**Files:**
- Create: `app/pages/sql_generation.py`、`app/pages/history.py`、`app/pages/system_info.py`、`tests/test_architecture.py`
- Modify: `app.py`（tab1 原 1037-1277、tab2 原 1281-1366、tab4 原 1374-1482 的 with 块体）

**Interfaces:**
- Produces:
  - `app.pages.sql_generation.show_sql_generation() -> None`
  - `app.pages.history.show_history() -> None`
  - `app.pages.system_info.show_system_info() -> None`
- Consumes: `app.model_config.render_model_config_panel`、`app.pages.governance_settings.{show_governance_settings,current_governance_config}`、`app.pages.kg_builder.show_kg_builder`（tab3 不动）

- [ ] **Step 1: 搬运三个 Tab 体**

各 `with tabN:` 块体去一层缩进包进对应 `show_*()`；块内局部 import（如 governance_settings）随迁；所需 config/core import 按实际使用随迁。**已知跨 Tab 依赖：tab4 使用的 `ctx` 定义在 tab1 块内（`ctx = st.session_state.app_context`）——`show_system_info()` 函数体开头必须补上这同一行，使其自持；tab2 已确认自包含。**app.py 保留：imports、page_config、inject_icon_styles、inject_global_styles、init_session_state、主标题两行、`st.tabs([...])`（标签文案逐字不变）、`with tabN: show_*()`、footer。目标 ≤250 行。

- [ ] **Step 2: 写架构守护测试**

```python
# tests/test_architecture.py
"""架构守护：app.py 薄入口 + 模块入口 + 无循环 import + CSS 注入。"""
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]

def test_app_entry_is_thin():
    assert len((ROOT / "app.py").read_text(encoding="utf-8").splitlines()) <= 250

def test_ui_modules_expose_entry_points():
    entries = {
        "app.styles": "inject_global_styles",
        "app.state": "init_session_state",
        "app.bootstrap": "initialize_system",
        "app.sidebar": "render_sidebar",
        "app.model_config": "render_model_config_panel",
        "app.pages.sql_generation": "show_sql_generation",
        "app.pages.history": "show_history",
        "app.pages.system_info": "show_system_info",
    }
    for mod, fn in entries.items():
        assert callable(getattr(importlib.import_module(mod), fn)), f"{mod}.{fn}"

def test_no_cycle_to_entry():
    for p in list((ROOT / "app").glob("*.py")) + list((ROOT / "app" / "pages").glob("*.py")):
        src = p.read_text(encoding="utf-8")
        assert "from app import" not in src and "import app\n" not in src, p

def test_custom_css_injected():
    # 密封启动：复用 test_model_config_panel 的 FakeContext 模式，不依赖真实 DB
    from tests.test_model_config_panel import FakeContext, _base_config, _launch
    at = _launch(FakeContext(_base_config()))
    assert any(".main-title" in m.value for m in at.markdown)
```

- [ ] **Step 3: 回归 + key 清单 diff（Review Focus #1）**

Run: `.venv/bin/python -m pytest tests -q` → 计数不变（新增 4 个架构测试 → passed +4）。
Run: `.venv/bin/python /tmp/dump_keys.py > /tmp/keys_after.json && diff /tmp/keys_before.json /tmp/keys_after.json` → 无差异。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(ui): 拆分三个 Tab 页面，app.py 收敛为薄入口

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: pyproject.toml 落地 ruff 门禁

**Files:**
- Create: `pyproject.toml`

**Interfaces:** 无代码接口。

- [ ] **Step 1: 创建配置**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
extend-exclude = ["python_deps", ".venv", "data", "logs", "tmp_smoke"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 跑 ruff 并修复**

Run: `.venv/bin/python -m ruff check .`
Expected: builder-check 已实测该规则集**恰好 6 处 F401**（spec §5.3 清单）、无其他告警——修复后零告警，无需降级。若出现额外告警则按规则修；E7 告警 >20 处才按 spec §7 降级并注明。**不做大规模风格整改。**

- [ ] **Step 3: 回归 + Commit**

Run: `.venv/bin/python -m pytest tests -q` → 计数不变。

```bash
git add -A && git commit -m "build: 新增 pyproject.toml 落地 ruff 门禁

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: 基于实际代码重写 README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 6 后的最终目录结构；CHANGELOG.md；core/ 各包实际代码

- [ ] **Step 1: 重写 README + CHANGELOG 条目**

保留：品牌头图、功能展示截图（docs/screenshots/ 7 张）、出品信息、README 版本历史段（v1.4 的唯一记录）。重写/新增：
1. **架构章节**：分层图（UI 层 app.py+app/ → 应用层 core/app_context.ApplicationContext → 领域层 core 各子包 → 基础设施 config.py + MySQL/Neo4j/LLM/Embedding）；目录树逐包一句话职责（从实际代码核对）；自然语言查询数据流（混合检索 BM25+FAISS → 提示词 → LLM → SQLFluff 校验 → 正确性内核 → 执行 → 历史）。
2. **环境说明**：本机开发验证 Python 3.12（.venv 实测 3.12.10）；部署示例版本中性（`PYTHON_BIN=/path/to/python3`，不断言生产机版本）；删除未核实的"Python 3.9+"声明；保留 start_server.sh 参数表。
3. **功能/版本表**：对照代码核对 v1.4 特性；**不 bump 版本**（housekeeping，README 保持 v1.4）；确认 Task 1 的 Neon 引用外科编辑无遗漏。
4. **测试章节**：`.venv/bin/python -m pytest tests -q`、ruff 命令；说明集成测试由各文件内 TEXT2SQL_RUN_DB_TESTS 开关 gating（默认关）。
5. **CHANGELOG.md**：追加 [Unreleased] 条目（Removed：Neon 实验链/零引用死方法；Changed：UI 分层/README；Added：pyproject.toml/架构守护测试；Security：.env 停止跟踪）。不改历史条目。
6. 版本号表述以 README v1.4 为准（app.py footer 的 v1.0 文案不改——行为不变约束）。

- [ ] **Step 2: claim-check 工作流验证（Review Focus #5）**

用 Workflow 工具起验证流水线：把 README 拆成节，每节一个代理对照实际代码逐条核实声明（目录树存在性、数据流顺序、特性表、命令可跑性），返回 confirmed/wrong 清单。wrong 项修到零。

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "docs: 基于实际代码重写 README（含架构章节）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: 终验与整支审查

**Files:** 无新改动（验证任务）。

- [ ] **Step 1: 全量终验**

Run: `.venv/bin/python -m pytest tests -q` → 938 passed（934+4 架构测试）, 14 skipped, 0 failed。
Run: `.venv/bin/python -m ruff check .` → 零告警。
冒烟：worktree 内 `.venv/bin/python -m streamlit run app.py --server.port 8502 --server.headless true`（后台）→ `curl -s http://localhost:8502/_stcore/health` = ok、首页 HTTP 200 → 停掉 8502 进程。8501 全程不动。

- [ ] **Step 2: 整支对抗审查工作流**

用 Workflow 起整支 review：diff main...HEAD 按维度（行为保持/key 与顺序漂移、死代码删除安全性、README 准确性、架构守护有效性）并行审查 + 逐条对抗验证。confirmed 问题修复后重跑 Step 1。

- [ ] **Step 3: 合并回 main**

用 superpowers:finishing-a-development-branch skill 合并 worktree 分支。合并后 8501 实例在下次交互时热重载新代码；向用户报告最终计数与访问地址。