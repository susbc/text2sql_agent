"""启动器 launcher.py 单元测试（打包 spec §5.2）。

只测 helper（数据目录初始化/.env 模板/semantic_models 复制/端口探测/路径解析），
不真正启动 Streamlit；main() 编排测试以 spy 替代 launch_streamlit。
"""
import socket
import sys
from pathlib import Path

import pytest
from loguru import logger

import config
import launcher


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """把 config.DATA_DIR 指到临时目录（helper 须在调用时动态读取）。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


def _make_bundle(tmp_path):
    """构造含 semantic_models 样例的 bundle 资源目录。"""
    bundle = tmp_path / "bundle"
    models = bundle / "semantic_models"
    (models / "schema").mkdir(parents=True)
    (models / "default.yaml").write_text("name: default\n", encoding="utf-8")
    (models / "schema" / "t.yaml").write_text("table: t\n", encoding="utf-8")
    return bundle


def test_first_run_writes_env_template(data_dir):
    assert not (data_dir / ".env").exists()
    result = launcher.ensure_data_dir()
    assert result == data_dir
    assert (data_dir / "logs").is_dir()
    text = (data_dir / ".env").read_text(encoding="utf-8")
    assert "SQL_DIALECT=sqlite" in text
    assert f"SQLITE_PATH={data_dir / 'text2sql.db'}" in text
    assert "NEO4J_ENABLED=false" in text
    assert "LLM_PROVIDER=" in text
    assert "LLM_MODEL=" in text
    assert "EMBEDDING_PROVIDER=" in text


def test_existing_env_not_overwritten(data_dir):
    existing = "# 用户自定义\nSQL_DIALECT=mysql\nLLM_API_KEY=secret\n"
    (data_dir / ".env").write_text(existing, encoding="utf-8")
    launcher.ensure_data_dir()
    assert (data_dir / ".env").read_text(encoding="utf-8") == existing
    assert (data_dir / "logs").is_dir()


def test_ensure_data_dir_idempotent(data_dir):
    launcher.ensure_data_dir()
    first = (data_dir / ".env").read_text(encoding="utf-8")
    launcher.ensure_data_dir()
    assert (data_dir / ".env").read_text(encoding="utf-8") == first


def test_ensure_data_dir_creates_missing_parents(tmp_path, monkeypatch):
    nested = tmp_path / "a" / "b"
    monkeypatch.setattr(config, "DATA_DIR", nested)
    launcher.ensure_data_dir()
    assert (nested / "logs").is_dir()
    assert (nested / ".env").is_file()


def test_semantic_models_copied_when_frozen(tmp_path, monkeypatch):
    bundle = _make_bundle(tmp_path)
    data = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert launcher.copy_semantic_models() is True
    copied = data / "semantic_models" / "default.yaml"
    assert copied.read_text(encoding="utf-8") == "name: default\n"
    assert (data / "semantic_models" / "schema" / "t.yaml").is_file()


def test_semantic_models_existing_target_untouched(tmp_path, monkeypatch):
    bundle = _make_bundle(tmp_path)
    data = tmp_path / "data"
    target = data / "semantic_models"
    target.mkdir(parents=True)
    (target / "custom.yaml").write_text("keep: me\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert launcher.copy_semantic_models() is False
    assert (target / "custom.yaml").read_text(encoding="utf-8") == "keep: me\n"
    assert not (target / "default.yaml").exists()


def test_semantic_models_not_copied_in_dev(data_dir, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert launcher.copy_semantic_models() is False
    assert not (data_dir / "semantic_models").exists()


def test_find_free_port_returns_bindable():
    port = launcher.find_free_port()
    assert port >= 8501
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))


def test_find_free_port_skips_occupied():
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("127.0.0.1", 8501))
        blocker.listen(1)
    except OSError:
        # 8501 已被本机其他进程占用：find_free_port 同样必须跳过它
        blocker.close()
        blocker = None
    try:
        port = launcher.find_free_port()
        assert port > 8501
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
    finally:
        if blocker is not None:
            blocker.close()


def test_resolve_bundle_dir_dev_fallback(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert launcher.resolve_bundle_dir() == Path(launcher.__file__).resolve().parent
    assert launcher.resolve_bundle_dir() == config.PROJECT_ROOT


def test_resolve_bundle_dir_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert launcher.resolve_bundle_dir() == tmp_path


def test_resolve_bundle_dir_onedir_internal(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "text2sql-agent"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(exe))
    internal = tmp_path / "_internal"
    internal.mkdir()
    assert launcher.resolve_bundle_dir() == internal
    # 旧版 onedir 布局（datas 与可执行文件同级）回退到 exe 所在目录
    internal.rmdir()
    assert launcher.resolve_bundle_dir() == tmp_path


def test_resolve_main_script_dev(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert launcher.resolve_main_script() == config.PROJECT_ROOT / "app.py"


def test_resolve_main_script_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert launcher.resolve_main_script() == tmp_path / "app.py"


def test_main_orchestrates_without_starting_server(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOG_FILE", tmp_path / "logs" / "app.log")
    calls = []
    monkeypatch.setattr(launcher, "launch_streamlit", lambda: calls.append("launch"))
    try:
        launcher.main()
        assert calls == ["launch"]
        assert (data_dir / ".env").is_file()
        assert (data_dir / "logs").is_dir()
    finally:
        # main() 挂的早期 sink 须回收，避免泄漏到后续测试
        logger.remove()
        logger.add(sys.stderr)


def test_early_sink_port_line_survives_app_reconfigure(tmp_path, monkeypatch):
    """I6/R8：端口行经早期 sink 落盘；app.py 重配 logging 后仍在文件。"""
    log_file = tmp_path / "logs" / "app.log"
    monkeypatch.setattr(config, "LOG_FILE", log_file)
    sink_id = launcher.setup_early_log_sink()
    try:
        assert isinstance(sink_id, int)
        assert log_file.parent.is_dir()  # 父目录自动创建
        logger.info("启动 Streamlit：{}（http://127.0.0.1:{}）", "app.py", 8502)
        # 模拟 app.py 重配 logging：logger.remove() 清掉全部 sink 再挂旋转文件 sink
        logger.remove()
        logger.add(log_file, level="INFO", rotation="1 day")
        logger.info("重配后的后续日志")
        text = log_file.read_text(encoding="utf-8")
        assert "http://127.0.0.1:8502" in text
        assert "重配后的后续日志" in text
    finally:
        logger.remove()
        logger.add(sys.stderr)


def test_main_installs_early_sink_before_launch(data_dir, tmp_path, monkeypatch):
    """I6：main() 在 launch_streamlit 之前挂早期 sink，端口行/数据目录行落盘。"""
    log_file = tmp_path / "early" / "app.log"
    monkeypatch.setattr(config, "LOG_FILE", log_file)
    seen = {}

    def fake_launch():
        logger.info("启动 Streamlit：{}（http://127.0.0.1:{}）", "app.py", 8502)
        seen["text"] = log_file.read_text(encoding="utf-8")

    monkeypatch.setattr(launcher, "launch_streamlit", fake_launch)
    try:
        launcher.main()
        assert "http://127.0.0.1:8502" in seen["text"]
        assert "数据目录就绪" in seen["text"]
    finally:
        logger.remove()
        logger.add(sys.stderr)
