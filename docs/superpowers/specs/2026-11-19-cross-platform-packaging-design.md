# 跨平台桌面打包 设计文档

日期：2026-11-19
状态：待确认（方向已认可：轻量安装包+首跑向导+LLM 前提）
前置依赖：SQLite 迁移完成（去 MySQL、自包含存储）后执行。本文档可先批准，执行排在迁移合并之后。

## 1. 意图

把 Streamlit text2sql 应用封装成 **Linux/Windows/macOS 可下载安装即用**的软件：
双击启动本地服务并自动开浏览器。用户已选形态＝PyInstaller 可执行 + 安装包
（Win .exe / Mac .app·.dmg / Linux AppImage）。

## 2. 用户已决策 / 控制器技术裁决

- 形态：PyInstaller onedir + 每 OS 安装包；GitHub Actions 矩阵构建（本机 macOS 可本地验证）。
- 数据目录：用户家目录可写位置（platformdirs），不捆进包体；SQLite 自包含。
- 首跑配置向导：设置 LLM（Ollama 地址或云端 API Key）、可选 Neo4j。
- v1 不代码签名（Mac Gatekeeper/Win SmartScreen 警告，文档说明右键打开；签名/公证后续）。
- **LLM 前提（用户已接受）**：包体不含 Ollama/模型；首跑需用户装 Ollama 拉 gemma4:E4B
  或填云端 API Key（向导引导）。Neo4j 默认关闭、可选连外部，不捆绑。
- 全内置 turnkey（捆 Ollama+模型+Neo4j，数 GB）不做 v1。

## 3. 现状约束（摸底）

- config.py：`load_dotenv()`（读 cwd 的 .env）；`PROJECT_ROOT=Path(__file__).parent`；
  INDEX_CACHE_DIR/LOG_FILE 相对 PROJECT_ROOT；迁移后 SQLITE_PATH 默认 data/text2sql.db。
- 启动：`python -m streamlit run app.py --server.headless true`（端口 8501）。
- 重原生依赖：faiss-cpu、scikit-learn、sqlfluff、streamlit、neo4j 驱动——PyInstaller
  需收集静态资源/原生库/隐藏导入；**不能跨 OS 交叉编译**，须每 OS 构建。
- NEO4J_ENABLED 默认 False（降级模式可无图谱运行）。

## 4. 目标 / 非目标 / 反目标

**目标**
- 三 OS 安装包，双击起服务+开浏览器，无需用户装 Python。
- 冻结态数据路径重定向到用户数据目录（SQLite/logs/index_cache/.env 可写）。
- 首跑向导配置 LLM；未配置时引导而非崩溃。
- CI 矩阵自动构建三 OS 产物并上传。
- macOS 本地产物实测可用（起服务、生成→SQLite 执行端到端）。

**非目标**
- 不捆绑 Ollama/模型/Neo4j（外部前提）。
- 不代码签名/公证（v1）；不做自动更新（v1）。
- 不改业务逻辑（仅打包层 + 冻结态路径适配）。
- 不追求原生 GUI 窗口（浏览器形态，用户已选）。

**反目标**
- 包内写数据到只读 bundle 路径致崩溃。
- 缺隐藏导入/静态资源致 frozen 启动失败。
- 未配置 LLM 时白屏/异常无引导。
- 文档宣称 turnkey 但实际需 Ollama 前提（须如实说明）。

## 5. 设计细节

### 5.1 冻结态路径适配（config.py 最小改动）
- 新增 DATA_DIR 解析：`getattr(sys, "frozen", False)` → platformdirs.user_data_dir("text2sql-agent")
  （Win %LOCALAPPDATA%/text2sql-agent、Mac ~/Library/Application Support/text2sql-agent、
  Linux ~/.local/share/text2sql-agent）；否则 PROJECT_ROOT/data（开发态不变）。
- SQLITE_PATH/LOG_FILE/INDEX_CACHE_DIR/SEMANTIC_MODEL_DIR 派生自 DATA_DIR；.env 从
  DATA_DIR 加载（load_dotenv(DATA_DIR/".env")）。semantic_models/ 首跑复制到 DATA_DIR
  （治理 .compiled 写 DATA_DIR，不写只读 bundle；治理本就 mysql-only 休眠）。种子文件
  data/seed_*.sql 作为 bundle 数据收集，SQLiteClient 从 bundle（_SEED_DIR）读种子初始化
  DATA_DIR 库（已实现）。
- 开发态行为逐字不变（frozen=False 走原路径）——既有 938+ 测试不受影响。

### 5.2 启动器（launcher.py，打包入口）
- 创建 DATA_DIR（含 logs/）；首跑无 .env→写默认模板（SQLITE_PATH、SQL_DIALECT=sqlite、
  NEO4J_ENABLED=false、LLM 占位）。
- 以编程方式起 Streamlit（frozen 下不能 `sys.executable -m streamlit`）：
  用 streamlit.web.bootstrap / cli._main_run 在进程内运行 app.py，或子进程调 bundled
  streamlit；设 server.headless=true、address=127.0.0.1、port=8501（占用则递增）。
