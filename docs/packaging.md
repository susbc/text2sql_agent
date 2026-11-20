# 打包构建指南（PyInstaller）

形态：PyInstaller **onedir** + 每 OS 安装包（spec §5）。入口＝`launcher.py`
（进程内起 Streamlit，非 `streamlit run` 子进程）。规格文件＝仓库根
`text2sql.spec`（入库）；`dist/`、`build/` 产物不入库（.gitignore）。

**不能跨 OS 交叉编译**：macOS/Windows/Linux 须各自在本机（或 CI 矩阵）构建。
`text2sql.spec` 三平台通用：`BUNDLE`（.app）仅在 macOS 生效，其余平台自动跳过，
产出 `dist/text2sql-agent/` onedir 目录。

用户-facing 的下载安装说明见 README「下载安装」章节与
`packaging/README_FIRST_RUN.txt`（随三个安装包分发）；本文面向构建者。

## 1. 本地构建步骤

### 1.1 构建 onedir / .app（三平台通用，macOS 实测）

```bash
# 1) 运行时依赖 + 构建期依赖（pyinstaller 只在 requirements-build.txt）
#    -c packaging/constraints.txt（R9）：复现 PoC venv 验证过的传递依赖集
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt \
  -c packaging/constraints.txt

# 2) 构建（约 90s 冷构建 / 70s 增量；macOS .app 实测约 549MB，onedir 约 545MB）
.venv/bin/python -m PyInstaller text2sql.spec --noconfirm

# 3) 启动（双击等价）
open dist/text2sql-agent.app
# 或终端直跑可执行文件看启动日志：
dist/text2sql-agent.app/Contents/MacOS/text2sql-agent
# Windows：dist\text2sql-agent\text2sql-agent.exe
# Linux：dist/text2sql-agent/text2sql-agent
```

启动行为：创建用户数据目录（首跑写 `.env` 模板、复制 `semantic_models/`）→
挂早期 loguru 文件 sink（`<数据目录>/logs/app.log`，启动端口行先于 app.py
重配 logging 落盘，R8）→ 自 8501 起探测空闲端口（占用递增，上限 100 次尝试）
→ 起服务（headless 绑定 127.0.0.1）→ 就绪后自动开浏览器。调试日志：
`<数据目录>/logs/app.log`（含「启动 Streamlit：…（http://127.0.0.1:<端口>）」
端口行）。CI/headless 场景可设 `BROWSER=true` 抑制自动开浏览器（stdlib
`webbrowser` 语义）。

**运行时前提（不捆进包体）**：本地 Ollama（`ollama pull gemma4:E4B` +
`ollama pull bge-m3:latest`）或云端 API Key（Embedding 建议 DashScope
`text-embedding-v3`，同 Key）；Neo4j 可选、默认关闭。无可用 Embedding 时
检索回退 TF-IDF（降级模式）。未配置/不可达 LLM 时页面正常渲染并给出错误引导
（不白屏）。

### 1.2 各 OS 安装包（先完成 1.1 的 PyInstaller 构建）

**macOS .dmg**（仅 macOS；已本地验证）：

```bash
brew install create-dmg          # ≥ 1.3.0（--add-file 四参形式）
bash packaging/macos/dmg.sh      # 版本默认读根 VERSION 文件
# 指定版本：bash packaging/macos/dmg.sh 1.2.3 或 VERSION=1.2.3 bash ...
```

输出 `dist/text2sql-agent-<版本>-macos-arm64.dmg`（UDZO 压缩，实测约 188MB；
Applications 拖拽布局 + 卷内 `README_FIRST_RUN.txt`）。Finder 美化 AppleScript
偶发超时（-1712，无 GUI/CI 尤甚）→ 脚本自动 `--skip-jenkins` 重试，卷内容与
拖拽安装不变。文件名假定 arm64（`lipo` 核对，不符仅告警）。

**Windows setup.exe**（仅 Windows，Inno Setup 6.x）：

```bat
choco install innosetup -y
ISCC.exe packaging\windows\installer.iss
:: 指定版本：ISCC.exe /DVERSION=1.2.3 packaging\windows\installer.iss
```

