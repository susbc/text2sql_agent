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

from app.ui_icons import icon, icon_header, inject_icon_styles
from config import (
    EMBEDDING_PROVIDERS,
    FEW_SHOT_ENABLED,
    FEW_SHOT_TOP_K,
    HISTORY_AUTO_SAVE,
    LLM_PROVIDERS,
    LOG_FILE,
    LOG_LEVEL,
    NEO4J_ENABLED,
    SQL_DIALECT,
    SQL_QUERY_MAX_ROWS,
)
from core.sql.validator import validate_sql
from core.utils.correctness_ui import (
    execution_is_disabled,
    public_failure_messages,
    structured_validation_messages,
)
from core.utils.governance_settings import active_semantic_version
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
    # 输入区域 - 使用卡片样式
    st.markdown(icon_header("自然语言转 SQL", "square-pen", level=3), unsafe_allow_html=True)

    # 数据库选择
    db_options = []
    db_labels = []
    db_list = []
    ctx = st.session_state.app_context
    if st.session_state.initialized and ctx and ctx.neo4j_client and ctx.neo4j_client.driver:
        try:
            db_list = ctx.neo4j_client.get_database_list()
            db_options = [db["database_id"] for db in db_list]
            db_labels = [f"{db['name']} ({db['db_type']})" for db in db_list]
        except Exception as e:
            logger.warning(f"获取数据库列表失败：{e}")

    col_db, col1, col2 = st.columns([1, 2, 1])

    with col_db:
        if db_options:
            # 默认选择第一个数据库
            default_idx = 0
            selected_db_label = st.selectbox(
                "选择数据库",
                options=db_labels,
                index=default_idx if len(db_labels) > 0 else 0,
                key="selected_database",
                help="选择要查询的数据库，系统将生成对应语法的 SQL"
            )
            # 获取选中的数据库 ID
            selected_idx = db_labels.index(selected_db_label)
            selected_db_id = db_options[selected_idx]
            selected_db_info = next((db for db in db_list if db["database_id"] == selected_db_id), None)
            selected_db_type = selected_db_info["db_type"] if selected_db_info else "mysql"
        else:
            st.selectbox("选择数据库", options=["暂无数据库"], disabled=True)
            selected_db_id = None
            selected_db_type = "mysql"

    with col1:
        user_query = st.text_area(
            "请输入您的查询需求",
            placeholder="例如：查询所有订单金额大于 100 的用户",
            height=120,
            key="user_query",
            help="输入自然语言描述，系统将自动生成对应的 SQL 语句"
        )

    with col2:
        st.markdown("""
        <div class="stCard">
        <h4>示例查询</h4>
        <ul style="padding-left: 20px; line-height: 2;">
        <li>查询所有用户</li>
        <li>查询订单数量</li>
        <li>查询金额最大的订单</li>
        <li>统计每个用户订单数</li>
        <li>查询创建时间最近的订单</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    # 生成按钮
    st.markdown("")  # 间距
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        generate_btn = st.button("生成 SQL", type="primary", use_container_width=True)
    with col2:
        execute_btn = st.button(
            "▶执行 SQL",
            use_container_width=True,
            disabled=execution_is_disabled(st.session_state.last_result),
        )
    with col3:
        copy_btn = st.button("复制 SQL", use_container_width=True)

    # 生成 SQL
    if generate_btn and user_query:
        if not st.session_state.initialized or not ctx or not ctx.sql_generator:
            st.error("请先初始化系统")
        else:
            # 优先使用用户选择的数据库
            if selected_db_id is not None:
                detected_dialect = selected_db_type
                detected_db_id = selected_db_id
                db_name = selected_db_label.split(' ')[0]
            else:
                # 自动检测
                detected_dialect, detected_db_id = ctx.sql_generator.detect_dialect(user_query)
                db_info = ctx.sql_generator.dialect_detector.get_database_info(detected_db_id) if detected_db_id else None
                db_name = db_info.get('name', '未知') if db_info else '默认数据库'

            st.info(f"检测到目标数据库：**{db_name}** ({detected_dialect.upper()})")

            with st.spinner("正在生成 SQL..."):
                result = ctx.sql_generator.generate_sql(
                    user_query=user_query,
                    session_id=st.session_state.session_id,
                    target_dialect=detected_dialect,
                    target_database_id=detected_db_id,
                    auto_save_history=HISTORY_AUTO_SAVE,
                )

            # 检查是否检索到知识
            if result.get('matched_knowledge') is not None and len(result.get('matched_knowledge', [])) == 0:
                st.warning("""
                **未检索到相关知识库内容**

                可能的原因：
                1. 知识库为空或未初始化 - 请先在"知识图谱构建"页面导入 DDL 文件
                2. 知识库索引未刷新 - 请点击侧边栏的 **"重新初始化系统"** 按钮
                3. 查询问题与知识库内容不匹配 - 尝试调整查询措辞
                """)

            if result.get('status') in {'success', 'rejected'} and result.get('sql'):
                st.session_state.last_sql = result['sql']
                st.session_state.last_result = result

                # 显示思考过程（CoT）
                if result.get('thinking'):
                    with st.expander("思考过程（CoT）", expanded=False):
                        st.markdown(result['thinking'])

                # 显示生成的 SQL
                st.code(result['sql'], language='sql', line_numbers=True)

                # 显示匹配的知识
                if result.get('matched_knowledge'):
                    with st.expander("匹配的知识"):
                        for knowledge in result['matched_knowledge']:
                            st.markdown(f"- **{knowledge['name']}** (类型：{knowledge['node_type']}, 相似度：{knowledge['score']:.4f})")

                # 显示校验结果
                validation = result.get('validation') or validate_sql(
                    result['sql'], dialect=detected_dialect
                )
                if validation['valid']:
                    st.success("SQL 校验通过")
                else:
                    structured = structured_validation_messages(result)
                    if structured:
                        for message in structured:
                            st.warning(f"SQL 校验问题：{message}")
                    else:
                        st.warning(
                            f"SQL 校验问题：{', '.join(validation.get('errors', []))}"
                        )

                # 添加到历史
                st.session_state.history.append({
                    'query': user_query,
                    'user_query': result.get('user_query', user_query),
                    'sql': result['sql'],
                    'status': result.get('status'),
                    'semantic_version': result.get('semantic_version'),
                    'content_sha256': result.get('content_sha256'),
                    'validation': result.get('validation'),
                    'executable': result.get('executable'),
                    'allowed_tables': result.get('allowed_tables'),
                    'allowed_schemas': result.get('allowed_schemas'),
                    'timestamp': '刚刚'
                })

                st.rerun()
            else:
                structured = structured_validation_messages(result)
                error_msg = public_failure_messages(result)[0]
                # 检查是否是连接错误
                if not structured and (
                    'Connection' in error_msg or 'connection' in error_msg.lower()
                ):
                    st.error("""
                    **LLM 服务连接失败**

                    可能的原因：
                    1. 网络连接问题 - 请检查网络连接
                    2. API Key 无效或过期 - 请检查 `.env` 文件中的 `LLM_API_KEY` 配置
                    3. 服务不可用 - 阿里云 DashScope 服务可能暂时不可用

                    建议操作：
                    - 检查 `.env` 文件中的 API Key 配置是否正确
                    - 稍后重试
                    """)
                elif not structured:
                    st.error(f"生成失败：{error_msg}")
                else:
                    for message in structured:
                        st.error(f"生成失败：{message}")

    # 显示当前 SQL
    if st.session_state.last_sql:
        st.markdown(icon_header("生成的 SQL", "file-code", level=3), unsafe_allow_html=True)
        sql_container = st.container()
        with sql_container:
            st.code(st.session_state.last_sql, language='sql', line_numbers=False)

            persisted_validation = structured_validation_messages(
                st.session_state.last_result
            )
            for message in persisted_validation:
                st.warning(f"SQL 校验问题：{message}")

            if copy_btn:
                st.info("点击代码块右上角的复制按钮即可复制 SQL")

    # 执行 SQL
    if execute_btn and st.session_state.last_sql and ctx and ctx.sql_generator:
        with st.spinner("⏳ 正在执行 SQL..."):
            exec_result = ctx.sql_generator.execute_sql(
                sql=st.session_state.last_sql,
                history_id=(st.session_state.last_result or {}).get('history_id'),
                allowed_tables=(st.session_state.last_result or {}).get('allowed_tables'),
                allowed_schemas=(st.session_state.last_result or {}).get('allowed_schemas'),
                user_query=(st.session_state.last_result or {}).get('user_query'),
                semantic_version=(st.session_state.last_result or {}).get(
                    'semantic_version'
                ),
                content_sha256=(st.session_state.last_result or {}).get(
                    'content_sha256'
                ),
                session_id=st.session_state.session_id,
            )

        if exec_result.get('status') == 'success':
            st.success(f"执行成功，返回 {exec_result.get('row_count', 0)} 条记录")
            if exec_result.get('truncated'):
                st.warning(f"结果超过安全上限，仅显示前 {SQL_QUERY_MAX_ROWS} 条")

            # 显示结果
            data = exec_result.get('data', [])
            if data:
                st.dataframe(data, use_container_width=True, height=300)
        else:
            for message in public_failure_messages(exec_result):
                st.error(f"执行失败：{message}")

    # 无输入提示
    if generate_btn and not user_query:
        st.warning("请输入查询内容")


# ==================== Tab 2: 执行历史 ====================
with tab2:
    st.markdown(icon_header("执行历史", "history", level=3), unsafe_allow_html=True)
    
    if st.session_state.history:
        # 统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总记录数", len(st.session_state.history))
        with col2:
            success_count = len([h for h in st.session_state.history if h.get('status') == 'success'])
            st.metric("成功", success_count)
        with col3:
            st.metric("待执行", len(st.session_state.history) - success_count)
        
        st.divider()
        
        # 历史列表
        for i, item in enumerate(reversed(st.session_state.history)):
            with st.expander(f"**{i+1}.** {item['query'][:60]}{'...' if len(item['query']) > 60 else ''}", expanded=(i==0)):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**查询:** `{item['query']}`")
                with col2:
                    status_icon = "成功" if item.get('status') == 'success' else "执行中"
                    st.markdown(f"**状态:** {status_icon}")
                
                st.code(item['sql'], language='sql', line_numbers=False)
                
                # 操作按钮
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("使用此 SQL", key=f"use_{i}", use_container_width=True):
                        st.session_state.last_sql = item['sql']
                        st.session_state.last_result = item
                        st.rerun()
                with col2:
                    if st.button("复制", key=f"copy_{i}", use_container_width=True):
                        st.success("已复制到剪贴板")
                with col3:
                    if st.button("删除", key=f"delete_{i}", use_container_width=True):
                        st.session_state.history.pop(len(st.session_state.history) - 1 - i)
                        st.rerun()
                with col4:
                    if st.button("提取&增强", key=f"extract_{i}", use_container_width=True):
                        # 提取 JOIN 关系
                        from core.sql.join_extractor import extract_joins_from_sql
                        joins = extract_joins_from_sql(item['sql'])
                        # 转为字典列表存储（避免 Streamlit session_state 序列化 dataclass 的问题）
                        if joins:
                            st.session_state[f"extracted_joins_{i}"] = [
                                {
                                    "left_table": jn.left_table,
                                    "right_table": jn.right_table,
                                    "join_type": jn.join_type,
                                    "join_condition": jn.join_condition,
                                    "from_column": jn.from_column,
                                    "to_column": jn.to_column,
                                    "extra_condition": jn.extra_condition
                                }
                                for jn in joins
                            ]
                        else:
                            st.session_state[f"extracted_joins_{i}"] = []

                # 显示提取的 JOIN 关系
                extracted = st.session_state.get(f"extracted_joins_{i}", [])
                if extracted:
                    st.markdown(f"**提取到 {len(extracted)} 个 JOIN 关系：**")
                    for j, join in enumerate(extracted):
                        st.markdown(
                            f"  **{j+1}.** `{join['left_table']}` → `{join['right_table']}` "
                            f"({join['join_type']}) — ON `{join['join_condition']}`"
                        )

                    if st.button("确认增强到知识图谱", key=f"confirm_{i}", type="primary", use_container_width=True):
                        # 更新 Neo4j 权重
                        if ctx and ctx.neo4j_client and ctx.neo4j_client.driver:
                            from core.graph_builder.loader.weight_initializer import (
                                rebalance_with_history,
                            )
                            stats = rebalance_with_history(extracted, ctx.neo4j_client)
                            st.success(f"增强完成：更新 {stats['updated']} 条，新建 {stats['created']} 条关系")
                        else:
                            st.warning("Neo4j 未连接，无法增强")
    else:
        st.info("暂无历史记录，快去生成第一条 SQL 吧！")


# ==================== Tab 3: 知识图谱构建 ====================
with tab3:
    from app.pages.kg_builder import show_kg_builder
    show_kg_builder()

with tab4:
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
        # 脱敏展示：隐藏主机地址和端口详情，仅显示连接状态
        mysql_status = "已连接" if (ctx and ctx.mysql_client and ctx.mysql_client.engine) else "未连接"
        neo4j_status = "已连接" if NEO4J_ENABLED and (ctx and ctx.neo4j_client and ctx.neo4j_client.driver) else "未连接/未启用"
        st.markdown("""
        **数据库配置**
        - MySQL: {mysql_status}
        - Neo4j: {neo4j_status}
        - SQL 方言：{dialect}
        """.format(
            mysql_status=mysql_status,
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


# ==================== Footer ====================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; padding: 20px 0;'>"
    "溯算编程 · Text2SQL 智能体 v1.0 | 基于本地知识库的 SQL 智能生成系统 | © 2026 溯算编程"
    "</div>",
    unsafe_allow_html=True
)
