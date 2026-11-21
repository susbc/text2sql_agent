"""更新检查器单测（自动更新 spec §3.2）。

密封约束：全程 mock urllib.request.urlopen / fetch_latest_release / threading.Thread /
time.sleep，不发真实网络请求、不留驻后台线程；模块级 _cache/_started 由 autouse
fixture 在每例前后重置，避免跨例污染。
"""
import json
import urllib.error
import urllib.request
from unittest import mock

import pytest

import config
from core import update_checker

_RELEASE_PAYLOAD = {
    "tag_name": "v1.2.0",
    "html_url": "https://github.com/susbc/text2sql_agent/releases/tag/v1.2.0",
    "name": "v1.2.0",
    "published_at": "2026-11-21T00:00:00Z",
}


@pytest.fixture(autouse=True)
def reset_checker_state():
    """每例前后重置模块级缓存与启动标记。"""

    def _reset():
        with update_checker._lock:
            update_checker._cache = None
            update_checker._started = False

    _reset()
    yield
    _reset()


# ==================== parse_version ====================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("V1.2.3", (1, 2, 3)),
        (" 1.2.3 ", (1, 2, 3)),
        (" v1.2.3 ", (1, 2, 3)),
        ("0.0.0", (0, 0, 0)),
        ("10.20.30", (10, 20, 30)),
    ],
)
def test_parse_version_valid(raw, expected):
    assert update_checker.parse_version(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", "v", "1.2", "1.2.3.4", "1..3", "1.2.x", "-1.2.3", "1.2.3-beta", None],
)
def test_parse_version_invalid(raw):
    """空串/非数字/段数错误一律 None（空 VERSION → APP_VERSION="" 不得误报）。"""
    assert update_checker.parse_version(raw) is None


# ==================== is_newer ====================


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("1.1.0", "1.0.0", True),
        ("2.0.0", "1.9.9", True),
        ("1.0.1", "1.0.0", True),
        ("v1.1.0", "1.0.0", True),
        ("1.10.0", "1.9.0", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "1.1.0", False),
        ("abc", "1.0.0", False),
        ("1.0.0", "", False),
        ("", "", False),
        (None, "1.0.0", False),
    ],
)
def test_is_newer(latest, current, expected):
    assert update_checker.is_newer(latest, current) is expected


# ==================== fetch_latest_release ====================


def _patch_urlopen(monkeypatch, *, payload=None, raw=None, exc=None):
    """mock urllib.request.urlopen：返回 JSON 响应或抛指定异常。"""
    opener = mock.MagicMock()
    if exc is not None:
        opener.side_effect = exc
    else:
        body = raw if raw is not None else json.dumps(payload).encode("utf-8")
        opener.return_value.__enter__.return_value.read.return_value = body
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    return opener


def test_fetch_latest_release_success(monkeypatch):
    _patch_urlopen(monkeypatch, payload=_RELEASE_PAYLOAD)
    assert update_checker.fetch_latest_release("susbc/text2sql_agent") == _RELEASE_PAYLOAD


def test_fetch_latest_release_request_shape(monkeypatch):
    """URL 正确、带 User-Agent（GitHub 必需）与 Accept 头、默认 timeout=5。"""
    opener = _patch_urlopen(monkeypatch, payload=_RELEASE_PAYLOAD)
    update_checker.fetch_latest_release("susbc/text2sql_agent")
    request = opener.call_args.args[0]
    assert isinstance(request, urllib.request.Request)
    assert request.full_url == "https://api.github.com/repos/susbc/text2sql_agent/releases/latest"
    assert request.get_header("User-agent")
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert opener.call_args.kwargs["timeout"] == 5


def test_fetch_latest_release_custom_timeout(monkeypatch):
    opener = _patch_urlopen(monkeypatch, payload=_RELEASE_PAYLOAD)
    update_checker.fetch_latest_release("susbc/text2sql_agent", timeout=2)
    assert opener.call_args.kwargs["timeout"] == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exc": urllib.error.URLError(TimeoutError("timed out"))},
        {"exc": urllib.error.HTTPError("https://api.github.com", 403, "rate limit", {}, None)},
        {"exc": OSError("connection reset")},
        {"raw": b"{bad json"},
        {"raw": b"[1, 2, 3]"},
        {"payload": {"tag_name": "v1.2.0"}},
        {"payload": {**_RELEASE_PAYLOAD, "tag_name": ""}},
        {"payload": {**_RELEASE_PAYLOAD, "html_url": ""}},
    ],
    ids=["urlerror-timeout", "http-403", "oserror", "bad-json", "non-dict", "missing-keys",
         "empty-tag", "empty-url"],
)
def test_fetch_latest_release_degrades_to_none(monkeypatch, kwargs):
    """任何网络/解析错误都返回 None，绝不抛异常。"""
    _patch_urlopen(monkeypatch, **kwargs)
    assert update_checker.fetch_latest_release("susbc/text2sql_agent") is None


# ==================== check_for_update ====================


def _patch_fetch(monkeypatch, release):
    monkeypatch.setattr(update_checker, "fetch_latest_release", lambda repo: release)


@pytest.mark.parametrize("tag", ["v1.1.0", "1.1.0", " v1.1.0 "])
def test_check_for_update_newer(monkeypatch, tag):
    release = {
        "tag_name": tag,
        "html_url": "https://example.com/release",
        "name": "Release 1.1.0",
        "published_at": "2026-11-21T00:00:00Z",
    }
    _patch_fetch(monkeypatch, release)
    assert update_checker.check_for_update("1.0.0", "susbc/text2sql_agent") == {
        "latest_version": "1.1.0",
        "url": "https://example.com/release",
        "name": "Release 1.1.0",
    }


