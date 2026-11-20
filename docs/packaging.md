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
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt

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
自 8501 起探测空闲端口（占用递增，上限 100 次尝试）→ 起服务（headless 绑定
127.0.0.1）→ 就绪后自动开浏览器。调试日志：`<数据目录>/logs/app.log`
（loguru 文件 sink）。CI/headless 场景可设 `BROWSER=true` 抑制自动开浏览器
（stdlib `webbrowser` 语义）。

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

冻结态 `config.DATA_DIR = platformdirs.user_data_dir("text2sql-agent")`：

| OS | 路径 |
| --- | --- |
| macOS | `~/Library/Application Support/text2sql-agent` |
| Windows | `%LOCALAPPDATA%\text2sql-agent` |
| Linux | `~/.local/share/text2sql-agent` |

内容：`.env`（首跑模板，绝不覆盖已有；模型配置面板保存经
`core/config_persistence.write_env_config` 原子合并写回，跨重启存活）、
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
  运行时缺模块的产物，构建环境须与 PoC venv 对齐（见 §6 langchain-openai 条）。
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
- **流程**：checkout → setup-python 3.12（pip 缓存按两个 requirements 哈希）
  → 导出 `VERSION`（根 VERSION 文件）→ `pip install -r requirements.txt
  -r requirements-build.txt` → `pyinstaller text2sql.spec --noconfirm` →
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

- [x] 终端直跑与 `open`（双击等价）均起服务；`/_stcore/health` = ok。
- [x] 首页渲染无异常（Streamlit websocket 协议级驱动验证，205+ 元素）。
- [x] 首跑 DATA_DIR 初始化：`.env` 模板、`semantic_models/` 复制、种子建库
      （8 业务表 30 行 + 6 应用表，历史种子 50 行，`risk_blacklist` 3 行）。
- [x] LLM 不可达（`LLM_BASE_URL` 指向拒绝端口）→ 页面渲染 + 错误引导
      「生成失败：LLM 服务调用失败，请检查模型配置后重试」，不白屏。
- [x] 应用内模型配置面板保存 → 「LLM 已切换为：Ollama (本地) / gemma4:E4B」；
      保存持久化到 DATA_DIR/.env（跨重启，Task 4 已加持久化测试）。
- [x] 端到端：「查询所有黑名单用户」→ `SELECT * FROM risk_blacklist` →
      执行返回 3 行 → 历史落 `DATA_DIR/text2sql.db`
      `sql_generation_history`（execution_status=success）。
- [x] faiss（FAISS 索引 dim=1024）、sqlfluff 校验、Ollama embedding（bge-m3）
      冻结态全链路正常；resource_tracker 子进程不再多起服务。
- [x] bundle 只读：构建完成后 0 文件改动。
- [x] dmg 安装包：hdiutil attach 验证卷内容（.app + Applications 链接 +
      README_FIRST_RUN.txt），UDZO 压缩约 188MB。
- [x] 开发态回归：1106 passed, 9 skipped（Task 7 文档完成时复核，基线不变）；
      ruff 零。

## 6. 已知限制 / 后续

- **v1 不签名/不公证、不自动更新**（spec §4 非目标）；OS 警告绕过指引见
  README「下载安装」与 README_FIRST_RUN.txt。
- **LLM 前提（非 turnkey）**：不捆绑 Ollama/模型/Neo4j；首跑需拉两模型或配
  云端 Key + DashScope embedding。无可用 Embedding → TF-IDF 降级（语义检索
  减弱，应用仍可用）。
- **`langchain_anthropic` 未安装** → anthropic 提供商在包内不可用（构建环境
  装上即自动收集）；ollama/openai 系实测可用。
- **`langchain-openai` 未列入 requirements.txt**（PoC venv 手动装有 0.1.0，
  spec 收集列表含它）：CI 从 requirements.txt 全新安装不会带上该包，
  `collect_all("langchain_openai")` 对缺失包仅告警跳过（§3.1）——CI 产物的
  云端 OpenAI 兼容 LLM 路线（openai/azure/dashscope/deepseek/zhipu）会缺模块，
  Ollama 默认路线不受影响。补 pin 属构建依赖修订，留待后续裁决（Task 6 遗留）。
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
