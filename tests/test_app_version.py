"""运行时版本常量与更新检查配置测试（自动更新 spec §3.1/§3.3）。

APP_VERSION 读根 VERSION 文件（单一事实源），缺失/不可读回退 "0.0.0"；
UPDATE_* 默认值：启用 True / 间隔 6 小时 / 仓库 susbc/text2sql_agent。
reload 副作用沿用 test_frozen_paths 模式：finally 中 reload(config) 恢复开发态。
"""
import importlib
import importlib.util
import shutil
from pathlib import Path

import dotenv

import config

UPDATE_ENV_VARS = (
    "UPDATE_CHECK_ENABLED",
    "UPDATE_CHECK_INTERVAL_HOURS",
    "UPDATE_GITHUB_REPO",
)


def test_app_version_matches_version_file():
    """APP_VERSION 与根 VERSION 文件内容一致（当前 1.0.0）。"""
    expected = (config.PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert config.APP_VERSION == expected
    assert config.APP_VERSION == "1.0.0"


def test_app_version_fallback_when_missing(monkeypatch):
    """VERSION 缺失/不可读时 APP_VERSION 回退 "0.0.0"，不阻塞启动。"""
    real_read_text = Path.read_text

    def missing_version(self, *args, **kwargs):
        if self.name == "VERSION":
            raise FileNotFoundError(str(self))
        return real_read_text(self, *args, **kwargs)

    try:
        with monkeypatch.context() as m:
            m.setattr(Path, "read_text", missing_version)
            importlib.reload(config)
            assert config.APP_VERSION == "0.0.0"
    finally:
        importlib.reload(config)


def test_update_config_defaults(monkeypatch):
    """env 无覆盖时 UPDATE_* 取 spec §3.3 默认值。"""
    try:
        with monkeypatch.context() as m:
            for var in UPDATE_ENV_VARS:
                m.delenv(var, raising=False)
            # 屏蔽 .env 注入，保证默认值断言与开发者本地 .env 内容无关
            m.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
            importlib.reload(config)
            assert config.UPDATE_CHECK_ENABLED is True
            assert config.UPDATE_CHECK_INTERVAL_HOURS == 6
            assert config.UPDATE_GITHUB_REPO == "susbc/text2sql_agent"
    finally:
        importlib.reload(config)


def _load_config_copy(directory: Path):
    """把 config.py 复制到 directory 并以独立模块名加载，模拟冻结态 bundle 布局。

    冻结态 VERSION 由 spec datas 收集到 config.py 同级（_internal），故
    APP_VERSION 走同一 `Path(__file__).parent / "VERSION"` 路径即可读。
    importlib.reload 会经 meta_path 重新定位真实 config.py（重置 __file__），
    无法用 monkeypatch __file__+reload 模拟；改为加载副本，既跑真实解析代码，
    又不改动真实 config 模块（无需 reload 恢复）。
    """
    shutil.copy(Path(config.__file__), directory / "config.py")
    spec = importlib.util.spec_from_file_location("_config_frozen_probe", directory / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_version_frozen_reads_bundled_version(tmp_path):
    """冻结态：config.py 与 VERSION 同在 bundle 目录，APP_VERSION 同路径可读。"""
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    module = _load_config_copy(tmp_path)
    assert module.PROJECT_ROOT == tmp_path
    assert module.APP_VERSION == "9.9.9"


def test_app_version_frozen_missing_fallback(tmp_path):
    """冻结态 bundle 缺 VERSION → 回退 "0.0.0"，不阻塞启动。"""
    module = _load_config_copy(tmp_path)
    assert module.APP_VERSION == "0.0.0"
