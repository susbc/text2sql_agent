"""
Text2SQL 智能体 - Streamlit 主入口
基于本地知识库的 SQL 智能生成应用
"""
# ruff: noqa: E402
import sys
from pathlib import Path

import streamlit as st

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# 品牌资源
LOGO_ICON_PATH = project_root / "assets" / "logo_icon.png"

from loguru import logger

from app.ui_icons import inject_icon_styles
from config import LOG_FILE, LOG_LEVEL
from core.utils.log_sanitizer import make_safe_streamlit_sink, safe_log_format


# 配置日志（级别与路径由 LOG_LEVEL / LOG_FILE 控制；此前两者被定义却从未被读取，
# 导致 .env 里的日志级别配置完全不起作用，且文件 sink 恒为 DEBUG）
logger.remove()
logger.add(
    make_safe_streamlit_sink(st.write),
    level=LOG_LEVEL,
    format=safe_log_format,
)
logger.add(
    LOG_FILE,
    level=LOG_LEVEL,
    rotation="1 day",
    format=safe_log_format,
)

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="溯算编程 · Text2SQL 智能体",
    page_icon=str(LOGO_ICON_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/renguanjie/text2sql-agent',
        'Report a bug': 'https://github.com/renguanjie/text2sql-agent/issues',
        'About': '# 溯算编程 · Text2SQL 智能体\n基于本地知识库的 SQL 智能生成系统\n\n核心技术：BM25+FAISS 检索 + LangChain + SQLFluff'
    }
)

# 图标组件基础样式（幂等，对齐 Bootstrap Reboot 的克制基线风格）
inject_icon_styles()

# ==================== 自定义 CSS 样式 ====================
from app.styles import inject_global_styles

inject_global_styles()

# ==================== 会话状态初始化 ====================
from app.state import init_session_state

init_session_state()


# ==================== 侧边栏 ====================
from app.sidebar import render_sidebar

render_sidebar()


# ==================== 主界面 ====================
# 主标题
st.markdown('<p class="main-title">溯算编程 · Text2SQL 智能体</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">基于本地知识库的 SQL 智能生成系统</p>', unsafe_allow_html=True)

# 选项卡
tab1, tab2, tab3, tab4 = st.tabs(["SQL 生成", "执行历史", "知识图谱构建", "系统信息"])

# ==================== Tab 1: SQL 生成 ====================
with tab1:
    from app.pages.sql_generation import show_sql_generation
    show_sql_generation()


# ==================== Tab 2: 执行历史 ====================
with tab2:
    from app.pages.history import show_history
    show_history()


# ==================== Tab 3: 知识图谱构建 ====================
with tab3:
    from app.pages.kg_builder import show_kg_builder
    show_kg_builder()

with tab4:
    from app.pages.system_info import show_system_info
    show_system_info()


# ==================== Footer ====================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; padding: 20px 0;'>"
    "溯算编程 · Text2SQL 智能体 v1.0 | 基于本地知识库的 SQL 智能生成系统 | © 2026 溯算编程"
    "</div>",
    unsafe_allow_html=True
)
