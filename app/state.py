"""会话状态初始化（自 app.py「会话状态初始化」段迁入）。"""
import uuid

import streamlit as st


def init_session_state() -> None:
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False

    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if 'app_context' not in st.session_state:
        st.session_state.app_context = None

    if 'history' not in st.session_state:
        st.session_state.history = []

    if 'last_sql' not in st.session_state:
        st.session_state.last_sql = None

    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
