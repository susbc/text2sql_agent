"""系统信息页面（自 app.py「Tab 4: 系统信息」段迁入）。"""
from pathlib import Path

import streamlit as st

from app.ui_icons import icon_header
from config import (
    EMBEDDING_PROVIDERS,
    FEW_SHOT_ENABLED,
    FEW_SHOT_TOP_K,
    LLM_PROVIDERS,
    LOG_FILE,
    NEO4J_ENABLED,
    SQL_DIALECT,
    SQLITE_PATH,
)
from core.utils.governance_settings import active_semantic_version


def show_system_info() -> None:
    ctx = st.session_state.app_context  # 自持：原跨 Tab 依赖 tab1 块内绑定
    st.markdown(icon_header("系统信息", "info", level=3), unsafe_allow_html=True)

    # 读取当前生效的配置（ctx.config 快照，未初始化时回落到 .env）
    from app.model_config import _active_model_config
    _active = _active_model_config()
    _current_llm_provider = _active['llm_provider']
    _current_llm_model = _active['llm_model']
    _current_llm_base_url = _active['llm_base_url']
    _current_emb_provider = _active['embedding_provider']
    _current_emb_model = _active['embedding_model']

    # 系统状态卡片
    st.markdown(icon_header("配置信息", "sliders-horizontal", level=4), unsafe_allow_html=True)
    config_col1, config_col2 = st.columns(2)
    with config_col1:
        # LLM 配置展示（显示当前生效值 + 标签）
        llm_label = LLM_PROVIDERS.get(_current_llm_provider, {}).get("label", _current_llm_provider)
        st.markdown(f"""
        **LLM 配置**
        - 提供商：{llm_label}
        - 模型：{_current_llm_model}
        - Base URL: {_current_llm_base_url or "默认"}
        """)

        emb_label = EMBEDDING_PROVIDERS.get(_current_emb_provider, {}).get("label", _current_emb_provider)
        st.markdown(f"""
        **Embedding 配置**
        - 提供商：{emb_label}
        - 模型：{_current_emb_model}
        """)

    with config_col2:
        # SQLite 为本地文件库：展示文件路径与连接状态，无主机/端口信息
        db_client = ctx.db_client if ctx else None
        db_status = "已连接" if (db_client and db_client.engine) else "未连接"
        sqlite_path = getattr(db_client, "path", None) or SQLITE_PATH
        table_count = history_count = "未知"
        if db_client and db_client.engine:
            try:
                db_stats = db_client.get_statistics()
                table_count = db_stats.get("total_tables", 0)
                history_count = db_stats.get("total_history", 0)
            except Exception:
                table_count = history_count = "未知"
        neo4j_status = "已连接" if NEO4J_ENABLED and (ctx and ctx.neo4j_client and ctx.neo4j_client.driver) else "未连接/未启用"
        st.markdown("""
        **数据库配置**
        - SQLite: {db_status}
        - 文件路径：{sqlite_path}
        - 表数：{table_count} ｜ 历史数：{history_count}
        - Neo4j: {neo4j_status}
        - SQL 方言：{dialect}
        """.format(
            db_status=db_status,
            sqlite_path=sqlite_path,
            table_count=table_count,
            history_count=history_count,
            neo4j_status=neo4j_status,
            dialect=SQL_DIALECT
        ))

        st.markdown("""
        **检索配置**
        - BM25+FAISS 混合检索
        - Few-Shot: {few_shot} (top {top_k})
        """.format(
            few_shot="已启用" if FEW_SHOT_ENABLED else "禁用",
            top_k=FEW_SHOT_TOP_K
        ))

        from app.pages.governance_settings import current_governance_config
        _gov_cfg = current_governance_config(ctx)
        st.markdown("""
        **语义治理**
        - 治理：{gov} ｜ EXPLAIN 预检：{explain}
        - 激活语义版本：{version}
        """.format(
            gov="已启用" if _gov_cfg['semantic_governance_enabled'] else "已关闭",
            explain="已启用" if _gov_cfg['sql_explain_enabled'] else "已关闭",
            version=active_semantic_version(
                getattr(ctx, "semantic_registry", None)
            ) or "未加载",
        ))

    st.divider()

    # 模型配置 UI 面板
    from app.model_config import render_model_config_panel
    render_model_config_panel()

    st.divider()

    # 语义治理与执行预检配置面板
    from app.pages.governance_settings import show_governance_settings
    show_governance_settings()

    st.divider()

    # 统计信息
    st.markdown(icon_header("统计信息", "bar-chart-3", level=4), unsafe_allow_html=True)
    if ctx and ctx.sql_generator:
        stats = ctx.sql_generator.get_statistics()
        
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("总请求数", stats.get('total_requests', 0))
        with stat_col2:
            st.metric("成功生成", stats.get('successful_generations', 0))
        with stat_col3:
            st.metric("失败", stats.get('failed_generations', 0))
    
    st.divider()
    
    # 日志
    st.markdown(icon_header("最近日志", "file-text", level=4), unsafe_allow_html=True)
    try:
        log_file = Path(LOG_FILE)
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.readlines()[-20:]
                st.text("".join(logs))
        else:
            st.info("日志文件不存在")
    except Exception as e:
        st.write(f"无法读取日志：{e}")