- 服务就绪后 webbrowser.open(http://127.0.0.1:port)。
- PyInstaller 入口＝launcher.py（非 app.py）。

### 5.3 首跑向导
- 复用现有 model_config 面板（LLM + Embedding 两段）：app 检测未配置→引导。
- **持久化（Q1）**：向导/面板保存结果写 DATA_DIR/.env（明文，与现有 .env 一致），
  跨重启存活。打包层 config-writer helper，model_config 保存流程最小扩展（配置 plumbing，
  非 SQL/治理业务逻辑）；加持久化测试。
- **Embedding（Q3）**：向导同时配 LLM + Embedding。Ollama 前提＝拉两个模型
  （gemma4:E4B + bge-m3:latest）；纯云端＝API Key + DashScope text-embedding-v3（同 key）；
  无 Ollama 且未配云 embedding→TF-IDF 回退（降级，文档如实说明）。
- 可选 Neo4j 连接提示（默认关闭，图谱增强需外部 Neo4j）。
- 不新建独立 GUI 对话框（Streamlit 内引导，最小改动）。

### 5.4 PyInstaller 规格（text2sql.spec）
- onedir；入口 launcher.py；--name text2sql-agent。
- collect_all：streamlit（静态资源/组件）、faiss（原生库）、sqlfluff（规则/方言）、
  pydantic、langchain、neo4j、sklearn、nltk 数据。
- hiddenimports：streamlit 运行时动态导入、core/app 各模块、sqlglot 方言。
- datas：app/、core/、semantic_models/、data/seed_*.sql、assets/、schema.sql。
- Mac --windowed（.app，无终端）；Win/Linux 控制台可选（--noconsole 视调试）。
- 已知风险：Streamlit+PyInstaller 需迭代调 hook（静态资源路径、metadata）；
  faiss 原生库 per-OS；先 macOS PoC 跑通再矩阵。

### 5.5 安装包
- Mac：PyInstaller .app → create-dmg → .dmg（含 Applications 拖拽）。
- Win：PyInstaller dir → Inno Setup（或 NSIS）→ installer.exe（开始菜单/桌面快捷方式）。
- Linux：PyInstaller dir → appimage-builder/python-appimage → .AppImage。
- 各含 README 前提说明（Ollama/可选 Neo4j）+ 右键打开绕过签名警告指引。

### 5.6 CI 矩阵（.github/workflows/build.yml）
- triggers：tag v* / workflow_dispatch。
- matrix（v1 现代平台，用户已定）：macos-latest（Apple Silicon arm64）、
  windows-latest（x64）、ubuntu-22.04（glibc 2.35 _floor，兼容较新发行版）；
  setup-python 3.12；pip install -r requirements.txt + pyinstaller + 打包工具；
  pyinstaller text2sql.spec；制作安装包；upload-artifact（每 OS 产物）。
  Intel Mac（macos-13）/更旧 Linux/Win arm64 留后续。
- v1 不签名；release 附产物（后续）。

### 5.7 文档
- README 新增"下载安装"章节：三 OS 安装包获取、前提（Ollama 拉模型或云 Key、
  可选 Neo4j）、首跑向导、签名警告绕过、数据目录位置。
- 打包构建文档（docs/packaging.md）：本地构建步骤、CI、已知限制。

## 6. 验证计划
1. 开发态回归：冻结态路径改动后全量测试绿（frozen=False 不变）。
2. macOS PoC：pyinstaller 构建→双击 .app→服务起+浏览器开→未配置引导→
   配 Ollama/Key→自然语言生成 SQLite SQL→执行返回业务数据→历史落用户数据目录。
3. 数据目录核实：SQLite/logs/.env 在 user_data_dir，bundle 只读无写。
4. CI 矩阵三 OS 构建成功（产物可下载）；Win/Linux 产物冒烟（CI 内或人工）。
5. ruff 零。

## 7. 实现者决策
- Streamlit frozen 启动具体 API（bootstrap vs cli vs 子进程）按实测选定。
- PyInstaller hook 细节（collect 范围、hiddenimports）按启动报错迭代。
- 端口占用处理、首跑模板内容、向导措辞。
- 安装包工具具体配置（Inno Setup 脚本/AppImage recipe/dmg 布局）。
- git 提交切分（路径适配 / launcher+spec / 向导 / CI / 安装包脚本 / 文档）。

## 8. 风险与缓解
- PyInstaller+Streamlit+faiss bundling 高迭代风险 → macOS PoC 先行，跑通再矩阵；
  预留 hook 调试预算。
- 包体大（数百 MB，faiss/sklearn/streamlit）→ onedir 压缩分发，接受。
- 无签名 OS 警告 → 文档明确指引；签名留后续。
- Ollama 前提非 turnkey → 首跑向导+文档如实说明（用户已接受）。

## 9. builder-check 裁决（5 项）
- Q1 向导持久化：必须跨重启存活→写 DATA_DIR/.env；打包层 config-writer + model_config
  保存最小扩展（配置 plumbing，允许）；加持久化测试。
- Q2 治理写 bundle：SEMANTIC_MODEL_DIR 重定向 DATA_DIR + 首跑复制 semantic_models/；
  治理 mysql-only 休眠（sqlite 下 config 闸门阻止启用），不触发 bundle 写。
- Q3 Embedding：向导覆盖 LLM+Embedding；Ollama 拉两模型（gemma4:E4B+bge-m3）；
  纯云＝Key+DashScope embedding；TF-IDF 回退降级文档说明。
- Q4 平台范围（用户已定）：现代平台＝macos-latest arm64 + windows-latest x64 +
  ubuntu-22.04；Intel Mac/旧 Linux/Win arm64 后续。
- Q5 产品定位：v1＝自带示例数据自包含 demo（bundled 30 行）；不引导改 SQLITE_PATH
  指向任意库（避免种子注入污染）；接自己数据经 KG+外部 Neo4j 属高级/后续。