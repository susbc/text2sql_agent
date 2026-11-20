"""首跑向导配置持久化测试（打包 spec §5.3 / §9-Q1/Q3）。

覆盖：
- write_env_config 合并写回 DATA_DIR/.env：保留注释/顺序/无关键，原子写；
- 持久化跨"重启"生效（冻结态 reload(config) 模拟新进程加载 DATA_DIR/.env）；
- model_config 保存成功后才持久化（AppTest），失败不写；
- 未配置 LLM（云端缺 Key / Ollama 不可达）时 system_info 显示首跑引导（AppTest）。

开发态 DATA_DIR=PROJECT_ROOT/data，持久化落 data/.env（不碰根目录用户 .env）；
测试一律把 config.DATA_DIR 指到 tmp_path，不污染真实数据目录。
"""
from __future__ import annotations

import importlib
import os
import sys
import urllib.error
from pathlib import Path
from typing import Any

import platformdirs
import pytest

import config
from core.config_persistence import write_env_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PY = PROJECT_ROOT / "app.py"

pytest.importorskip("streamlit", reason="Streamlit 未安装")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.pages import system_info  # noqa: E402
from config import (  # noqa: E402
    EMBEDDING_PROVIDERS,
    LLM_PROVIDERS,
)
from core.app_context import ApplicationConfigurationError  # noqa: E402

KEY_PROVIDER = next(k for k, v in LLM_PROVIDERS.items() if v["needs_api_key"])
KEY_PROVIDER_LABEL = LLM_PROVIDERS[KEY_PROVIDER]["label"]
EMB_KEY_PROVIDER = next(k for k, v in EMBEDDING_PROVIDERS.items() if v["needs_api_key"])
EMB_KEY_PROVIDER_LABEL = EMBEDDING_PROVIDERS[EMB_KEY_PROVIDER]["label"]

GUIDANCE_MARKER = "首次运行引导"

# autouse 桩会把 _ollama_reachable 替换掉；探测本身的单测用原始函数
_REAL_OLLAMA_PROBE = system_info._ollama_reachable

