"""全局自定义 CSS 样式（自 app.py「自定义 CSS 样式」段迁入）。"""
import streamlit as st


def inject_global_styles() -> None:
    st.markdown("""
<style>
    /* 主标题样式 */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1E88E5, #43A047);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* 副标题样式 */
    .subtitle {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    
    /* 卡片样式 */
    .stCard {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 按钮样式优化 */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 24px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* 代码块样式 */
    .stCode {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
    }
    
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    
    /* 成功/错误提示优化 */
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)
