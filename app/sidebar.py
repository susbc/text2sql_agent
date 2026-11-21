"""侧边栏（自 app.py「侧边栏」段迁入）。"""
import json
from pathlib import Path

import streamlit as st

from app.bootstrap import initialize_system
from app.ui_icons import icon_header, icon_line
from config import (
    APP_VERSION,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    FEW_SHOT_ENABLED,
    FEW_SHOT_TOP_K,
    NEO4J_ENABLED,
    SQLITE_PATH,
    UPLOAD_MAX_BYTES,
)
from core.update_checker import get_cached_update
from core.utils.upload_limits import UploadValidationError, read_uploaded_text

project_root = Path(__file__).resolve().parent.parent
LOGO_PATH = project_root / "assets" / "logo.png"


def get_knowledge_graph_template() -> dict:
    """返回知识图谱 JSON 导入模板。"""
    return {
        "version": "2.0",
        "format": "text2sql_knowledge_graph",
        "nodes": [
            {
                "label": "Database",
                "properties": {
                    "database_id": 1,
                    "name": "example_db",
                    "db_type": "mysql",
                    "db_language": "SQL",
                    "description": "示例数据库"
                }
            },
            {
                "label": "Table",
                "properties": {
                    "name": "customer",
                    "database": "example_db",
                    "database_id": 1,
                    "description": "客户表",
                    "is_view": False
                }
            },
            {
                "label": "Column",
                "properties": {
                    "name": "customer_id",
                    "table_name": "customer",
                    "database_id": 1,
                    "data_type": "BIGINT",
                    "description": "客户 ID",
                    "is_primary_key": True,
                    "is_nullable": False
                }
            }
        ],
        "edges": [
            {
                "type": "HAS_TABLE",
                "start": {
                    "label": "Database",
                    "properties": {"database_id": 1, "name": "example_db"}
                },
                "end": {
                    "label": "Table",
                    "properties": {"database_id": 1, "name": "customer"}
                },
                "properties": {}
            },
            {
                "type": "HAS_COLUMN",
                "start": {
                    "label": "Table",
                    "properties": {"database_id": 1, "name": "customer"}
                },
                "end": {
                    "label": "Column",
                    "properties": {"database_id": 1, "table_name": "customer", "name": "customer_id"}
                },
                "properties": {}
            }
        ],
        "databases": [
            {
                "database_id": 1,
                "name": "example_db",
                "db_type": "mysql",
                "db_language": "SQL",
                "description": "示例数据库"
            }
        ],
        "tables": [
            {
                "name": "customer",
                "database": "example_db",
                "database_id": 1,
                "description": "客户表",
                "is_view": False
            }
        ],
        "columns": [
            {
                "name": "customer_id",
                "table_name": "customer",
                "database_id": 1,
                "data_type": "BIGINT",
                "description": "客户 ID",
                "is_primary_key": True,
                "is_nullable": False
            }
        ],
        "relationships": [
            {
                "relationship_type": "CONNECTS",
                "from_table": "customer",
                "from_database_id": 1,
                "from_column": "customer_id",
                "to_table": "order",
                "to_database_id": 1,
                "to_column": "customer_id",
                "join_type": "LEFT JOIN",
                "weight": 1.0,
                "occurrence_count": 1,
                "source": "manual"
            }
        ],
        "concepts": [
            {
                "name": "客户域",
                "description": "客户相关数据",
                "tags": ["客户"],
                "related_tables": ["customer"]
            }
        ]
    }


def _render_sidebar_logo() -> None:
    """侧栏品牌 logo：点击放大全屏，再点击缩小。

    用 components.html（同源 iframe）实现：Streamlit 的 st.markdown 会
    剥掉内联事件属性且 <script> 不执行，iframe 内不受此限；通过
    window.frameElement 把 iframe 自身撑满视口来模拟全屏。
    """
    import base64

    import streamlit.components.v1 as components

    data = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    full_path = project_root / "assets" / "logo_full.png"
    data_full = (
        base64.b64encode(full_path.read_bytes()).decode()
        if full_path.exists() else data
    )
    components.html(
        f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:transparent;}}
