# 跨平台桌面打包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Streamlit text2sql 应用封装成 Linux/Windows/macOS 可下载安装即用的软件（PyInstaller 可执行+安装包，双击起本地服务自动开浏览器），冻结态数据落用户数据目录，首跑向导配 LLM+Embedding 并持久化。

**Architecture:** PyInstaller onedir 打包 launcher.py（进程内 streamlit.web.bootstrap 起服务）；config.py 冻结态感知（sys.frozen→platformdirs 用户数据目录）；GitHub Actions 矩阵三 OS 构建+安装包。macOS PoC 先行跑通再矩阵。v1 自带示例数据 demo、不签名、Ollama/云 Key 前提。

**Tech Stack:** Python 3.12、PyInstaller（构建期）、platformdirs（运行时）、streamlit 1.29.0（bootstrap）、create-dmg/Inno Setup/appimage-builder（安装包）、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-11-19-cross-platform-packaging-design.md`（权威，§5 细节/§9 裁决）

## Global Constraints

- 开发态行为逐字不变：sys.frozen=False 走原 PROJECT_ROOT/data 路径，既有 1072 测试不受影响。
- 冻结态数据全落用户数据目录（platformdirs.user_data_dir("text2sql-agent")）：SQLite/logs/index_cache/semantic_models/.env 可写；bundle 只读无写。
- 首跑向导配置持久化到 DATA_DIR/.env（跨重启）；LLM+Embedding 都配；Ollama 前提两模型（gemma4:E4B+bge-m3）或云 Key+DashScope embedding；TF-IDF 回退降级文档说明。
- v1 平台：macos-latest arm64 + windows-latest x64 + ubuntu-22.04；不签名（文档说明 Gatekeeper/SmartScreen 右键打开）；不自动更新。
- v1 demo 定位：自带示例数据，不引导改 SQLITE_PATH 指向任意库。
- Neo4j 可选外部（默认关）；不捆绑 Ollama/模型/Neo4j。
- 隔离 worktree（保护 8501）；worktree cp 主仓 .env；主仓 .venv/bin/python 绝对路径。8501 不动；PoC/冒烟用 8502 用后即停。
- 提交中文 conventional + Co-Authored-By: Claude Code <noreply@anthropic.com>。
- 行号快照按内容定位。

## Review Focus

1. **冻结态写只读 bundle 崩溃** → T1 frozen 路径测试 + T3 PoC 数据目录核实。
2. **frozen 启动缺隐藏导入/静态资源失败** → T3 PoC 实测启动+渲染+执行。
3. **首跑配置不持久（每次重启重配）** → T4 持久化测试（写 .env 跨重启）。
4. **未配置 LLM 白屏/崩溃** → T4 未配置引导测试 + T3 PoC 未配置渲染。
5. **开发态回归** → T1 后全量 1072 不变（frozen=False）。

---

### Task 1: 冻结态路径适配 + platformdirs 依赖

**Files:**
- Modify: `config.py`（DATA_DIR 解析 + SQLITE_PATH/LOG_FILE/INDEX_CACHE_DIR/SEMANTIC_MODEL_DIR/.env 派生）、`requirements.txt`（加 platformdirs）
- Create: `tests/test_frozen_paths.py`

**Interfaces:**
- Produces: `config.DATA_DIR`（frozen→platformdirs.user_data_dir("text2sql-agent")；else PROJECT_ROOT/"data"）；SQLITE_PATH/INDEX_CACHE_DIR/SEMANTIC_MODEL_DIR/LOG_FILE 派生自 DATA_DIR；load_dotenv(DATA_DIR/".env")。
- Consumes: platformdirs（新依赖）。

- [ ] **Step 1: 写测试（先失败）**

```python
# tests/test_frozen_paths.py
def test_dev_mode_uses_project_data(monkeypatch):
    # sys.frozen 不存在→DATA_DIR==PROJECT_ROOT/data；SQLITE_PATH 含 data/text2sql.db
def test_frozen_mode_uses_user_data_dir(monkeypatch):
    # monkeypatch sys.frozen=True + platformdirs.user_data_dir→tmp；重载 config→DATA_DIR==tmp；SQLITE_PATH/LOG_FILE/INDEX_CACHE_DIR/SEMANTIC_MODEL_DIR 均在 tmp 下