# 冻结态 reload 前需清掉的模型配置 env（模拟新进程：OS env 未携带这些键）
_MODEL_ENV_VARS = (
    "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL",
    "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_API_KEY", "EMBEDDING_API_BASE",
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """把 config.DATA_DIR 指到临时目录（helper 须在调用时动态读取）。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _stub_ollama_probe(monkeypatch):
    """默认把 Ollama 可达性探测桩为可达：测试不依赖真实网络/本机 Ollama 状态。"""
    monkeypatch.setattr(system_info, "_ollama_reachable", lambda base_url="": True)


# ==================== write_env_config：合并/保留/原子写 ====================


def test_write_env_config_persists_and_preserves(data_dir):
    env_path = data_dir / ".env"
    env_path.write_text(
        "# 用户自定义注释\nSQL_DIALECT=sqlite\nCUSTOM_KEY=keep-me\nLLM_API_KEY=old-key\n",
        encoding="utf-8",
    )
    write_env_config({"LLM_API_KEY": "sk-x"})
    text = env_path.read_text(encoding="utf-8")
    assert "LLM_API_KEY=sk-x" in text
    assert "old-key" not in text
    # 无关键与注释原样保留，行序不变
    assert "SQL_DIALECT=sqlite" in text
    assert "CUSTOM_KEY=keep-me" in text
    assert "# 用户自定义注释" in text
    assert text.index("SQL_DIALECT=sqlite") < text.index("CUSTOM_KEY=keep-me")
    assert text.splitlines()[0] == "# 用户自定义注释"


def test_write_env_config_creates_when_absent(data_dir):
    env_path = data_dir / ".env"
    assert not env_path.exists()
    write_env_config({"LLM_PROVIDER": "dashscope", "LLM_API_KEY": "sk-new"})
    assert env_path.exists()
    text = env_path.read_text(encoding="utf-8")
    assert "LLM_PROVIDER=dashscope" in text
    assert "LLM_API_KEY=sk-new" in text


def test_write_env_config_atomic_replace(data_dir, monkeypatch):
    """必须走同目录临时文件 + os.replace 原子替换（不得直接截断写目标文件）。"""
    env_path = data_dir / ".env"
    env_path.write_text("SQL_DIALECT=sqlite\n", encoding="utf-8")
    calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    write_env_config({"LLM_API_KEY": "sk-atomic"})
    assert len(calls) == 1
    src, dst = calls[0]
    assert Path(dst) == env_path
    # 临时文件必须与目标同目录（跨文件系统 rename 非原子）
    assert Path(src).parent == data_dir
    assert Path(src) != env_path
    assert not Path(src).exists()  # 替换后临时文件不复存在
    assert "LLM_API_KEY=sk-atomic" in env_path.read_text(encoding="utf-8")


def test_write_env_config_failed_replace_keeps_original(data_dir, monkeypatch):
    """替换中途失败：既有 .env 逐字不变，临时文件清理，异常上抛。"""
    env_path = data_dir / ".env"
    original = "# 既有配置\nSQL_DIALECT=sqlite\nLLM_API_KEY=old\n"
    env_path.write_text(original, encoding="utf-8")

    def broken_replace(src, dst):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError, match="simulated disk failure"):
        write_env_config({"LLM_API_KEY": "sk-new"})
    assert env_path.read_text(encoding="utf-8") == original
    assert [p.name for p in data_dir.iterdir()] == [".env"]  # 无临时文件残留


def test_write_env_config_updates_all_duplicate_occurrences(data_dir):
    """同名键出现多次时全部更新，避免 dotenv 后值覆盖导致旧值复活。"""
    env_path = data_dir / ".env"
    env_path.write_text("LLM_API_KEY=old-1\nOTHER=1\nLLM_API_KEY=old-2\n", encoding="utf-8")
    write_env_config({"LLM_API_KEY": "sk-dup"})
    text = env_path.read_text(encoding="utf-8")
    assert "old-1" not in text and "old-2" not in text
    assert text.count("LLM_API_KEY=sk-dup") == 2
    assert "OTHER=1" in text


# ==================== 跨重启存活（冻结态 reload 模拟） ====================


def test_config_survives_reload(data_dir, monkeypatch):
    """写入 DATA_DIR/.env 后模拟冻结态重启：reload(config) 必须读到持久化值。"""
    write_env_config({
        "LLM_PROVIDER": "dashscope",
        "LLM_MODEL": "qwen-max",
        "LLM_API_KEY": "sk-survives-reload",
        "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "EMBEDDING_PROVIDER": "dashscope",
        "EMBEDDING_MODEL": "text-embedding-v3",
        "EMBEDDING_API_KEY": "sk-emb-survives",
    })
    try:
        with monkeypatch.context() as m:
            m.setattr(sys, "frozen", True, raising=False)
            m.setattr(platformdirs, "user_data_dir", lambda *a, **k: str(data_dir))
            for var in _MODEL_ENV_VARS:
                m.delenv(var, raising=False)
            importlib.reload(config)
            assert config.DATA_DIR == data_dir
            assert config.LLM_PROVIDER == "dashscope"
            assert config.LLM_MODEL == "qwen-max"
            assert config.LLM_API_KEY == "sk-survives-reload"
            assert config.EMBEDDING_PROVIDER == "dashscope"
            assert config.EMBEDDING_API_KEY == "sk-emb-survives"
    finally:
        # 恢复开发态：清掉 reload 期间 load_dotenv 注入的键，再按根 .env 重载
        for var in _MODEL_ENV_VARS:
            os.environ.pop(var, None)
        importlib.reload(config)


# ==================== AppTest：保存成功才持久化 ====================


class FakeContext:
    """只实现 app.py 会触到的 ApplicationContext 表面（离线、无数据库）。"""

    def __init__(self, config_dict: dict[str, Any]):
        self._config = dict(config_dict)
        self.db_client = None
        self.neo4j_client = None
        self.sql_generator = None
        self.semantic_registry = None
        self.initialization_error = None
        self.llm_reload_calls: list[dict[str, Any]] = []
        self.embedding_reload_calls: list[dict[str, Any]] = []

    @property
    def config(self) -> dict[str, Any]:
        return dict(self._config)

    def ensure_initialized(self) -> bool:
        return True

    def reset(self) -> None:
        pass

    def reload_llm(self, **updates: Any) -> None:
        self.llm_reload_calls.append(dict(updates))
        self._config.update(updates)

    def reload_embedding(self, **updates: Any) -> None:
        self.embedding_reload_calls.append(dict(updates))
        self._config.update(updates)


class FailingContext(FakeContext):
    def reload_llm(self, **updates: Any) -> None:
        raise ApplicationConfigurationError("配置无效")

    def reload_embedding(self, **updates: Any) -> None:
        raise ApplicationConfigurationError("配置无效")


def _base_config(**overrides: Any) -> dict[str, Any]:
    values = {
        "llm_provider": KEY_PROVIDER,
        "llm_model": LLM_PROVIDERS[KEY_PROVIDER]["default_model"],
        "llm_api_key": "",
        "llm_base_url": "",
        "embedding_provider": "ollama",
        "embedding_model": "bge-m3:latest",
        "embedding_api_key": "",
    }
    values.update(overrides)
    return values


def _launch(ctx: FakeContext) -> AppTest:
    at = AppTest.from_file(str(APP_PY), default_timeout=90)
    at.session_state["initialized"] = True
    at.session_state["app_context"] = ctx
    at.run()
    assert not at.exception, f"app.py 渲染异常：{at.exception}"
    return at


def test_save_llm_persists_to_data_dir_env(data_dir):
    ctx = FakeContext(_base_config())
    at = _launch(ctx)
    at.text_input(key="cfg_llm_api_key").set_value("sk-brand-new-key")
    at.button(key="btn_save_llm").click()
    at.run()
    assert not at.exception
    text = (data_dir / ".env").read_text(encoding="utf-8")
    assert f"LLM_PROVIDER={KEY_PROVIDER}" in text
    assert "LLM_API_KEY=sk-brand-new-key" in text
    assert f"LLM_MODEL={LLM_PROVIDERS[KEY_PROVIDER]['default_model']}" in text
    assert "LLM_BASE_URL=" in text


def test_save_llm_blank_key_persists_active_key(data_dir):
    """留空沿用当前密钥：持久化的必须是解析后的生效密钥，而非空输入。"""
    ctx = FakeContext(_base_config(llm_api_key="sk-active-secret"))
    at = _launch(ctx)
    at.button(key="btn_save_llm").click()
    at.run()
    assert not at.exception
    text = (data_dir / ".env").read_text(encoding="utf-8")
    assert "LLM_API_KEY=sk-active-secret" in text


def test_failed_save_does_not_persist(data_dir):
    ctx = FailingContext(_base_config())
    at = _launch(ctx)
    at.text_input(key="cfg_llm_api_key").set_value("sk-should-not-persist")
    at.button(key="btn_save_llm").click()
    at.run()
    assert at.error  # 失败必须呈现
    assert not (data_dir / ".env").exists()


def test_save_embedding_persists_to_data_dir_env(data_dir):
    ctx = FakeContext(_base_config())
    at = _launch(ctx)
    at.selectbox(key="cfg_emb_provider").set_value(EMB_KEY_PROVIDER_LABEL)
    at.run()
    at.text_input(key="cfg_emb_api_key").set_value("sk-emb-new")
    at.button(key="btn_save_emb").click()
    at.run()
    assert not at.exception
    text = (data_dir / ".env").read_text(encoding="utf-8")
    assert f"EMBEDDING_PROVIDER={EMB_KEY_PROVIDER}" in text
    assert "EMBEDDING_API_KEY=sk-emb-new" in text
    assert f"EMBEDDING_MODEL={EMBEDDING_PROVIDERS[EMB_KEY_PROVIDER]['default_model']}" in text


def test_failed_embedding_save_does_not_persist(data_dir):
    ctx = FailingContext(_base_config())
    at = _launch(ctx)
    at.button(key="btn_save_emb").click()
    at.run()
    assert at.error
    assert not (data_dir / ".env").exists()


# ==================== AppTest：未配置首跑引导 ====================


def _info_text(at: AppTest) -> str:
    return " ".join(i.value for i in at.info)


def test_unconfigured_llm_shows_first_run_guidance(monkeypatch):
    """无 Key 且 Ollama 不可达（首跑默认态）→ 系统信息显示引导。"""
    monkeypatch.setattr(system_info, "_ollama_reachable", lambda base_url="": False)
    ctx = FakeContext(_base_config(llm_provider="ollama", llm_api_key=""))
    at = _launch(ctx)
    text = _info_text(at)
    assert GUIDANCE_MARKER in text
    # 两条配置路线 + 降级说明都要讲到
    assert "gemma4:E4B" in text
    assert "bge-m3:latest" in text
    assert "API Key" in text
    assert "DashScope" in text
    assert "TF-IDF" in text


def test_cloud_provider_without_key_shows_guidance():
    ctx = FakeContext(_base_config(llm_provider=KEY_PROVIDER, llm_api_key=""))
    at = _launch(ctx)
    assert GUIDANCE_MARKER in _info_text(at)


def test_configured_llm_hides_guidance(monkeypatch):
    # 云端提供商 + 生效 Key → 已配置
    ctx = FakeContext(_base_config(llm_provider=KEY_PROVIDER, llm_api_key="sk-active"))
    at = _launch(ctx)
    assert GUIDANCE_MARKER not in _info_text(at)
    # 本地 Ollama 可达 → 已配置（无需 Key）
    monkeypatch.setattr(system_info, "_ollama_reachable", lambda base_url="": True)
    ctx = FakeContext(_base_config(llm_provider="ollama", llm_api_key=""))
    at = _launch(ctx)
    assert GUIDANCE_MARKER not in _info_text(at)


# ==================== Ollama 探测：地址回退链与容错 ====================


class _FakeResp:
    def read(self, n):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_ollama_probe_url_follows_factory_fallback(monkeypatch):
    """探测地址必须与 llm_factory 一致：base_url → OLLAMA_HOST → localhost。"""
    captured = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(system_info.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert _REAL_OLLAMA_PROBE("") is True
    assert captured["url"] == "http://localhost:11434/api/tags"
    assert captured["timeout"] <= 2.0  # 短超时，不得拖慢渲染
    assert _REAL_OLLAMA_PROBE("http://myhost:1234/") is True
    assert captured["url"] == "http://myhost:1234/api/tags"
    monkeypatch.setenv("OLLAMA_HOST", "http://envhost:9999")
    assert _REAL_OLLAMA_PROBE("") is True
    assert captured["url"] == "http://envhost:9999/api/tags"
    # 显式 base_url 优先于 OLLAMA_HOST
    assert _REAL_OLLAMA_PROBE("http://explicit:11434") is True
    assert captured["url"] == "http://explicit:11434/api/tags"


def test_ollama_probe_swallows_errors(monkeypatch):
    """连接失败/超时 → 不可达；HTTPError（服务在监听）→ 可达；绝不抛异常。"""

    def refuse(url, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(system_info.urllib.request, "urlopen", refuse)
    assert _REAL_OLLAMA_PROBE("") is False

    def http_error(url, timeout=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(system_info.urllib.request, "urlopen", http_error)
    assert _REAL_OLLAMA_PROBE("") is True
