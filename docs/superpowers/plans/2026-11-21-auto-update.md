# 自动更新检查与提示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 打包应用后台定期检查 GitHub Releases，发现新版在侧栏弹提示（当前版 vs 新版 + 下载链接），可关闭/禁用；不自动下载替换。

**Architecture:** config.APP_VERSION 读 VERSION（bundle）；core/update_checker.py 后台 daemon 线程周期查 GitHub API + 模块级线程安全缓存；侧栏读缓存渲染横幅。网络失败静默降级。

**Tech Stack:** Python 3.12、urllib（GitHub API）、threading、Streamlit、pytest/AppTest。

**Spec:** `docs/superpowers/specs/2026-11-21-auto-update-design.md`

## Global Constraints

- 基线 **1124 passed, 9 skipped**；每任务全量保持 + 新增；ruff 零。
- 不阻塞 UI（后台线程，UI 非阻塞读缓存）；不跨线程写 st.session_state（模块级缓存）。
- 网络失败/超时/限流静默降级（返回 None，不崩）；opt-out（UPDATE_CHECK_ENABLED=False 不起线程）。
- 不改业务逻辑；dev 行为兼容；精确 staging；提交中文 conventional + Co-Authored-By: Claude Code <noreply@anthropic.com>。
- 隔离 worktree（auto-update）；主仓 .venv/bin/python 绝对路径；8501 不动。

## Review Focus
1. 版本比较误报（semver 解析/比较）→ T2 单测。
2. 网络异常致崩溃/阻塞 UI → T2 降级测试 + 后台线程。
3. 跨线程 session_state 不安全 → 模块级缓存（T2）。
4. 冻结态读不到自身版本 → T1 spec bundle VERSION + 测试。
5. 横幅 dismiss/禁用逻辑 → T3 AppTest。

---

### Task 1: 运行时版本 + 配置 + spec bundle

**Files:**
- Modify: `config.py`（APP_VERSION + UPDATE_CHECK_ENABLED/INTERVAL_HOURS/GITHUB_REPO）、`text2sql.spec`（datas 加 VERSION）、`env.example`（UPDATE_* 注释）
- Create: `tests/test_app_version.py`

**Interfaces:**
- Produces: `config.APP_VERSION`（读 PROJECT_ROOT/VERSION，回退 "0.0.0"）；`config.UPDATE_CHECK_ENABLED`(bool 默认 True)、`UPDATE_CHECK_INTERVAL_HOURS`(int 默认 6)、`UPDATE_GITHUB_REPO`(str 默认 "susbc/text2sql_agent")。

- [ ] **Step 1: 写测试（先失败）**：APP_VERSION==VERSION 文件内容（"1.0.0"）；缺失文件回退 "0.0.0"（monkeypatch）；UPDATE_* 默认值。
- [ ] **Step 2: 实现**：config.APP_VERSION 读 VERSION（try/except→"0.0.0"）；UPDATE_CHECK_ENABLED=parse_env_bool(...,True)；UPDATE_CHECK_INTERVAL_HOURS=parse_env_int(...,6)；UPDATE_GITHUB_REPO=os.getenv(...,"susbc/text2sql_agent")。spec datas 追加 (str(PROJECT_ROOT/"VERSION"), ".")。env.example 加 UPDATE_* 注释段。
- [ ] **Step 3: 测试通过 + 全量 + ruff + Commit**：`feat(update): 运行时版本常量 APP_VERSION + 更新检查配置 + bundle VERSION`

---

### Task 2: 更新检查器 core/update_checker.py + 单测

**Files:**
- Create: `core/update_checker.py`、`tests/test_update_checker.py`

**Interfaces:**
- Produces: `parse_version(s)->tuple|None`；`is_newer(latest,current)->bool`；`fetch_latest_release(repo,timeout=5)->dict|None`；`check_for_update(current,repo)->dict|None`（{latest_version,url,name}）；`start_update_checker()->None`（幂等 daemon 线程，UPDATE_CHECK_ENABLED=False 不起）；`get_cached_update()->dict|None`（非阻塞）。
- Consumes: config.APP_VERSION/UPDATE_*。

- [ ] **Step 1: 写测试（先失败）**：parse_version（"1.2.3"/"v1.2.3"→(1,2,3)，非法→None）；is_newer（新/旧/等）；fetch_latest_release mock urllib（正常解析 tag_name/html_url/name；超时/URLError/403/坏 JSON→None）；check_for_update（新版→dict，旧/等→None）；start_update_checker opt-out 不起线程 + 幂等；get_cached_update 非阻塞。
- [ ] **Step 2: 实现**：urllib.request GET api.github.com/repos/{repo}/releases/latest（User-Agent header，timeout）；json 解析；semver 元组比较；模块级 _cache+_lock+threading.Thread(daemon) 周期 sleep(interval*3600) 检查写缓存；start 幂等（_started flag+lock）；get_cached_update 加锁读。网络异常 log debug 返回 None。
- [ ] **Step 3: 测试通过 + 全量 + ruff + Commit**：`feat(update): GitHub Releases 更新检查器（后台周期线程+线程安全缓存+降级）`

---

### Task 3: 侧栏更新横幅 + 启动钩子 + AppTest

**Files:**
- Modify: `app/sidebar.py`（横幅）、`app/bootstrap.py` 或 `app.py`（start_update_checker 钩子）
- Create: `tests/test_update_banner.py`

**Interfaces:**
- Consumes: core.update_checker.get_cached_update/start_update_checker；config.APP_VERSION。
- Produces: 侧栏新版横幅（info + link_button 下载 + dismiss 按钮 key="dismiss_update"）；session_state.update_dismissed。

- [ ] **Step 1: 写 AppTest（先失败）**：mock get_cached_update 返回新版→横幅含"发现新版本"+下载链接 url；点 dismiss→横幅隐藏（session_state.update_dismissed=latest）；缓存 None→无横幅；UPDATE_CHECK_ENABLED=False→无横幅。
- [ ] **Step 2: 实现**：render_sidebar 读 get_cached_update()，有新版且未 dismiss→st.info+st.link_button("下载更新",url)+st.button("关闭",key="dismiss_update")（点击置 dismissed）；app 初始化调 start_update_checker()（幂等）。widget key 稳定。
- [ ] **Step 3: 测试通过 + 全量 + ruff + Commit**：`feat(update): 侧栏新版提示横幅（下载链接+关闭）+ 启动检查钩子`

---

### Task 4: 终验 + 整支审查 + 合并（控制器）

- [ ] **Step 1: 终验**：全量绿（1124+新增）；ruff 零；真实 API 冒烟（当前 1.0.0==latest→无提示）；mock 更高版→横幅；冻结态 APP_VERSION 可读（spec bundle）。
- [ ] **Step 2: 整支对抗审查工作流**：维度（版本比较正确性/网络降级与线程安全/UI 逻辑/冻结态版本/dev 回归）+ 逐条对抗验证；confirmed 单一修复波 + scoped re-review。
- [ ] **Step 3: 合并回 main + 推送**：finishing-a-development-branch（用户决策）。