```

- [ ] **Step 2: 实现 config.py 冻结态适配**

import sys/platformdirs；`_FROZEN=getattr(sys,"frozen",False)`；`DATA_DIR=Path(platformdirs.user_data_dir("text2sql-agent")) if _FROZEN else PROJECT_ROOT/"data"`；SQLITE_PATH 默认 str(DATA_DIR/"text2sql.db")；INDEX_CACHE_DIR 默认 str(DATA_DIR/"index_cache")；SEMANTIC_MODEL_DIR 默认 str(DATA_DIR/"semantic_models")；LOG_FILE=DATA_DIR/"logs"/"app.log"（frozen）或 PROJECT_ROOT/"logs"/"app.log"（dev，保持原）；load_dotenv(DATA_DIR/".env")（frozen）或 load_dotenv()（dev）。env 覆盖仍优先。**dev 路径逐字不变**。requirements 加 platformdirs>=4。

- [ ] **Step 3: 跑测试通过 + 全量回归**

Run: `.venv/bin/python -m pip install platformdirs`；`-m pytest tests/test_frozen_paths.py tests -q` → 1072+新增 passed, 9 skipped（dev 不变）；ruff 零。

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(packaging): config 冻结态路径适配用户数据目录 + platformdirs

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 启动器 launcher.py + 首跑 .env 模板

**Files:**
- Create: `launcher.py`、`app/bootstrap_paths.py`（或 launcher 内 helper：DATA_DIR 初始化/种子复制/semantic_models 复制）、`tests/test_launcher.py`
- 参照: config.DATA_DIR、streamlit.web.bootstrap

**Interfaces:**
- Produces: `launcher.main()`：确保 DATA_DIR（含 logs/）存在；首跑无 .env→写默认模板（SQLITE_PATH、SQL_DIALECT=sqlite、NEO4J_ENABLED=false、LLM/EMBEDDING 占位）；frozen 时复制 bundle semantic_models→DATA_DIR/semantic_models（若缺）；进程内起 streamlit（bootstrap.run）；webbrowser.open。
- Consumes: T1 DATA_DIR。

- [ ] **Step 1: 写测试（先失败）**

```python
def test_first_run_writes_env_template(tmp_path, monkeypatch):
    # DATA_DIR=tmp（无 .env）→ensure_data_dir 写 .env 含 SQL_DIALECT=sqlite/SQLITE_PATH/NEO4J_ENABLED=false
def test_existing_env_not_overwritten(tmp_path):
    # 已有 .env→不覆盖
def test_semantic_models_copied_when_frozen(tmp_path, monkeypatch):
    # frozen + bundle semantic_models 存在 + DATA_DIR 缺→复制
```

- [ ] **Step 2: 实现 launcher + helper**

ensure_data_dir()：mkdir DATA_DIR/logs；无 .env 写模板；frozen 复制 semantic_models（bundle 路径 sys._MEIPASS 或 onedir _internal）。launch()：设 streamlit config（server.headless=True/address=127.0.0.1/port=8501 占用递增），bootstrap.run(main_script=app.py 路径, ...)；就绪后 webbrowser.open(http://127.0.0.1:port)。app.py 路径 frozen→bundle 内 datas。端口探测 socket bind。

- [ ] **Step 3: 跑测试通过 + 全量回归 + Commit**

Run: `-m pytest tests/test_launcher.py tests -q` → 绿；ruff 零。
```bash
git commit -m "feat(packaging): launcher 启动器 + 首跑 .env 模板与数据目录初始化

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: PyInstaller spec + macOS PoC（高风险迭代）

**Files:**
- Create: `text2sql.spec`、`requirements-build.txt`（pyinstaller）、`docs/packaging.md`（构建步骤草稿）
- 参照: launcher.py、app/、core/、semantic_models/、data/seed_*.sql、assets/

**Interfaces:**
- Produces: macOS .app（dist/text2sql-agent.app）双击起服务+开浏览器+渲染+未配置引导+配 LLM 后生成→SQLite 执行。
- Consumes: T1/T2。