输出 `dist\text2sql-agent-<版本>-windows-x64-setup.exe`。版本优先级：
`/DVERSION` > 环境变量 `VERSION`（`GetEnv`）> 默认 1.0.0。脚本为 UTF-8 with
BOM（Inno Setup 6 中文脚本要求）；`ArchitecturesAllowed=x64compatible`
（6.3+ 弃用裸 x64）；默认装到 `{autopf}\text2sql-agent`，含桌面/开始菜单快捷
方式与卸载器；onedir 全量（exe + `_internal\`）+ `README_FIRST_RUN.txt` 入包。

**Linux .AppImage**（仅 Linux，appimage-builder 1.x）：

```bash
sudo apt-get install -y squashfs-tools patchelf desktop-file-utils libfuse2 file
python -m pip install "appimage-builder~=1.1.0"   # 锁 1.x：配方为 1.x 语法
mkdir -p dist/AppDir
VERSION=1.0.0 appimage-builder \
  --recipe packaging/linux/AppImageBuilder.yml \
  --appdir dist/AppDir \
  --build-dir dist/appimage-build
mv text2sql-agent-*-linux-x86_64.AppImage dist/   # 输出落 CWD，按配方约定 mv
chmod +x dist/*.AppImage
```

`VERSION` 环境变量**必须导出**：`{{ VERSION }}` 模板在配方解析时求值，缺失即
报错。构建需网络（自动下载 AppImageKit runtime 与 AppRun）。onedir 整树进
`AppDir/usr/bin`（exe 与 `_internal/` 同级，勿拆分布局）；`runtime.preserve:
usr/bin` 禁止 patchelf 改写（bootloader 自带 rpath/_MEIPASS 加载逻辑，改写会
破坏冻结态）；`PATH: '$APPDIR/usr/bin:$PATH'` 使 desktop Exec 裸名可解析。
用户运行需 FUSE（libfuse2）；缺失时 `--appimage-extract-and-run` 回退。

### 1.3 版本号（单一事实源）

仓库根 `VERSION` 文件（当前 1.0.0）：`text2sql.spec`（plist）与 `dmg.sh`
直接读文件；CI 读出导出 `VERSION` 环境变量供 iss `GetEnv("VERSION")` 与
AppImage `{{ VERSION }}` 模板——四处同源一致。

## 2. 数据目录（bundle 只读）

冻结态 `config.DATA_DIR = platformdirs.user_data_dir("text2sql-agent",
appauthor=False)`（`appauthor=False` 防 Windows 双层 author 目录，三 OS 单层
一致；对 macOS/Linux 无影响）：

| OS | 路径 |
| --- | --- |
| macOS | `~/Library/Application Support/text2sql-agent` |
| Windows | `%LOCALAPPDATA%\text2sql-agent` |
| Linux | `~/.local/share/text2sql-agent` |

内容：`.env`（首跑模板，绝不覆盖已有；**打包应用**模型配置面板保存经
`core/config_persistence.write_env_config` 原子合并写回，跨重启存活——
仅冻结态持久化（R7），开发态配置会话级、开发者自管根 `.env`）、
`text2sql.db`（SQLite，种子自 bundle `data/seed_*.sql` 幂等加载）、`logs/`、
`semantic_models/`（首跑自 bundle 复制）、`index_cache/`（可选）。
**实测：多次启动+端到端查询后 bundle 内 0 个文件被修改/新增**
（`find .app -type f -newer <构建完成标记>` 为空）。

## 3. Hook 知识库（macOS PoC 迭代实测，CI 矩阵必读）

### 3.1 收集策略（text2sql.spec）

- `collect_all("streamlit")` **缺一不可**：`static/` 前端、components、proto，
  以及 dist-info metadata——`streamlit/version.py` 在 import 时即
  `importlib_metadata.version("streamlit")`，缺 metadata 直接崩。
- `collect_all("faiss")` + `collect_dynamic_libs("faiss")`：faiss-cpu 1.15
  arm64 含 `_swigfaiss.abi3.so`（扩展）、`libfaiss.dylib`、delocate 注入的
  `.dylibs/libomp.dylib`、`MetalDistance.metallib`（Metal 内核，按 data 收集）。
  PyInstaller 把 dylib 提升到 bundle 根并改写 `@rpath`，实测加载正常。
  注意 `.dylibs` 在 bundle 内被重命名为 `__dot__dylibs`（点目录规避）。
- `collect_all("sqlfluff")`：规则/方言数据 + 默认配置；`collect_all("sqlglot")`
  全方言（动态加载）；`sqlparse`。
- `collect_all("sqlalchemy")`：2.0 方言经 importlib 动态加载，须整包冻结 +
  metadata。`excludes=["mysql","psycopg2"]` 排除未用驱动瘦身（全方言收集会
  牵出驱动模块；运行时仅 sqlite）。
- pydantic 系（`pydantic`/`pydantic_core`/`pydantic_settings`）、langchain 系
  （`langchain`/`langchain_community`/`langchain_core`/`langchain_openai`）、
  `neo4j`、`sklearn`+`scipy`+`joblib`+`threadpoolctl`、`rank_bm25`、`numpy`。
- Streamlit 图表/数据栈：`altair`（vega-lite schema JSON）、`pydeck`（jinja2
  模板）、`pandas`、`pyarrow`（原生库）。
- 云端提供商：`dashscope`、`openai`、`tiktoken`；**`tiktoken_ext` 是独立顶层
  插件包**（entry_points 动态加载），须 `collect_submodules("tiktoken_ext")`，
  metadata 由 `collect_all("tiktoken")` 提供。
- `git`/`gitdb`/`smmap`（streamlit.git_util → GitPython）、`tornado`、
  `jsonschema`、`yaml`、`importlib_metadata`、`loguru`、`platformdirs`、
  `dotenv`、`requests`。
- `collect_data_files("pytz")` + `collect_data_files("tzdata")`：纯数据包，
  Analysis 不追踪其数据文件。
- PyInstaller 6.22 的 `copy_metadata` 支持 import 名→分发名解析
  （`sklearn`→scikit-learn、`faiss`→faiss-cpu、`git`→GitPython、
  `yaml`→PyYAML），上述 `collect_all` 均已预验证可解析。
- **缺失包行为**：`collect_all` 对未安装的包仅告警跳过（返回空三元组，
  PyInstaller 6.22 `on_error="warn once"`），不中断构建——缺包会静默产出
  运行时缺模块的产物，构建环境须与 PoC venv 对齐：云端 LLM 栈
  （langchain-openai/openai/tiktoken）已直 pin 入 requirements.txt（Task 8
  C1），传递依赖经 `packaging/constraints.txt` 约束（R9），安装命令见 §1.1。
- `watchdog` 未安装：streamlit 回退 `PollingPathWatcher`（已显式冻结）；
  启动时打印的 "install watchdog" 提示无害，无需捆绑。
- `nltk` 虽在 requirements 但应用代码未 import，未收集（如未来启用需
  `collect_data_files("nltk")`）。

### 3.2 隐藏导入

- **`collect_submodules("core")` + `collect_submodules("app")` 必须**：
  `app.py` 仅以 datas 进 bundle（Streamlit 主脚本由 bootstrap exec），
  Analysis 只追踪 `launcher.py`，不追踪 app.py 的 import 链。
- streamlit 运行时动态导入显式列出：`streamlit.web.cli`、
  `streamlit.web.bootstrap`、`streamlit.runtime.scriptrunner.magic`/
  `script_runner`、`streamlit.watcher.polling_path_watcher`、
  `streamlit.components.v1`（collect_all 已含子模块，显式列出便于审计）。

### 3.3 datas 布局

- 根 `app.py` → bundle 根（`launcher.resolve_main_script()` →
  `bundle_dir/app.py`）；`schema.sql` → 根。
- `data/seed_business.sql`、`data/seed_history.sql` → `data/`
  （`SQLiteClient._SEED_DIR = Path(__file__).parents[2]/"data"`）。
- `app/`、`core/` 源码树（`__file__` 相对路径回退）、`semantic_models/`
  （首跑复制到 DATA_DIR）、`assets/`（logo）。
- **PyInstaller datas 语义陷阱**：`(源, 目标目录)`——第二元素是**目录**而非
  完整文件名。误写 `(src/assets/logo.png, "assets/logo.png")` 会生成
  `assets/logo.png/logo.png` 嵌套目录 → 运行时 `IsADirectoryError`。
  正确：目标目录＝`dest/相对父目录`（spec `_project_tree`）。

### 3.4 启动器修复（launcher.py，实测迭代产物）

1. **`global_developmentMode=False` 旗标**：streamlit/config.py 以
   `__file__` 是否含 "site-packages" 判定 dev 模式；冻结路径永不包含 →
   `developmentMode=True` → 与 `server.port` 冲突触发
   `AssertionError: server.port does not work when global.developmentMode
   is true`。必须在 `flag_options` 显式关闭。
2. **multiprocessing 子进程拦截（`_exec_multiprocessing_child`）**：CPython
   multiprocessing（spawn/resource_tracker）以 `sys.executable -B -S -I -c
   <code>` 拉子进程；**冻结 exe 忽略 `-c` 旗标并重跑入口脚本**——sqlfluff
   校验（`multiprocessing.Pool`）触发的 resource_tracker 子进程会再跑一遍
   `main()`，多起一个 Streamlit 服务（多占端口、多开浏览器标签）。修复：
   入口检测 `sys.argv` 中的 `-c`，按 CPython 语义 exec 子进程代码后退出。
   开发态恒不触发。CI 冒烟的冻结态 SQLite 探针正利用此通道（§4）。
3. **早期日志文件 sink（`setup_early_log_sink`，R8）**：端口行在
   `bootstrap.run` 之前发出，而 app.py 运行时才 `logger.remove()` + 重挂
   sink——早期 sink（`config.LOG_FILE`，冻结态即 DATA_DIR/logs/app.log，
   level=DEBUG、safe_log_format）保证端口行先落盘；app.py 重配后端口信息
   仍在文件。README「实际端口见 logs/app.log」由此成立。

### 3.5 macOS BUNDLE 布局与行为

- `Contents/MacOS/text2sql-agent`（可执行）；`Contents/Frameworks/`＝
  `sys._MEIPASS`（onedir 的 `_internal` 等价物）；`Contents/Resources/`
  含 datas 副本/符号链接。冻结模块 `__file__.resolve()` 可能落到 Resources
  路径——两处内容一致，`resolve_bundle_dir()` 优先 `_MEIPASS`，无碍。
- `console=False`（windowed）：Finder 双击无终端；终端直跑可执行文件仍可见
  启动日志。应用日志恒写 DATA_DIR/logs/app.log。
- 停机：SIGTERM → streamlit 优雅停机（"Stopping..."），**等待浏览器会话
  断开**；浏览器标签仍开着时退出会延迟（streamlit 1.29 语义）。v1 无原生
  退出菜单，关标签或强制退出即可。
- v1 不签名：Gatekeeper 警告，右键→打开绕过（README「下载安装」章节与
  README_FIRST_RUN.txt 均已说明）。

## 4. CI 矩阵（.github/workflows/build.yml）

- **触发**：tag `v*` 推送 / 手动 `workflow_dispatch`。`permissions:
  contents: read`；三 OS 统一 bash（Windows 用 Git Bash）；`fail-fast: false`
  （单 OS 失败不拖累其余两 OS）；timeout 60min。
- **矩阵**（spec §9-Q4 现代平台）：`macos-latest`（Apple Silicon arm64）/
  `windows-latest`（x64）/ `ubuntu-22.04`（glibc 2.35 下限，兼容较新发行版）。
  Intel Mac/更旧 Linux/Win arm64 留后续。
- **流程**：checkout → setup-python 3.12（pip 缓存按两个 requirements +
  constraints 哈希）→ 导出 `VERSION`（根 VERSION 文件）→ `pip install
  -r requirements.txt -r requirements-build.txt -c packaging/constraints.txt`
  （R9：复现 PoC 验证过的传递依赖集）→ `pyinstaller text2sql.spec --noconfirm` →
  OS 安装包（brew create-dmg + dmg.sh / choco innosetup + ISCC / apt 工具 +
  appimage-builder~=1.1.0）→ 冒烟 → upload-artifact。
- **冒烟边界（无 LLM）**：CI 无 Ollama/云 Key，NL 生成冒烟属人工（macOS PoC
  已覆盖，§5）。CI 冒烟＝冻结产物 launch + `/_stcore/health`=ok + 首页
  HTTP 200 静态渲染 + 冻结态 SQLite 直查探针（经 launcher 的 multiprocessing
  `-c` 拦截在冻结环境内执行 Python，对 bundled 种子库做只读 COUNT，断言
  历史/业务种子非空）。`BROWSER=true` 抑制开浏览器。端口优先读 launcher
  日志（占用递增不误认他服务），无日志回退扫描 8501..8510。Linux 直跑
  AppImage（FUSE），同时验证 runtime.preserve 未破坏 ELF、desktop Exec 裸名
  经 AppRun PATH 可解析；FUSE 不可用回退 `--appimage-extract-and-run`。
  冒烟脚本已在 macOS PoC 产物上本地验证（health=ok / home=200 /
  FROZEN_SQLITE_OK）。失败时上传 smoke-*.log。
- **产物**：`text2sql-agent-<VERSION>-<os后缀>` artifact＝安装包 +
  `dist/text2sql-agent/` onedir（macOS 的 .app 与 dmg 内容重复，不单独上传），
  保留 14 天。**release 附产物为后续工作**：现有 workflow 无 GitHub Releases
  发布步骤（spec §5.6「release 附产物（后续）」）。
- **验证状态（如实）**：workflow 与三 OS 安装包脚本已入库；macOS 腿的构建 +
  dmg + 冒烟脚本已在本机 PoC 产物上验证。**workflow 尚未在 GitHub 上运行过**
  （packaging 分支未推送、未打 tag）；Windows/Linux 腿的首次 CI 运行与产物
  冒烟待推送后核实。

## 5. PoC 验证清单（macOS arm64，Python 3.12，PyInstaller 6.22.3）

**Task 8 从 HEAD 重建后全量重跑**（旧产物早于 Task 4、plist 0.1.0、PYZ 缺
core.config_persistence，已作废）。重建 77.7s；.app 549MB / onedir 545MB；
plist=1.0.0；PYZ 含 core.config_persistence，datas model_config.py 含冻结门控。
验证用隔离 HOME（scratch `build/frozen-home`，platformdirs 经 HOME 展开，
不触真实用户数据目录）；终端直跑可执行文件（`open` 双击等价路径 Task 3 已
验证，BUNDLE 布局未变）；live dev 8501 未触碰，冻结实例自 8502 起（占用递增
实测 8502/8503）。驱动＝websocket 协议级探针（build/st_probe*.py，scratch）。

- [x] 启动即起服务；`/_stcore/health` = ok；首页渲染无异常（207 元素）。
- [x] 首跑 DATA_DIR 初始化：`.env` 模板（846B）、`semantic_models/` 复制、
      种子建库（15 表＝8 业务 + 6 应用 + sqlite_sequence，历史种子 50 行，
      `risk_blacklist` 3 行）。
- [x] **端口行落 DATA_DIR/logs/app.log（R8/I6）**：早期 sink 在 app.py 重配
      logging 前写「启动 Streamlit：…（http://127.0.0.1:<端口>）」；验证脚本
      自该文件读端口（多次重启均命中，含递增端口）。
- [x] 模型配置面板保存 → 「LLM 已切换为：Ollama (本地) / gemma4:E4B」→
      **DATA_DIR/.env 原子合并写入**（LLM_BASE_URL=http://localhost:11434
      可观测，模板原值为空）→ **重启后 system_info 显示持久化 Base URL**
      （frozen 门控 R7 实证；dev 会话级由单测覆盖）。
- [x] 未配置引导（`LLM_BASE_URL` 指向拒绝端口，env 注入不改动文件）：
      首页渲染 + 「首次运行引导」（frozen 文案含「重启不丢失」）+ 生成错误
      引导「生成失败：LLM 服务调用失败，请检查模型配置后重试」，不白屏。
- [x] 端到端：「查询所有黑名单用户」→ `SELECT … FROM risk_blacklist`
      （LLM 输出非确定：SELECT * 或列清单均出现）→ 执行返回 3 行 → 历史落
      `DATA_DIR/text2sql.db` `sql_generation_history`（execution_status=success）。
      另实测 LLM 幻觉列名（JOIN users.username 不存在）→ 执行失败被优雅捕获：
      浏览器仅见脱敏错误编号，app.log 记 error_id/stage/exception_type，
      历史 execution_status=fail——安全边界与容错路径冻结态完好。
- [x] faiss（FAISS 索引 dim=1024）、sqlfluff 校验、Ollama embedding（bge-m3）
      冻结态全链路正常；冻结态 `-c` 探针（multiprocessing 拦截通道）：
      FROZEN_SQLITE_OK history_rows=51 risk_blacklist=3 +
      PERSISTENCE_MODULE_OK，不多起服务。
- [x] bundle 只读：重建标记后历经首跑/保存/生成/执行/重启/引导/探针，
      .app 与 onedir 均 **0 文件改动**（`find -type f -newer <标记>` 为空）。
- [x] dmg 重生成（bash packaging/macos/dmg.sh，完整布局未触发 skip-jenkins）：
      hdiutil attach 验证卷内容（.app + Applications 链接 +
      README_FIRST_RUN.txt），卷内 plist=1.0.0、含 config_persistence；
      UDZO 压缩约 188MB（197,403,761B）。
- [x] CI 安装命令复现（R9/I5）：scratch venv 全新安装
      `-r requirements.txt -r requirements-build.txt -c packaging/constraints.txt`
      成功；云端栈 ChatOpenAI/AzureChatOpenAI 可实例化、tiktoken_ext 可导入、
      ChatOllama 活体生成「好的」、OllamaEmbeddings dim=1024、应用工厂 import
      链通过（CI_SMOKE_OK）。langchain 一致组合见 §6。
- [x] 开发态回归：**1124 passed, 9 skipped**（1106 基线 + 18 新增）；ruff 零；
      build.yml / AppImageBuilder.yml YAML 合法。

## 6. 已知限制 / 后续

- **v1 不签名/不公证、不自动更新**（spec §4 非目标）；OS 警告绕过指引见
  README「下载安装」与 README_FIRST_RUN.txt。
- **LLM 前提（非 turnkey）**：不捆绑 Ollama/模型/Neo4j；首跑需拉两模型或配
  云端 Key + DashScope embedding。无可用 Embedding → TF-IDF 降级（语义检索
  减弱，应用仍可用）。
- **`langchain_anthropic` 未安装** → anthropic 提供商在包内不可用（构建环境
  装上即自动收集）；ollama/openai 系实测可用。
- **构建工具链刻意 pin（Task 8 I4/I5）**：`pyinstaller==6.22.3` +
  `pyinstaller-hooks-contrib==2026.10`（月度 rev，不 pin 会解析未验证组合）；
  传递依赖经 `packaging/constraints.txt`（PoC venv 验证闭包）约束。刻意升级
  任一 pin 须重建产物 + 重跑 §5 frozen PoC 清单复证，并同步更新 constraints。
  Windows/Linux 专属传递依赖（pefile/pywin32-ctypes/greenlet/watchdog 等）
  PoC venv 未装、不在 constraints 内，对应 CI 腿自行解析（首跑后如需复现再补录）。
- **langchain 系 pin 对齐一致组合（Task 8，I5 验证时发现的既有缺陷）**：
  原 `langchain==0.1.0`/`langchain-community==0.0.10` 声明 `langsmith<0.1.0`，
  与 `langchain-core==0.1.53` 声明的 `langsmith>=0.1.0` **交集为空**——pip
  全新解析必然 ResolutionImpossible（PoC venv 系手工装配，langsmith 0.1.147
  漂移超出前两者声明范围，runtime 实测相容但 pip 无法表达）。已对齐上游
  0.1.x 末代一致组合 `langchain==0.1.20` + `langchain-community==0.0.38`；
  core/langsmith/langchain-openai/openai/tiktoken 保持 PoC 验证版本。应用不
  import 顶层 langchain，community 仅用 ChatOllama（0.0.x API 稳定）。
  **本地重建产物（共享 venv）含 langchain 0.1.0/community 0.0.10，CI 产物含
  0.1.20/0.0.38**；差异面经 scratch venv 全新安装 + ChatOllama 活体冒烟核实。
  新增传递依赖 `langchain-text-splitters==0.0.2`（应用不用 text_splitter）。
- **Windows/Linux 产物冒烟待首次 CI 运行**（§4 验证状态）；faiss 原生库每 OS
  由 `collect_all`/`collect_dynamic_libs` 自适应（Win 为 .dll/.pyd）。
- 知识图谱「连接并构建」装载需 Neo4j；SQLite 元数据模式下知识自活体库
  introspection 自动加载（PoC 即此路径），不影响生成/执行。语义治理
  mysql-only 休眠，v1 SQLite 演示模式下 config 闸门阻止启用。
- 包体约 549MB（macOS .app 实测；faiss/scipy/sklearn/pyarrow/streamlit 全量
  收集），onedir 压缩分发可接受（spec §8）；dmg 压缩后约 188MB。
- v1 demo 定位：自带示例数据（8 业务表 30 行）开箱即查；不引导改 SQLITE_PATH
  指向任意库（避免种子注入污染）；接自有数据经 KG + 外部 Neo4j 属高级/后续。
- GitHub Releases 发布流程、代码签名/公证、自动更新均留后续。
