"""侧栏新版横幅 + 启动检查钩子的 AppTest 集成测试（自动更新 spec §3.4/§3.5）。

覆盖：
- mock 缓存有新版 → 横幅（info 含「发现新版本」+ 下载链接 url + 关闭按钮）；
- 点「关闭」按版本隐藏（session_state.update_dismissed=latest），rerun 仍隐藏；
- dismiss 后出现更新版本 → 横幅重新触发；
- 缓存 None / UPDATE_CHECK_ENABLED=False → 无横幅；
- initialize_system 调用 start_update_checker（启动钩子）；禁用时不起线程。

全程离线：autouse fixture 重置检查器缓存/启动标记并禁止网络调用，
启动钩子以 mock 替代，测试期间绝不启动真实后台线程。

AppTest 1.29 的树解析不会清理 rerun 后未重新发射的 link_button/button 旧节点
（真实前端会清理），因此「横幅已隐藏」以 at.info 文案 + session_state 断言，
不以 link_button/button 节点缺失断言。
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest import mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PY = PROJECT_ROOT / "app.py"

pytest.importorskip("streamlit", reason="Streamlit 未安装")
from streamlit.testing.v1 import AppTest  # noqa: E402

import config  # noqa: E402
from core import update_checker  # noqa: E402
from tests.test_model_config_panel import FakeContext, _base_config  # noqa: E402

RELEASE_URL = "https://example/release"
UPDATE_999 = {"latest_version": "9.9.9", "url": RELEASE_URL, "name": "x"}
UPDATE_1000 = {"latest_version": "10.0.0", "url": RELEASE_URL, "name": "x"}


def _no_network(*args, **kwargs):
    raise AssertionError("测试期间不得发起更新检查网络请求")


@pytest.fixture(autouse=True)
def _offline_update_checker(monkeypatch):
    """重置检查器全局状态、切断网络，并把启动钩子换成 mock（防真实线程）。"""
    monkeypatch.setattr(update_checker, "_started", False)
    monkeypatch.setattr(update_checker, "_cache", None)
    monkeypatch.setattr(update_checker, "fetch_latest_release", _no_network)
    monkeypatch.setattr(update_checker, "check_for_update", _no_network)
    # bootstrap 钩子实际调用的名字；raising=False 兼容 RED 阶段（属性尚未实现）
    monkeypatch.setattr(
        "app.bootstrap.start_update_checker", mock.MagicMock(), raising=False
    )


def _launch() -> AppTest:
    """沿用 test_model_config_panel 的密封启动：预置 initialized 跳过真实初始化。"""
    at = AppTest.from_file(str(APP_PY), default_timeout=90)
    at.session_state["initialized"] = True
    at.session_state["app_context"] = FakeContext(_base_config())
    at.run()
    assert not at.exception, f"app.py 渲染异常：{at.exception}"
    return at


def _banner_texts(at: AppTest) -> list[str]:
    return [i.value for i in at.info if "发现新版本" in i.value]


def _patch_cache(monkeypatch, payload: dict | None) -> None:
    """在 sidebar 实际导入的名字上 mock（app.sidebar.get_cached_update）。"""
    monkeypatch.setattr("app.sidebar.get_cached_update", lambda: payload, raising=False)


# ==================== 横幅显示 ====================


def test_banner_shows_new_version_with_download_link(monkeypatch):
    _patch_cache(monkeypatch, UPDATE_999)
    at = _launch()
    texts = _banner_texts(at)
    assert len(texts) == 1
    assert "9.9.9" in texts[0]
    assert config.APP_VERSION in texts[0]
    links = at.get("link_button")
    assert len(links) == 1
    assert links[0].proto.label == "下载更新"
    assert links[0].proto.url == RELEASE_URL
    at.button(key="dismiss_update")  # 关闭按钮存在


def test_banner_uses_latest_version_when_name_is_null(monkeypatch):
    """GitHub Release 的 name 可为 null；横幅必须用 latest_version 而非 name。"""
    _patch_cache(monkeypatch, {**UPDATE_999, "name": None})
    at = _launch()
    texts = _banner_texts(at)
    assert len(texts) == 1
    assert "v9.9.9" in texts[0]


# ==================== 按版本关闭 ====================


def test_dismiss_hides_banner_and_persists_across_reruns(monkeypatch):
    _patch_cache(monkeypatch, UPDATE_999)
    at = _launch()
    assert _banner_texts(at)
    at.button(key="dismiss_update").click()
    at.run()
    assert not at.exception
    assert at.session_state["update_dismissed"] == "9.9.9"
    assert not _banner_texts(at)
    at.run()  # 再一轮 rerun 仍隐藏
    assert not _banner_texts(at)
    assert at.session_state["update_dismissed"] == "9.9.9"


def test_newer_version_retriggers_after_dismiss(monkeypatch):
    _patch_cache(monkeypatch, UPDATE_999)
    at = _launch()
    at.button(key="dismiss_update").click()
    at.run()
    assert not _banner_texts(at)
    _patch_cache(monkeypatch, UPDATE_1000)
    at.run()
    texts = _banner_texts(at)
    assert len(texts) == 1
    assert "10.0.0" in texts[0]
    # 旧版本的 dismiss 记录不影响新版本
    assert at.session_state["update_dismissed"] == "9.9.9"


# ==================== 无横幅 ====================


def test_no_banner_when_cache_is_none(monkeypatch):
    _patch_cache(monkeypatch, None)
    at = _launch()
    assert not _banner_texts(at)
    assert len(at.get("link_button")) == 0
    with pytest.raises(KeyError):
        at.button(key="dismiss_update")


def test_disabled_check_yields_no_banner(monkeypatch):
    """UPDATE_CHECK_ENABLED=False → 检查器不运行、缓存恒空 → 无横幅（真实读路径）。"""
    monkeypatch.setattr(config, "UPDATE_CHECK_ENABLED", False)
    # 不 mock get_cached_update：走真实缓存读取（autouse 已重置 _cache=None）
    at = _launch()
    assert not _banner_texts(at)
    assert len(at.get("link_button")) == 0


# ==================== 启动钩子 ====================


def _bootstrap_script(tmp_path: Path) -> str:
    """最小脚本：只跑 initialize_system（两次，验证重复初始化下钩子接线安全）。"""
    script = tmp_path / "bootstrap_hook_under_test.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "from app.bootstrap import initialize_system\n"
        "initialize_system()\n"
        "initialize_system()\n",
        encoding="utf-8",
    )
    return str(script)


def test_initialize_system_invokes_start_hook(tmp_path, monkeypatch):
    """app 初始化处必须调用 start_update_checker（幂等由检查器自身保证，见 T2 测试）。"""
    monkeypatch.setattr("app.bootstrap.ApplicationContext", FakeContext)
    spy = mock.MagicMock()
    monkeypatch.setattr("app.bootstrap.start_update_checker", spy, raising=False)
    at = AppTest.from_file(_bootstrap_script(tmp_path), default_timeout=60)
    at.run()
    assert not at.exception
    assert spy.call_count == 2  # 每次初始化都调用；真实函数幂等，不会重复起线程


def test_initialize_system_opt_out_starts_no_thread(tmp_path, monkeypatch):
    """禁用时走真实 start_update_checker：不起线程、不置启动标记。"""
    monkeypatch.setattr(config, "UPDATE_CHECK_ENABLED", False)
    monkeypatch.setattr("app.bootstrap.ApplicationContext", FakeContext)
    monkeypatch.setattr(
        "app.bootstrap.start_update_checker", update_checker.start_update_checker,
        raising=False,
    )
    at = AppTest.from_file(_bootstrap_script(tmp_path), default_timeout=60)
    at.run()
    assert not at.exception
    assert update_checker._started is False
    assert not any(t.name == "update-checker" for t in threading.enumerate())