- [ ] **Step 1: 写 spec + 装 pyinstaller**

requirements-build.txt: pyinstaller>=6。text2sql.spec：Analysis(launcher.py)，collect_all("streamlit")（静态/组件/metadata），collect_dynamic_libs("faiss")，collect_data_files("sqlfluff")+collect_all("sqlfluff")，collect_all("pydantic")/langchain/neo4j/sklearn，hiddenimports（streamlit 运行时动态导入、core/app 模块、sqlglot 方言），datas=[(app/),(core/),(semantic_models/),(data/seed_*.sql),(assets/),(schema.sql)]，onedir，Mac BUNDLE(--windowed .app)。

- [ ] **Step 2: macOS 构建 + 迭代调试**

Run: `.venv/bin/python -m pip install -r requirements-build.txt`；`-m PyInstaller text2sql.spec --noconfirm`。启动 dist 产物→修缺失隐藏导入/静态资源路径（streamlit static、faiss lib、sqlfluff rules）直到：服务起、浏览器开、首页渲染无异常、未配置 LLM 显示引导。

- [ ] **Step 3: PoC 端到端验证**

配 Ollama（若在跑）或云 Key→自然语言查询→生成 SQLite SQL→执行返回业务数据（risk_blacklist 3 行）→历史落 DATA_DIR/text2sql.db。核实数据全在用户数据目录（bundle 只读无写）。记录迭代修复的 hook 细节到 docs/packaging.md。

- [ ] **Step 4: 全量回归（dev 不变）+ Commit**

Run: `-m pytest tests -q` → 1072+ 不变；ruff 零。
```bash
git commit -m "feat(packaging): PyInstaller spec + macOS PoC 构建跑通

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 首跑向导（LLM+Embedding 持久化）

**Files:**
- Modify: `app/model_config.py`（保存流程扩展写 DATA_DIR/.env）、`app/pages/system_info.py`（未配置引导）、`core/config_persistence.py`（新 helper：write_env_config）
- Create: `tests/test_config_persistence.py`

**Interfaces:**
- Produces: config_persistence.write_env_config(updates: dict)→读 DATA_DIR/.env 合并写回（保留其余键，原子写）；model_config 保存按钮调它持久化 LLM+Embedding；未配置检测→引导文案。
- Consumes: T1 DATA_DIR、T2 .env 模板。

- [ ] **Step 1: 写测试（先失败）**

```python
def test_write_env_config_persists_and_preserves(tmp_path, monkeypatch):
    # DATA_DIR/.env 有 SQL_DIALECT=sqlite；write_env_config({"LLM_API_KEY":"x"})→文件含新 key 且 SQL_DIALECT 保留
def test_config_survives_reload(tmp_path):
    # 写后重载 config→LLM_API_KEY 生效（跨重启模拟）
def test_unconfigured_llm_guidance():
    # 无 key 且 Ollama 不可达→system_info 显示引导（AppTest）
```

- [ ] **Step 2: 实现持久化 + 向导**

config_persistence.write_env_config：解析现有 .env（键值），合并 updates，原子写（tmp+rename）。model_config _apply_llm_config/_apply_embedding_config 成功后调 write_env_config 持久化（provider/model/api_key/base_url）。system_info 检测未配置→引导（Ollama 两模型或云 Key+DashScope embedding；TF-IDF 回退说明）。

- [ ] **Step 3: 跑测试通过 + 全量回归 + Commit**

Run: `-m pytest tests/test_config_persistence.py tests -q` → 绿；ruff 零。
```bash
git commit -m "feat(packaging): 首跑向导 LLM+Embedding 配置持久化到 .env

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 安装包脚本（dmg / Inno Setup / AppImage）

**Files:**
- Create: `packaging/macos/dmg.sh`（create-dmg）、`packaging/windows/installer.iss`（Inno Setup）、`packaging/linux/AppImageBuilder.yml`、`packaging/README_FIRST_RUN.txt`（前提+签名警告指引，各包内置）

**Interfaces:**
- Produces: 三 OS 安装包制作脚本（输入 PyInstaller dist 产物）。
- Consumes: T3 spec/dist 布局。

