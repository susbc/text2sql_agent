"""SQL 生成页面（自 app.py「Tab 1: SQL 生成」段迁入）。"""
import streamlit as st
from loguru import logger

from app.ui_icons import icon_header
from config import HISTORY_AUTO_SAVE, SQL_QUERY_MAX_ROWS
from core.sql.validator import validate_sql
from core.utils.correctness_ui import (
    execution_is_disabled,
    public_failure_messages,
    structured_validation_messages,
)


def show_sql_generation() -> None:
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
            selected_db_type = selected_db_info["db_type"] if selected_db_info else "sqlite"
        else:
            st.selectbox("选择数据库", options=["暂无数据库"], disabled=True)
            selected_db_id = None
            selected_db_type = "sqlite"

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

    st.caption("执行目标：SQLite 业务库")

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
