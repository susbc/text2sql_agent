"""运行时版本常量与更新检查配置测试（自动更新 spec §3.1/§3.3）。

APP_VERSION 读根 VERSION 文件（单一事实源），缺失/不可读回退 "0.0.0"；
UPDATE_* 默认值：启用 True / 间隔 6 小时 / 仓库 susbc/text2sql_agent。
reload 副作用沿用 test_frozen_paths 模式：finally 中 reload(config) 恢复开发态。
"""
import importlib
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