@pytest.mark.parametrize("tag", ["v1.0.0", "v0.9.9", "abc"])
def test_check_for_update_not_newer(monkeypatch, tag):
    _patch_fetch(monkeypatch, {**_RELEASE_PAYLOAD, "tag_name": tag})
    assert update_checker.check_for_update("1.0.0", "susbc/text2sql_agent") is None


def test_check_for_update_fetch_none(monkeypatch):
    _patch_fetch(monkeypatch, None)
    assert update_checker.check_for_update("1.0.0", "susbc/text2sql_agent") is None


def test_check_for_update_empty_current(monkeypatch):
    """当前版本为空（VERSION 空文件）时不得误报新版。"""
    _patch_fetch(monkeypatch, _RELEASE_PAYLOAD)
    assert update_checker.check_for_update("", "susbc/text2sql_agent") is None


# ==================== 后台线程与缓存 ====================


def test_start_update_checker_opt_out(monkeypatch):
    """UPDATE_CHECK_ENABLED=False 不起线程。"""
    monkeypatch.setattr(config, "UPDATE_CHECK_ENABLED", False)
    thread_cls = mock.MagicMock()
    monkeypatch.setattr(update_checker.threading, "Thread", thread_cls)
    update_checker.start_update_checker()
    thread_cls.assert_not_called()
    assert update_checker._started is False


def test_start_update_checker_idempotent_daemon(monkeypatch):
    """调用两次只起一个线程；daemon=True；target 为检查循环。"""
    monkeypatch.setattr(config, "UPDATE_CHECK_ENABLED", True)
    thread_cls = mock.MagicMock()
    monkeypatch.setattr(update_checker.threading, "Thread", thread_cls)
    update_checker.start_update_checker()
    update_checker.start_update_checker()
    assert thread_cls.call_count == 1
    kwargs = thread_cls.call_args.kwargs
    assert kwargs["daemon"] is True
    assert kwargs["target"] is update_checker._checker_loop
    thread_cls.return_value.start.assert_called_once()
    assert update_checker._started is True


def test_get_cached_update_passive(monkeypatch):
    """非阻塞纯读缓存：不触发网络/检查；初始 None，写入后可读。"""

    def boom(*args, **kwargs):
        raise AssertionError("get_cached_update 不得触发网络或检查")

    monkeypatch.setattr(update_checker, "fetch_latest_release", boom)
    monkeypatch.setattr(update_checker, "check_for_update", boom)
    assert update_checker.get_cached_update() is None
    sentinel = {"latest_version": "9.9.9", "url": "u", "name": "n"}
    with update_checker._lock:
        update_checker._cache = sentinel
    assert update_checker.get_cached_update() == sentinel


class _StopLoop(Exception):
    """同步测试中用于跳出无限循环。"""


def _run_loop_once(monkeypatch, *, check_result=None, check_exc=None, hours=6):
    """在当前线程同步跑一轮循环：mock check/sleep，sleep 时抛 _StopLoop 跳出。"""
    events = []

    def fake_check(current, repo):
        events.append(("check", current, repo))
        if check_exc is not None:
            raise check_exc
        return check_result

    def fake_sleep(seconds):
        events.append(("sleep", seconds))
        raise _StopLoop()

    monkeypatch.setattr(config, "APP_VERSION", "1.0.0")
    monkeypatch.setattr(config, "UPDATE_GITHUB_REPO", "susbc/text2sql_agent")
    monkeypatch.setattr(config, "UPDATE_CHECK_INTERVAL_HOURS", hours)
    monkeypatch.setattr(update_checker, "check_for_update", fake_check)
    monkeypatch.setattr(update_checker.time, "sleep", fake_sleep)
    with pytest.raises(_StopLoop):
        update_checker._checker_loop()
    return events


def test_loop_checks_immediately_then_sleeps(monkeypatch):
    """启动先检查一次再 sleep；结果写入线程安全缓存。"""
    sentinel = {"latest_version": "9.9.9", "url": "u", "name": "n"}
    events = _run_loop_once(monkeypatch, check_result=sentinel, hours=6)
    assert events[0] == ("check", "1.0.0", "susbc/text2sql_agent")
    assert events[1] == ("sleep", 6 * 3600)
    assert update_checker.get_cached_update() == sentinel


@pytest.mark.parametrize("hours", [0, -3])
def test_loop_interval_guard(monkeypatch, hours):
    """间隔 <=0 时回退默认 6 小时，避免 busy-loop。"""
    events = _run_loop_once(monkeypatch, check_result=None, hours=hours)
    assert events[1] == ("sleep", 6 * 3600)


def test_loop_custom_interval(monkeypatch):
    events = _run_loop_once(monkeypatch, check_result=None, hours=2)
    assert events[1] == ("sleep", 2 * 3600)


def test_loop_degrades_on_check_exception(monkeypatch):
    """检查抛异常时循环不崩：缓存置 None 并继续 sleep。"""
    events = _run_loop_once(monkeypatch, check_exc=RuntimeError("boom"))
    assert events[1][0] == "sleep"
    assert update_checker.get_cached_update() is None


def test_loop_no_update_clears_cache(monkeypatch):
    """无新版时缓存写 None（覆盖旧值）。"""
    with update_checker._lock:
        update_checker._cache = {"latest_version": "0.0.1", "url": "u", "name": "n"}
    _run_loop_once(monkeypatch, check_result=None)
    assert update_checker.get_cached_update() is None
