"""桌面启动器（PyInstaller 打包入口，spec §5.2）。

职责：
1. ensure_data_dir()：创建可写数据目录 DATA_DIR（含 logs/）；首跑无 .env 时
   写默认模板（已存在的 .env 绝不覆盖）。
2. copy_semantic_models()：冻结态首跑把 bundle 内 semantic_models/ 复制到
   DATA_DIR/semantic_models（目标已存在则不动）。
3. setup_early_log_sink()：早期 loguru 文件 sink（config.LOG_FILE），使启动
   端口行在 app.py 重配 logging 之前已落 logs/app.log（R8）。
4. launch_streamlit()：进程内起 Streamlit（冻结态不能 `sys.executable -m
   streamlit`），headless 绑定 127.0.0.1，端口 8501 起探测占用递增；服务就绪
   后 webbrowser.open。

helper 与启动分离：单测只调 helper（tests/test_launcher.py），不拉起服务。
开发态可直接 `python launcher.py`（路径回退 PROJECT_ROOT），日常开发仍推荐
`streamlit run app.py`。

注意：冻结态 config 在 import 时加载 DATA_DIR/.env；首跑时模板在 config
import 之后才写入，但模板值与 config 冻结态默认值一致（SQLITE_PATH/
SEMANTIC_MODEL_DIR 等均派生自 DATA_DIR），故首跑无需 reload；用户编辑 .env
或首跑向导（Task 4）写入后，下次启动即生效。
"""
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from loguru import logger

import config
from core.utils.log_sanitizer import safe_log_format

# 默认起始端口（与 config.STREAMLIT_SERVER_PORT 默认一致）；占用则递增探测。
DEFAULT_STREAMLIT_PORT = 8501
_PORT_SCAN_ATTEMPTS = 100
_BROWSER_READY_TIMEOUT_SECONDS = 60.0


def is_frozen() -> bool:
    """是否 PyInstaller 冻结态。"""
    return bool(getattr(sys, "frozen", False))


def resolve_bundle_dir() -> Path:
    """解析 bundle 资源根目录（datas 落点）。

    - onefile：sys._MEIPASS（临时解包目录）；
    - onedir（PyInstaller 6+）：可执行文件同级 _internal/；
    - 旧版 onedir 布局：datas 与可执行文件同级，回退 exe 所在目录；
    - 开发态：launcher.py 所在目录（即 PROJECT_ROOT）。
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if is_frozen():
        exe_dir = Path(sys.executable).parent
        internal = exe_dir / "_internal"
        return internal if internal.is_dir() else exe_dir
    return Path(__file__).resolve().parent


def resolve_main_script() -> Path:
    """Streamlit 主脚本：冻结态取 bundle 内 app.py（datas），开发态取项目根。"""
    if is_frozen():
        return resolve_bundle_dir() / "app.py"
    return config.PROJECT_ROOT / "app.py"


def _env_template(data_dir: Path) -> str:
    """首跑 .env 默认模板：与 config 冻结态默认值对齐，向导/用户可再编辑。"""
    sqlite_path = data_dir / "text2sql.db"
    return f"""# text2sql-agent 首次运行自动生成的默认配置（打包 spec §5.2）。
# 已存在的 .env 不会被覆盖；修改后重启应用生效。

# SQLite 数据库文件（位于用户数据目录，可写）
SQLITE_PATH={sqlite_path}

# SQL 方言：执行目标为 SQLite
SQL_DIALECT=sqlite

# 图谱增强（可选，需外部 Neo4j 服务；默认关闭）
NEO4J_ENABLED=false

# LLM 配置（默认占位值，首跑向导会引导修改）
# 本地 ollama 需先 `ollama pull gemma4:E4B`；云端提供商需填 LLM_API_KEY
LLM_PROVIDER=ollama
LLM_MODEL=gemma4:E4B
LLM_API_KEY=
LLM_BASE_URL=

# Embedding 配置（默认占位值，首跑向导会引导修改）
# 本地 ollama 需 `ollama pull bge-m3:latest`；云端可配 dashscope + API Key
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_API_KEY=