- [ ] **Step 1: 写三 OS 安装包脚本**

macOS dmg.sh：create-dmg --window-size ... --icon ... dist/text2sql-agent.app→.dmg（Applications 拖拽）。Windows installer.iss：Inno Setup [Setup]/[Files]（dist/text2sql-agent/*）/[Icons]（桌面/开始菜单快捷方式）→installer.exe。Linux AppImageBuilder.yml：appimage-builder recipe（AppDir 从 dist，entrypoint launcher）→.AppImage。各含 README_FIRST_RUN.txt（Ollama 两模型/云 Key、可选 Neo4j、Gatekeeper/SmartScreen 右键打开、数据目录位置）。

- [ ] **Step 2: macOS dmg 本地验证**

Run: `bash packaging/macos/dmg.sh`（需 create-dmg，brew install）→.dmg 挂载验证 .app 可起。Win/Linux 脚本语法校验（CI 实测）。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(packaging): 三 OS 安装包脚本（dmg/Inno Setup/AppImage）+ 首跑说明

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: CI 矩阵（GitHub Actions）

**Files:**
- Create: `.github/workflows/build.yml`

**Interfaces:**
- Produces: tag v*/workflow_dispatch 触发，matrix 三 OS 构建+安装包+upload-artifact。
- Consumes: T3 spec、T5 脚本。

- [ ] **Step 1: 写 workflow**

matrix：[macos-latest, windows-latest, ubuntu-22.04]；setup-python 3.12；pip install -r requirements.txt -r requirements-build.txt；pyinstaller text2sql.spec；OS-specific 安装包（mac dmg.sh / win iscc installer.iss / linux appimage-builder）；upload-artifact（每 OS 产物）。ubuntu 装 appimage-builder 依赖；windows 装 Inno Setup（choco）；mac 装 create-dmg（brew）。v1 不签名。

- [ ] **Step 2: YAML 校验 + Commit**

Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml'))"` → 合法。（实际构建在 GitHub 跑；本地 macOS 已 PoC。）
```bash
git commit -m "ci(packaging): GitHub Actions 三 OS 构建矩阵 + 安装包产物

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 文档（README 下载安装 + 构建指南）

**Files:**
- Modify: `README.md`（下载安装章节）、`docs/packaging.md`（完善构建指南）

**Interfaces:**
- Consumes: T3-T6 实际产物/步骤。

- [ ] **Step 1: 写文档**

README 新增"下载安装"：三 OS 安装包获取（Releases）、前提（Ollama 拉 gemma4:E4B+bge-m3 或云 Key+DashScope embedding；可选 Neo4j）、首跑向导、签名警告绕过（Mac 右键打开/Win SmartScreen 更多信息仍运行）、数据目录位置（platformdirs 三 OS 路径）、v1 demo 定位。docs/packaging.md：本地构建步骤（pip install build deps、pyinstaller、各 OS 安装包）、CI 说明、已知限制（不签名/不自动更新/包体大/LLM 前提）、PoC 迭代的 hook 细节。基于实际代码/产物，不宣称 turnkey。

- [ ] **Step 2: claim-check + Commit**

文档声明对照实际核实（路径/命令/前提）。
```bash
git commit -m "docs(packaging): README 下载安装章节 + 构建指南

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: 终验 + 整支审查 + 合并（控制器）

**Files:** 无新改动。

- [ ] **Step 1: 终验**

dev 全量绿（1072+新增）；ruff 零；macOS PoC .app 端到端（起服务→未配置引导→配 LLM→生成 SQLite SQL→执行 3 行→历史落用户数据目录）；数据目录核实（bundle 只读）；CI YAML 合法。8501 不动；8502/PoC 用后即停。

- [ ] **Step 2: 整支对抗审查工作流**

Workflow 维度（冻结态路径安全/启动器与持久化/PyInstaller 产物完整性/安装包与 CI/文档准确/dev 回归）并行审查+逐条对抗验证。confirmed 单一修复波+scoped re-review。

- [ ] **Step 3: 合并回 main + 推送**

superpowers:finishing-a-development-branch：合并→测试→清理 worktree/分支→推送（用户决策）。报告最终状态+裁决清单。