#ss-logo{{width:160px;cursor:zoom-in;display:block;}}
</style></head><body>
<img id="ss-logo" src="data:image/png;base64,{data}" title="点击放大" alt="溯算编程"/>
<script>
(function () {{
  var img = document.getElementById('ss-logo');
  var frame = window.frameElement;
  var saved = frame.getAttribute('style') || '';
  var big = false;
  img.onclick = function () {{
    big = !big;
    if (big) {{
      frame.style.cssText =
        'position:fixed;inset:0;width:100vw;height:100vh;z-index:999999;border:0;';
      document.body.style.background = 'rgba(15,17,26,.88)';
      img.src = 'data:image/png;base64,{data_full}';
      // 原图 1312×1199，按视口等比放大到 92%
      img.style.cssText =
        'width:min(92vw, 100.7vh);height:auto;cursor:zoom-out;position:absolute;' +
        'top:50%;left:50%;transform:translate(-50%,-50%);';
    }} else {{
      frame.style.cssText = saved;
      document.body.style.background = 'transparent';
      img.src = 'data:image/png;base64,{data}';
      img.style.cssText = 'width:160px;cursor:zoom-in;display:block;';
    }}
  }};
}})();
</script>
</body></html>""",
        height=152,
    )


def _render_update_banner() -> None:
    """新版提示横幅（自动更新 spec §3.4）。

    读后台检查器的线程安全缓存（非阻塞、无网络）；有新版且未按版本关闭时
    显示 info + 下载链接 + 关闭按钮。关闭只记录被关闭的版本号，
    更新版本出现时横幅会重新触发。
    """
    update = get_cached_update()
    if update is None:
        return
    latest = update["latest_version"]
    if st.session_state.get("update_dismissed") == latest:
        return
    st.info(f"🎉 发现新版本 v{latest}（当前 v{APP_VERSION}）")
    st.link_button("下载更新", update["url"])
    if st.button("关闭", key="dismiss_update"):
        st.session_state["update_dismissed"] = latest
        st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        if LOGO_PATH.exists():
            _render_sidebar_logo()
        st.markdown(icon_header("控制中心", "settings", level=1, size=22), unsafe_allow_html=True)

        # 新版提示（有新版且未关闭时才渲染，不影响既有控件）
        _render_update_banner()

        # 系统状态卡片
        st.markdown(icon_header("系统状态", "activity", level=3), unsafe_allow_html=True)
        ctx = st.session_state.app_context
        if st.session_state.initialized and ctx:
            st.success("系统已初始化")

            col1, col2 = st.columns(2)
            with col1:
                if NEO4J_ENABLED:
                    st.markdown(icon_line("Neo4j", "network"), unsafe_allow_html=True)
                    st.caption("已启用" if ctx.neo4j_client and ctx.neo4j_client.driver else "未连接")
                else:
                    st.markdown(icon_line("SQLite 模式", "database"), unsafe_allow_html=True)
                    st.caption("元数据模式")
            with col2:
                st.markdown(icon_line("SQLite", "database"), unsafe_allow_html=True)
                db_status = "已连接" if (ctx.db_client and ctx.db_client.engine) else "未连接"
                st.caption(db_status)
                db_path = getattr(ctx.db_client, "path", None) or SQLITE_PATH
                st.caption(f"文件：{Path(db_path).name}")

            st.markdown(icon_line("Embedding", "plug"), unsafe_allow_html=True)
            st.caption(f"{EMBEDDING_PROVIDER}/{EMBEDDING_MODEL}")

            st.markdown(icon_line("Few-Shot", "target"), unsafe_allow_html=True)
            st.caption(f"{'已启用' if FEW_SHOT_ENABLED else '禁用'} (top {FEW_SHOT_TOP_K})")
        else:
            st.warning("系统未初始化")
            with st.spinner("正在初始化系统..."):
                init_result = initialize_system()
                if init_result:
                    st.success("初始化成功!")
                    st.rerun()
                else:
                    st.error(
                        st.session_state.get("initialization_error")
                        or "初始化失败，请检查配置"
                    )

        st.divider()

        # 重新初始化系统按钮
        if st.button("重新初始化系统", use_container_width=True, type="secondary"):
            if ctx:
                ctx.reset()
            for key in ['initialized', 'app_context']:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("系统状态已重置，正在重新初始化...")
            st.rerun()

        st.divider()

        # 会话信息
        st.markdown(icon_header("会话信息", "messages-square", level=3), unsafe_allow_html=True)
        st.code(f"{st.session_state.session_id[:12]}...", language="text")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("清空历史", use_container_width=True):
                st.session_state.history = []
                st.session_state.last_sql = None
                st.session_state.last_result = None
                st.success("历史已清空")
        with col2:
            st.metric("会话数", len(st.session_state.get('history', [])))

        st.divider()

        # 知识库管理
        st.markdown(icon_header("知识库管理", "archive", level=3), unsafe_allow_html=True)

        if NEO4J_ENABLED and ctx and ctx.neo4j_client and ctx.neo4j_client.driver:
            neo4j = ctx.neo4j_client
            try:
                stats = neo4j.execute_query("""
                MATCH (n)
                OPTIONAL MATCH (n)-[r]-()
                RETURN
                    count(DISTINCT n) as nodes,
                    count(DISTINCT r) as relationships
            """)
                if stats:
                    st.caption(f"节点：{stats[0].get('nodes', 0)} | 关系：{stats[0].get('relationships', 0)}")
            except Exception:
                st.caption("无法获取知识库统计")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("导出", use_container_width=True, type="secondary"):
                    if st.session_state.initialized:
                        with st.spinner("正在导出知识库..."):
                            export_data = neo4j.export_knowledge_graph()
                            if export_data:
                                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                                st.download_button(
                                    label="点击下载 JSON 文件",
                                    data=json_str,
                                    file_name=f"knowledge_graph_{st.session_state.session_id[:8]}.json",
                                    mime="application/json",
                                    use_container_width=True
                                )
            with col2:
                st.download_button(
                    label="下载模板",
                    data=json.dumps(get_knowledge_graph_template(), ensure_ascii=False, indent=2),
                    file_name="knowledge_graph_template.json",
                    mime="application/json",
                    use_container_width=True,
                    help="下载可导入的知识图谱 JSON 模板"
                )

            uploaded_file = st.file_uploader(
                "上传知识库 JSON 文件",
                type=["json"],
                accept_multiple_files=False,
                help="上传之前导出的知识库 JSON 文件进行恢复"
            )

            if uploaded_file is not None:
                try:
                    content = read_uploaded_text(uploaded_file, UPLOAD_MAX_BYTES)
                    import_data = json.loads(content)
                except json.JSONDecodeError as e:
                    import_data = None
                    st.error(f"JSON 格式异常：第 {e.lineno} 行第 {e.colno} 列，{e.msg}")
                except UploadValidationError as e:
                    import_data = None
                    st.error(str(e))

                if import_data is None:
                    st.warning("格式异常，是否下载模板后按模板调整？")
                    st.download_button(
                        label="下载知识图谱 JSON 模板",
                        data=json.dumps(get_knowledge_graph_template(), ensure_ascii=False, indent=2),
                        file_name="knowledge_graph_template.json",
                        mime="application/json",
                        use_container_width=True
                    )
                else:
                    validation = neo4j.validate_knowledge_graph_json(import_data)
                    if not validation["valid"]:
                        st.error("知识图谱 JSON 结构异常：")
                        for error in validation["errors"]:
                            st.write(f"- {error}")
                        st.warning("是否下载模板后按模板调整？")
                        st.download_button(
                            label="下载知识图谱 JSON 模板",
                            data=json.dumps(get_knowledge_graph_template(), ensure_ascii=False, indent=2),
                            file_name="knowledge_graph_template.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    else:
                        database_refs = validation.get("database_refs", [])
                        existing_databases = neo4j.get_existing_import_databases(import_data)
                        if database_refs:
                            st.caption("导入文件包含数据库：" + "、".join(
                                str(db.get("name") or db.get("database_id")) for db in database_refs
                            ))

                        if existing_databases:
                            st.warning(
                                "检测到导入文件中的数据库图谱已存在："
                                + "、".join(str(db.get("name") or db.get("database_id")) for db in existing_databases)
                                + "。请确认是否覆盖这些数据库的现有图谱。"
                            )
                            confirm_import = st.checkbox(
                                "确认覆盖已存在数据库图谱",
                                key="confirm_overwrite_import_kg"
                            )
                            import_clicked = st.button(
                                "覆盖并导入",
                                type="primary",
                                use_container_width=True,
                                disabled=not confirm_import,
                                key="overwrite_import_kg_btn"
                            )
                            overwrite = True
                        else:
                            st.info("未检测到同名或同 ID 数据库图谱，将直接导入。")
                            import_clicked = st.button(
                                "直接导入",
                                type="primary",
                                use_container_width=True,
                                key="direct_import_kg_btn"
                            )
                            overwrite = False

                        if import_clicked:
                            with st.spinner("正在导入知识库..."):
                                result = neo4j.import_knowledge_graph(import_data, overwrite=overwrite)
                                if "error" in result:
                                    st.error(f"导入失败：{result['error']}")
                                else:
                                    st.success(
                                        f"导入完成：{result['nodes']} 个节点，"
                                        f"{result['relationships']} 个关系"
                                    )
                                    if ctx:
                                        ctx.reset()
                                    for key in ['initialized', 'app_context']:
                                        if key in st.session_state:
                                            del st.session_state[key]
                                    st.rerun()

            col_clear1, col_clear2 = st.columns([3, 1])
            with col_clear1:
                if "confirm_clear_kg" not in st.session_state:
                    st.session_state.confirm_clear_kg = False
                clear_confirm = st.checkbox("确认清除", key="confirm_clear_kg",
                                            help="勾选后点击清除按钮将删除所有知识图谱数据")
            with col_clear2:
                clear_btn = st.button("清除知识库", use_container_width=True, type="secondary",
                                     disabled=not clear_confirm)

            if clear_btn:
                if st.session_state.initialized:
                    with st.spinner("正在清除知识库..."):
                        result = neo4j.clear_knowledge_graph()
                        if "error" in result:
                            st.error(f"清除失败：{result['error']}")
                        else:
                            st.success(f"已删除 {result['nodes']} 个节点，{result['relationships']} 个关系")
                            if ctx:
                                ctx.reset()
                            for key in ['initialized', 'app_context']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            if "confirm_clear_kg" in st.session_state:
                                del st.session_state.confirm_clear_kg
                            st.success("知识库已清除，系统将重新初始化...")
                            st.rerun()
        else:
            st.caption("Neo4j 未启用")

        st.divider()

        # 关于
        st.markdown(icon_header("关于", "info", level=3), unsafe_allow_html=True)
        st.markdown("""
    **溯算编程 · Text2SQL 智能体 v1.0**

    基于本地知识库的 SQL 智能生成系统

    **核心技术**:
    - BM25 + FAISS 混合检索
    - LangChain + LLM 智能生成
    - SQLFluff 语法校验
    - Neo4j/SQLite 双模式
    """)

        st.markdown("---")
        st.caption("© 2026 溯算编程")
