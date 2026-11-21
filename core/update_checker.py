"""GitHub Releases 更新检查器（自动更新 spec §3.2）。

低频后台检查有无新版本，结果写入模块级线程安全缓存供侧栏横幅读取：
- 不用 st.session_state 跨线程（Streamlit session_state 线程不安全）；
- 网络/解析任何失败都降级为 None（log debug，绝不抛、绝不阻塞 UI）；
- start_update_checker() 幂等，daemon 线程不阻塞进程退出，
  UPDATE_CHECK_ENABLED=False 时不起线程。
"""
import json
import threading
import time
import urllib.request

from loguru import logger

import config

# 模块级线程安全缓存：后台线程写、UI 线程读（get_cached_update 非阻塞纯读）。
_cache: dict | None = None
_lock = threading.Lock()
_started = False

# 间隔配置 <=0 时的兜底默认（小时），避免 busy-loop。
_DEFAULT_INTERVAL_HOURS = 6


def parse_version(s: str) -> tuple[int, ...] | None:
    """解析 "vX.Y.Z"/"X.Y.Z" 为整数元组；非法（空串/非数字/段数错误）→ None。"""
    if not isinstance(s, str):
        return None
    text = s.strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    parts = text.split(".")
    if len(parts) != 3:
        return None
    numbers = []
    for part in parts:
        if not part.isascii() or not part.isdigit():
            return None
        numbers.append(int(part))
    return tuple(numbers)


def is_newer(latest: str, current: str) -> bool:
    """latest 是否严格新于 current；任一解析失败 → False（不误报）。"""
    latest_tuple = parse_version(latest)
    current_tuple = parse_version(current)
    if latest_tuple is None or current_tuple is None:
        return False
    return latest_tuple > current_tuple


def fetch_latest_release(repo: str, timeout: float = 5) -> dict | None:
    """GET GitHub 最新 Release；任何错误（超时/403 限流/坏 JSON/缺字段）→ None。"""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            # GitHub API 强制要求 User-Agent，缺失会 403
            "User-Agent": f"text2sql-agent/{config.APP_VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            logger.debug(f"GitHub Releases 响应非 JSON 对象: {url}")
            return None
        required = ("tag_name", "html_url", "name", "published_at")
        if any(key not in payload for key in required):
            logger.debug(f"GitHub Releases 响应缺少字段 {required}: {url}")
            return None
        tag_name = payload["tag_name"]
        html_url = payload["html_url"]
        if not isinstance(tag_name, str) or not tag_name.strip():
            logger.debug(f"GitHub Releases tag_name 非法: {tag_name!r}")
            return None
        if not isinstance(html_url, str) or not html_url.strip():
            logger.debug(f"GitHub Releases html_url 非法: {html_url!r}")
            return None
        return {
            "tag_name": tag_name,
            "html_url": html_url,
            "name": payload["name"],
            "published_at": payload["published_at"],
        }
    except Exception as exc:
        logger.debug(f"获取 GitHub 最新 Release 失败（降级为 None）: {exc}")
        return None


def check_for_update(current: str, repo: str) -> dict | None:
    """有新版 → {latest_version, url, name}；无新版/检查失败 → None。"""
    release = fetch_latest_release(repo)
    if release is None:
        return None
    latest_version = release["tag_name"].strip()
    if latest_version[:1] in ("v", "V"):
        latest_version = latest_version[1:]
    if not is_newer(latest_version, current):
        return None
    return {
        "latest_version": latest_version,
        "url": release["html_url"],
        "name": release["name"],
    }


def _checker_loop() -> None:
    """后台循环：启动立即检查一次，之后每 interval 小时检查一次写缓存。"""
    global _cache
    while True:
        hours = config.UPDATE_CHECK_INTERVAL_HOURS
        if hours <= 0:
            hours = _DEFAULT_INTERVAL_HOURS
        try:
            update = check_for_update(config.APP_VERSION, config.UPDATE_GITHUB_REPO)
        except Exception as exc:
            # 防御兜底：check_for_update 理论上不抛，仍保证循环不因异常退出
            logger.debug(f"更新检查异常（降级为 None）: {exc}")
            update = None
        with _lock:
            _cache = update
        time.sleep(hours * 3600)


def start_update_checker() -> None:
    """幂等启动后台检查线程；UPDATE_CHECK_ENABLED=False 时不起线程。"""
    global _started
    if not config.UPDATE_CHECK_ENABLED:
        logger.debug("更新检查已禁用（UPDATE_CHECK_ENABLED=False），不启动后台线程")
        return
    with _lock:
        if _started:
            return
        _started = True
    thread = threading.Thread(target=_checker_loop, name="update-checker", daemon=True)
    thread.start()
    logger.debug("更新检查后台线程已启动")


def get_cached_update() -> dict | None:
    """非阻塞读缓存（不做网络请求），供 UI 每轮 rerun 读取。"""
    with _lock:
        return _cache
