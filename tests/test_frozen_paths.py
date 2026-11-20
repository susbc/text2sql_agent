"""冻结态（PyInstaller）数据路径适配测试（打包 spec §5.1）。

开发态（sys.frozen 不存在）路径必须与既有行为逐字一致；
冻结态重定向到 platformdirs 用户数据目录，env 覆盖仍优先。
每个用例结束后 reload(config) 恢复开发态，避免污染其他测试。
"""
import importlib
import ntpath
import os
import sys
import types

import dotenv
import platformdirs
from platformdirs import windows as pwin
from platformdirs.macos import MacOS
from platformdirs.unix import Unix

import config

PATH_ENV_VARS = ("SQLITE_PATH", "INDEX_CACHE_DIR", "SEMANTIC_MODEL_DIR")


def _spy_load_dotenv(monkeypatch, calls):
    """记录 reload(config) 期间 load_dotenv 的调用参数（reload 会重新绑定）。"""
    real = dotenv.load_dotenv

    def spy(dotenv_path=None, *args, **kwargs):
        calls.append(dotenv_path)
        return real(dotenv_path, *args, **kwargs)

    monkeypatch.setattr(dotenv, "load_dotenv", spy)


def test_dev_mode_uses_project_data(monkeypatch):
    """开发态：DATA_DIR=PROJECT_ROOT/data，各路径与既有默认值逐字一致。"""
    assert not getattr(sys, "frozen", False)
    calls = []
    try:
        with monkeypatch.context() as m:
            for var in PATH_ENV_VARS:
                m.delenv(var, raising=False)
            _spy_load_dotenv(m, calls)
            importlib.reload(config)
            root = config.PROJECT_ROOT
            assert config.DATA_DIR == root / "data"
            assert config.SQLITE_PATH == str(root / "data" / "text2sql.db")
            assert config.SQLITE_PATH.endswith(os.path.join("data", "text2sql.db"))
            assert config.INDEX_CACHE_DIR == str(root / "data" / "index_cache")
            # 开发态保持相对路径默认值，不得改为 DATA_DIR 绝对路径
            assert config.SEMANTIC_MODEL_DIR == "semantic_models"
            assert config.LOG_FILE == root / "logs" / "app.log"
            # 开发态 load_dotenv() 保持无参调用
            assert calls == [None]
    finally:
        importlib.reload(config)


def test_frozen_mode_uses_user_data_dir(monkeypatch, tmp_path):
    """冻结态：DATA_DIR=用户数据目录，SQLITE/索引/语义模型/日志/.env 均在其下。"""
    calls = []
    try:
        with monkeypatch.context() as m:
            m.setattr(sys, "frozen", True, raising=False)
            m.setattr(platformdirs, "user_data_dir", lambda *a, **k: str(tmp_path))
            for var in PATH_ENV_VARS:
                m.delenv(var, raising=False)
            _spy_load_dotenv(m, calls)
            importlib.reload(config)
            assert config.DATA_DIR == tmp_path
            assert config.SQLITE_PATH == str(tmp_path / "text2sql.db")
            assert config.INDEX_CACHE_DIR == str(tmp_path / "index_cache")
            assert config.SEMANTIC_MODEL_DIR == str(tmp_path / "semantic_models")
            assert config.LOG_FILE == tmp_path / "logs" / "app.log"
            # 冻结态 .env 从 DATA_DIR 加载
            assert calls == [tmp_path / ".env"]
    finally:
        importlib.reload(config)


def test_frozen_passes_appauthor_false(monkeypatch, tmp_path):
    """I2：config 必须以 appauthor=False 调 user_data_dir（防 Windows 双层路径）。"""
    captured = {}

    def spy(appname, *args, **kwargs):
        captured["appname"] = appname
        captured["kwargs"] = kwargs
        return str(tmp_path)

    try:
        with monkeypatch.context() as m:
            m.setattr(sys, "frozen", True, raising=False)
            m.setattr(platformdirs, "user_data_dir", spy)
            importlib.reload(config)
            assert captured["appname"] == "text2sql-agent"
            assert captured["kwargs"].get("appauthor") is False
    finally:
        importlib.reload(config)


def test_windows_data_dir_single_layer(monkeypatch):
    """I2：Windows appauthor=False → %LOCALAPPDATA%\\text2sql-agent 单层。

    platformdirs.windows 在非 Windows 上经 ctypes 解析真实 Windows 目录会
    NotImplementedError，故桩 get_win_folder 并借 ntpath 复现 Windows 路径语义。
    """
    monkeypatch.setattr(
        pwin, "get_win_folder", lambda csidl: r"C:\Users\tester\AppData\Local"
    )
    monkeypatch.setattr(pwin, "os", types.SimpleNamespace(path=ntpath))
    single = pwin.Windows(appname="text2sql-agent", appauthor=False).user_data_dir
    assert single == r"C:\Users\tester\AppData\Local\text2sql-agent"
    # 对照：不带 appauthor=False 时 author 层翻倍（修复前的 bug 形状）
    double = pwin.Windows(appname="text2sql-agent").user_data_dir
    assert double == r"C:\Users\tester\AppData\Local\text2sql-agent\text2sql-agent"


def test_macos_linux_paths_unaffected_by_appauthor():
    """I2：appauthor=False 对 macOS/Linux 路径无影响（与默认调用逐字一致）。"""
    assert (
        MacOS(appname="text2sql-agent", appauthor=False).user_data_dir
        == MacOS(appname="text2sql-agent").user_data_dir
    )
    assert (
        Unix(appname="text2sql-agent", appauthor=False).user_data_dir
        == Unix(appname="text2sql-agent").user_data_dir
    )


def test_frozen_env_override_still_wins(monkeypatch, tmp_path):
    """冻结态：显式 env 覆盖仍优先于 DATA_DIR 派生默认值。"""
    custom = tmp_path / "elsewhere"
    try:
        with monkeypatch.context() as m:
            m.setattr(sys, "frozen", True, raising=False)
            m.setattr(platformdirs, "user_data_dir", lambda *a, **k: str(tmp_path))
            m.setenv("SQLITE_PATH", str(custom / "my.db"))
            m.setenv("INDEX_CACHE_DIR", str(custom / "idx"))
            m.setenv("SEMANTIC_MODEL_DIR", str(custom / "models"))
            importlib.reload(config)
            assert config.DATA_DIR == tmp_path
            assert config.SQLITE_PATH == str(custom / "my.db")
            assert config.INDEX_CACHE_DIR == str(custom / "idx")
            assert config.SEMANTIC_MODEL_DIR == str(custom / "models")
    finally:
        importlib.reload(config)
