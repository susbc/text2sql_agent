# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: F821  -- Analysis/PYZ/EXE/COLLECT/BUNDLE/SPECPATH 由 PyInstaller 注入
"""text2sql-agent PyInstaller 规格（打包 spec §5.4，macOS PoC 迭代产物）。

入口＝launcher.py（进程内 bootstrap.run 起 Streamlit，非 `streamlit run` 子进程）。
形态＝onedir（COLLECT）+ macOS BUNDLE（.app，windowed 无终端）。

收集策略（详见 docs/packaging.md 的 hook 知识库）：
- collect_all：streamlit（static 前端/组件/metadata 缺一不可）、faiss（原生库
  libfaiss.dylib/.dylibs/libomp.dylib + MetalDistance.metallib）、sqlfluff（规则/
  方言数据）、pydantic 系、langchain 系、neo4j、sklearn/scipy、sqlalchemy（方言
  importlib 动态加载）、altair/pydeck/pandas/pyarrow/numpy（streamlit 图表栈）、
  dashscope/openai/tiktoken（云端 LLM/Embedding）、git/gitdb/smmap（streamlit.
  git_util）、tornado/jsonschema/yaml 等。
- hiddenimports：core/app 全子模块（app.py 仅作 datas 收集，不被 Analysis 追踪，
  其 import 必须显式冻结）、streamlit 运行时动态导入、sqlglot 方言。
- datas：根 app.py（resolve_main_script → bundle_dir/app.py）、app/ 与 core/ 源码
  树（__file__ 相对路径回退）、semantic_models/（首跑复制到 DATA_DIR）、
  data/seed_*.sql（SQLiteClient._SEED_DIR＝bundle/data）、assets/、schema.sql、
  VERSION（config.APP_VERSION 运行时读取，落 _internal 与 config 同级）。

数据不落 bundle：冻结态 config.DATA_DIR＝platformdirs.user_data_dir，SQLite/
logs/.env/index_cache 全在用户数据目录（spec §5.1）。
"""
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH)

# 版本号单一事实源＝仓库根 VERSION 文件（Task 6）：dmg.sh 直接读文件，
# CI 导出 VERSION 环境变量供 iss/AppImage 配方，此处 plist 同源，四处一致。
_VERSION_FILE = PROJECT_ROOT / "VERSION"
APP_VERSION = (
    _VERSION_FILE.read_text(encoding="utf-8").strip()
    if _VERSION_FILE.is_file()
    else "1.0.0"
)

datas = []
binaries = []
hiddenimports = []


def _collect_all(pkg: str) -> None:
    """整包收集：数据文件 + 原生库 + 全子模块 + dist-info metadata。"""
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hiddenimports)


# --- 第三方整包收集（均已用 collect_all 预验证可解析 metadata）---
_COLLECT_ALL_PACKAGES = (
    # Streamlit 本体：static/ 前端、components、proto、metadata（version.py 在
    # import 时即 importlib_metadata.version("streamlit")，缺 metadata 直接崩）。
    "streamlit",
    # faiss-cpu：_swigfaiss.abi3.so 扩展 + libfaiss.dylib + .dylibs/libomp.dylib
    # + MetalDistance.metallib（arm64 Metal 距离内核，datas 收集）。
    "faiss",
    # SQL 校验/解析：sqlfluff 规则与方言数据、sqlglot 全方言、sqlparse。
    "sqlfluff",
    "sqlglot",
    "sqlparse",
    # pydantic v2 系（pydantic_core 为 Rust 原生扩展）。
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    # LangChain 系（大量 try/except 可选导入，整包收集避免运行时缺模块）。
    "langchain",
    "langchain_community",
    "langchain_core",
    "langchain_openai",
    # 图谱（默认关闭，但 import 链需要）与检索/向量栈。
    "neo4j",
    "sklearn",
    "scipy",
    "joblib",
    "threadpoolctl",
    "rank_bm25",
    "numpy",
    # SQLAlchemy 2.0 方言经 importlib 动态加载，须整包冻结 + metadata。
    "sqlalchemy",
    # Streamlit 图表/数据栈：altair 需 vega-lite schema JSON，pydeck 需 jinja2
    # 模板，pyarrow/pandas 含原生库与测试数据。
    "altair",
    "pydeck",
    "pandas",
    "pyarrow",
    # 云端 LLM/Embedding 提供商（dashscope/openai）；tiktoken 供 ChatOpenAI 计数。
    "dashscope",
    "openai",
    "tiktoken",
    # streamlit.git_util → GitPython（import 名 git）→ gitdb/smmap。
    "git",
    "gitdb",
    "smmap",
    # 其余运行时依赖。
    "tornado",
    "jsonschema",
    "yaml",
    "importlib_metadata",
    "loguru",
    "platformdirs",
    "dotenv",
    "requests",
)
for _pkg in _COLLECT_ALL_PACKAGES:
    _collect_all(_pkg)

