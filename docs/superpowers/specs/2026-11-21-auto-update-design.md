# 自动更新检查与提示 设计文档

日期：2026-11-21
状态：待确认
范围（用户已定）：定期检查 GitHub Releases → 发现新版弹提示（当前版 vs 新版 + 下载链接）→ 用户手动下载安装。**不做自动下载/替换/重启**。

## 1. 意图

打包应用定期检查 GitHub 有无新版本，有则在 UI 提示用户更新（附 Release 下载链接），可关闭/禁用。

## 2. 现状

- 版本单一事实源＝根 `VERSION` 文件（1.0.0）；spec 读它写 plist，但**运行时无版本常量**，VERSION 也未打进 bundle。
- 侧栏 `app/sidebar.py render_sidebar()` 是放更新横幅的合适位置。
- GitHub Releases API：`GET https://api.github.com/repos/susbc/text2sql_agent/releases/latest`（未认证 60 次/小时，低频检查足够）。

## 3. 设计

### 3.1 运行时版本（config.py + spec）
- `config.APP_VERSION`：读 `PROJECT_ROOT/VERSION`（dev）/bundle 内 VERSION（frozen），缺失回退 "0.0.0"。
- `text2sql.spec` datas 增加根 `VERSION`（冻结态可读）。

### 3.2 更新检查器（core/update_checker.py）
- `parse_version(s) -> tuple`：解析 "vX.Y.Z"/"X.Y.Z"→整数元组；非法→None。
- `is_newer(latest, current) -> bool`：元组比较。
- `fetch_latest_release(repo, timeout=5) -> dict|None`：urllib GET releases/latest，解析 tag_name/html_url/name/published_at；网络错误/超时/403 限流/解析失败→None（log debug，不抛）。
- `check_for_update(current, repo) -> UpdateInfo|None`：fetch + is_newer → {latest_version, url, name} 或 None。
- **后台周期线程**：模块级线程安全缓存（lock + 全局 _latest）；daemon 线程每 `UPDATE_CHECK_INTERVAL_HOURS` 检查一次写缓存；`start_update_checker()` 幂等（只起一次），`UPDATE_CHECK_ENABLED=False` 不起。get_cached_update() 非阻塞读缓存供 UI。
  - 不用 st.session_state 跨线程（Streamlit session_state 线程不安全）；用模块级缓存。

### 3.3 配置（config.py + env.example）
- `UPDATE_CHECK_ENABLED`（默认 true）
- `UPDATE_CHECK_INTERVAL_HOURS`（默认 6）
- `UPDATE_GITHUB_REPO`（默认 "susbc/text2sql_agent"）

### 3.4 UI（app/sidebar.py）
- render_sidebar 读 get_cached_update()；若有新版且 `st.session_state.get("update_dismissed") != latest`：
  - 横幅 `st.info("🎉 发现新版本 v{latest}（当前 v{current}）")` + `st.link_button("下载更新", url)` + 关闭按钮（key="dismiss_update"，点击置 session_state.update_dismissed=latest）。
- 启动后台线程：app 初始化处（bootstrap 或 app.py）调 start_update_checker()（幂等）。

### 3.5 测试
- test_update_checker：parse_version/is_newer（新/旧/等/非法/v 前缀）、fetch 解析（mock urllib）、网络失败/超时/限流→None、opt-out 不起线程。
- test_update_banner（AppTest）：mock 缓存有新版→横幅+下载链接；dismiss 隐藏；disabled→无横幅。

## 4. 目标 / 非目标
- 目标：低频检查、新版提示+下载链接、可关闭/禁用、网络失败不崩、冻结态读自身版本。
- 非目标：不自动下载/替换/重启；不改业务逻辑；不认证 GitHub（公开 API 足够）。
- 反目标：阻塞 UI 的同步网络调用；跨线程写 session_state；网络异常致崩溃；误报（版本比较错）。

## 5. 验证
- 单测全绿 + 新增；ruff 零。
- mock 新版→横幅显示+链接正确；dismiss 隐藏；禁用无横幅。
- 真实 API 冒烟（当前 1.0.0 == latest→无提示；mock 更高版→提示）。
- 冻结态 APP_VERSION 可读（spec bundle VERSION）。

## 6. 实现者决策
- 后台线程启动点（bootstrap vs app.py）；缓存结构；横幅措辞/位置细节。
- 提交切分（版本常量+spec / 检查器+config / UI+测试）。