# 默认禁查应用内部表（与 config.SQL_BLOCKED_TABLES 默认一致）
SQL_BLOCKED_TABLES=knowledge_metadata,table_schema,column_schema,sql_generation_history,retrieval_terms,user_feedback
"""


def write_env_template(data_dir: Path) -> Path:
    """无 .env 时写默认模板；已有 .env 原样保留（绝不覆盖用户配置）。"""
    env_path = data_dir / ".env"
    if not env_path.exists():
        env_path.write_text(_env_template(data_dir), encoding="utf-8")
    return env_path


def ensure_data_dir() -> Path:
    """创建 DATA_DIR 与 logs/（parents exist_ok），首跑写 .env 模板。"""
    data_dir = Path(config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    write_env_template(data_dir)
    return data_dir


def setup_early_log_sink() -> int:
    """早期 loguru 文件 sink（R8，Task 8 I6）：让启动端口行落 logs/app.log。

    端口行由 launch_streamlit 在 bootstrap.run 之前发出，而 app.py 要到脚本
    运行时才重配 logging（logger.remove() 先清掉全部既有 sink）——没有本早期
    sink 时端口行只留在终端（windowed 双击不可见），README「实际端口见
    logs/app.log」不成立。sink 目标＝config.LOG_FILE（冻结态即
    DATA_DIR/logs/app.log，与 app.py 文件 sink 同一文件）；level=DEBUG 保证
    端口行不被 LOG_LEVEL 过滤。app.py 重配 logging 时本 sink 被 remove()
    回收，端口行已落盘不受影响。返回 sink id（便于测试移除）。
    """
    log_path = Path(config.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return logger.add(log_path, level="DEBUG", format=safe_log_format)


def copy_semantic_models() -> bool:
    """冻结态首跑：bundle semantic_models/ → DATA_DIR/semantic_models。

    开发态、目标已存在（用户可能已编辑）或 bundle 缺源时不复制，返回 False。
    """
    if not is_frozen():
        return False
    target = Path(config.DATA_DIR) / "semantic_models"
    if target.exists():
        return False
    source = resolve_bundle_dir() / "semantic_models"
    if not source.is_dir():
        logger.warning("bundle 内未找到 semantic_models/，跳过复制：{}", source)
        return False
    shutil.copytree(source, target, dirs_exist_ok=True)
    return True


def find_free_port(
    start: int = DEFAULT_STREAMLIT_PORT, attempts: int = _PORT_SCAN_ATTEMPTS
) -> int:
    """自 start 起用 socket bind 探测可用端口（占用递增），返回可绑定端口。"""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 刻意不设 SO_REUSEADDR：macOS 上它会让探测在已有通配符监听
            # （*:port）时仍绑定 127.0.0.1:port 成功，误报可用。裸 bind 最
            # 严格——探测可绑定则 tornado/streamlit 必然可绑定。
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"未找到可用端口：{start}..{start + attempts - 1} 均被占用")


def _open_browser_when_ready(
    port: int, timeout: float = _BROWSER_READY_TIMEOUT_SECONDS
) -> None:
    """守护线程轮询端口，服务就绪后打开浏览器（bootstrap.run 阻塞主线程）。"""
    url = f"http://127.0.0.1:{port}"

    def _wait_and_open() -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                    webbrowser.open(url)
                    return
            except OSError:
                time.sleep(0.2)
        logger.warning("等待 Streamlit 就绪超时（{}s），未自动打开浏览器：{}", timeout, url)

    threading.Thread(target=_wait_and_open, name="browser-open", daemon=True).start()


def launch_streamlit() -> None:
    """进程内启动 Streamlit（streamlit 1.29.0 bootstrap API）。

    1.29.0 的 bootstrap.run 签名为 (main_script_path, command_line, args,
    flag_options)，无 is_hello 参数；cli._main_run 依赖 click 上下文，不能
    在进程外直接调用。配置旗标经 load_config_options 覆盖 config.toml。
    """
    from streamlit.web import bootstrap  # 延迟导入：helper 单测不拉起 streamlit

    main_script = resolve_main_script()
    port = find_free_port()
    flag_options = {
        "server_headless": True,
        "server_address": "127.0.0.1",
        "server_port": port,
        # 打包态不监视 bundle 文件变更；桌面应用不上报使用统计
        "server_fileWatcherType": "none",
        "browser_gatherUsageStats": False,
        # 冻结态 streamlit/config.py 的 __file__ 不含 "site-packages"，
        # global.developmentMode 会被误判为 True，与 server.port 冲突触发
        # AssertionError（_check_conflicts）。显式关闭，开发态同值无副作用。
        "global_developmentMode": False,
    }
    bootstrap.load_config_options(flag_options)
    logger.info("启动 Streamlit：{}（http://127.0.0.1:{}）", main_script, port)
    _open_browser_when_ready(port)
    # 阻塞直至服务关闭（信号处理器负责停机）
    bootstrap.run(str(main_script), None, [], flag_options)


def _exec_multiprocessing_child() -> bool:
    """冻结态拦截 multiprocessing 子进程调用（PyInstaller hook 修复）。

    CPython multiprocessing（spawn / resource_tracker）以
    `sys.executable -B -S -I -c <code>` 拉起子进程；PyInstaller 冻结 exe 不支持
    -c 旗标，会重新执行入口脚本——若不拦截，sqlfluff 校验触发的
    resource_tracker 子进程将再跑一遍 main()，多起一个 Streamlit 服务（多占
    端口、多开浏览器标签）。此处按 CPython 语义执行 -c 代码并返回 True，
    调用方随即退出；开发态恒返回 False（行为逐字不变）。
    """
    if not is_frozen():
        return False
    argv = sys.argv[1:]
    if "-c" not in argv:
        return False
    idx = argv.index("-c")
    if idx + 1 >= len(argv):
        return False
    code = argv[idx + 1]
    sys.argv = ["-c"] + argv[idx + 2:]
    exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})
    return True


def main() -> None:
    """打包入口：数据目录初始化 → 早期日志 sink → 种子复制（冻结态）→ 起 Streamlit。"""
    data_dir = ensure_data_dir()
    setup_early_log_sink()
    logger.info("数据目录就绪：{}", data_dir)
    if copy_semantic_models():
        logger.info("已复制 semantic_models → {}", data_dir / "semantic_models")
    launch_streamlit()


if __name__ == "__main__":
    if not _exec_multiprocessing_child():
        main()