# faiss 原生库显式再收一遍（含 delocate 注入的 .dylibs/libomp.dylib，双保险）。
binaries += collect_dynamic_libs("faiss")

# tiktoken 编码插件是独立顶层包 tiktoken_ext，经 entry_points 动态加载：
# 子模块显式冻结，metadata 由上面 collect_all("tiktoken") 提供。
hiddenimports += collect_submodules("tiktoken_ext")

# pytz/tzdata 时区数据（pandas 依赖；纯数据包，Analysis 不会自动追踪数据文件）。
datas += collect_data_files("pytz")
datas += collect_data_files("tzdata")

# --- 项目模块隐藏导入 ---
# app.py 仅以 datas 形式进 bundle（Streamlit 主脚本由 bootstrap exec），Analysis
# 不追踪其 import 链 —— app/ 与 core/ 全子模块必须显式冻结。
hiddenimports += collect_submodules("core")
hiddenimports += collect_submodules("app")
# Streamlit 运行时动态导入（collect_all 已含子模块，此处按 brief 显式列出关键项）。
hiddenimports += [
    "streamlit.web.cli",
    "streamlit.web.bootstrap",
    "streamlit.runtime.scriptrunner.magic",
    "streamlit.runtime.scriptrunner.script_runner",
    # watchdog 未安装 → path_watcher 回退轮询实现，须冻结。
    "streamlit.watcher.polling_path_watcher",
    "streamlit.components.v1",
    "sqlglot.dialects",
    "loguru",
    "dotenv",
    "platformdirs",
]

# --- 项目数据文件（落 bundle 根/_internal，launcher.resolve_bundle_dir 解析）---


def _project_tree(rel_dir: str, dest: str) -> list:
    """项目目录 → datas 列表（剔除 __pycache__/*.pyc/.DS_Store）。

    注意 PyInstaller datas 语义：(源文件, 目标目录)——第二元素是目录而非
    完整文件名，文件保留 basename。故目标目录＝dest/相对父目录。
    """
    src_root = PROJECT_ROOT / rel_dir
    entries = []
    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root)
        if "__pycache__" in rel.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.name == ".DS_Store":
            continue
        entries.append((str(path), str(Path(dest) / rel.parent)))
    return entries


datas += [
    # Streamlit 主脚本必须在 bundle 根：resolve_main_script() → bundle_dir/app.py。
    (str(PROJECT_ROOT / "app.py"), "."),
    (str(PROJECT_ROOT / "schema.sql"), "."),
    # 运行时版本号：config.APP_VERSION 读 PROJECT_ROOT/VERSION。冻结态 config 在
    # PYZ 内，__file__ 落 _internal（＝datas 目标 "."），故 VERSION 须同级收集。
    (str(PROJECT_ROOT / "VERSION"), "."),
    # SQLiteClient._SEED_DIR = Path(__file__).parents[2]/"data" → bundle/data。
    (str(PROJECT_ROOT / "data" / "seed_business.sql"), "data"),
    (str(PROJECT_ROOT / "data" / "seed_history.sql"), "data"),
]
datas += _project_tree("app", "app")
datas += _project_tree("core", "core")
datas += _project_tree("semantic_models", "semantic_models")
datas += _project_tree("assets", "assets")

# --- 排除：未使用的重型可选依赖（sqlalchemy 全方言收集会牵出 mysql/psycopg2
# 驱动模块，运行时仅用 sqlite，排除以瘦身；tkinter/matplotlib 未安装亦未使用）---
excludes = ["tkinter", "matplotlib", "mysql", "psycopg2"]

a = Analysis(
    ["launcher.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="text2sql-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # windowed（.app 无终端）；调试可从终端直跑 Contents/MacOS/text2sql-agent。
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="text2sql-agent",
)
app = BUNDLE(
    coll,
    name="text2sql-agent.app",
    icon=None,
    bundle_identifier="com.susuan.text2sql-agent",
    info_plist={
        "CFBundleName": "text2sql-agent",
        "CFBundleDisplayName": "溯算 Text2SQL 智能体",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "NSHumanReadableCopyright": "溯算编程 · Text2SQL 智能体",
    },
)
