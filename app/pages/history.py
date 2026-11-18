"""执行历史页面（自 app.py「Tab 2: 执行历史」段迁入）。"""
import streamlit as st

from app.ui_icons import icon_header


def show_history() -> None:
    ctx = st.session_state.app_context  # 自持：原跨 Tab 依赖 tab1 块内绑定
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
