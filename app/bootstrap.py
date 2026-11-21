"""系统组件初始化（自 app.py「初始化函数」段迁入）。"""
import streamlit as st
from loguru import logger

from config import (
    BM25_B,
    BM25_K1,
    BM25_WEIGHT,
    DENSE_WEIGHT,
    EMBEDDING_API_BASE,
    EMBEDDING_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    FAISS_EMBEDDING_DIM,
    FAISS_ENABLED,
    FAISS_INDEX_TYPE,
    FEW_SHOT_ENABLED,
    FEW_SHOT_MIN_SIMILARITY,
    FEW_SHOT_TOP_K,
    GOVERNED_HISTORY_BINDING_TTL_SECONDS,
    GRAPH_MAX_DEPTH,
    GRAPH_MAX_EDGES,
    GRAPH_MAX_NODES,
    GRAPH_MAX_STRING_LENGTH,
    HISTORY_MAX_RECORDS,
    INDEX_CACHE_DIR,
    INDEX_CACHE_ENABLED,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    MAX_PREPARED_REQUESTS,
    NEO4J_CONNECTION_TIMEOUT,
    NEO4J_DATABASE,
    NEO4J_ENABLED,
    NEO4J_MAX_POOL_SIZE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    PREPARED_REQUEST_TTL_SECONDS,
    PROMPT_MAX_LENGTH,
    RETRIEVAL_TOP_K,
    SEMANTIC_CONTEXT_MAX_CHARS,
    SEMANTIC_CONTEXT_MAX_ITEMS,
    SEMANTIC_DATASOURCE,
    SEMANTIC_GOVERNANCE_ENABLED,
    SEMANTIC_MODEL_DIR,
    SQL_BLOCKED_TABLES,
    SQL_DIALECT,
    SQL_EXPLAIN_ENABLED,
    SQL_EXPLAIN_MAX_ESTIMATED_ROWS,
    SQL_EXPLAIN_TIMEOUT_MS,
    SQL_MAX_LENGTH,
    SQL_QUERY_MAX_ROWS,
    SQL_QUERY_TIMEOUT_MS,
    SQL_REPAIR_MAX_ATTEMPTS,
    SQL_SCOPE_ENFORCEMENT,
    SQL_VALIDATION_ENABLED,
    SQLITE_PATH,
)
from core.app_context import ApplicationContext
from core.update_checker import start_update_checker


def initialize_system():
    """初始化系统组件（委托给 ApplicationContext）"""
    logger.info("开始初始化系统...")

    # 更新检查后台线程（幂等、daemon、立即返回不阻塞 UI）；
    # 独立于系统初始化成败，UPDATE_CHECK_ENABLED=False 时不起线程。
    start_update_checker()

    app_ctx = ApplicationContext(config={
        'sqlite_path': SQLITE_PATH,
        'history_max_records': HISTORY_MAX_RECORDS,
        'governed_history_binding_ttl_seconds': GOVERNED_HISTORY_BINDING_TTL_SECONDS,
        'neo4j_enabled': NEO4J_ENABLED, 'neo4j_uri': NEO4J_URI,
        'neo4j_user': NEO4J_USER, 'neo4j_password': NEO4J_PASSWORD,
        'neo4j_database': NEO4J_DATABASE,
        'neo4j_max_pool_size': NEO4J_MAX_POOL_SIZE,
        'neo4j_connection_timeout': NEO4J_CONNECTION_TIMEOUT,
        'graph_max_nodes': GRAPH_MAX_NODES, 'graph_max_edges': GRAPH_MAX_EDGES,
        'graph_max_depth': GRAPH_MAX_DEPTH,
        'graph_max_string_length': GRAPH_MAX_STRING_LENGTH,
        'llm_provider': LLM_PROVIDER, 'llm_model': LLM_MODEL,
        'llm_api_key': LLM_API_KEY, 'llm_base_url': LLM_BASE_URL,
        'retrieval_top_k': RETRIEVAL_TOP_K, 'prompt_max_length': PROMPT_MAX_LENGTH,
        'sql_dialect': SQL_DIALECT,
        'sql_validation_enabled': SQL_VALIDATION_ENABLED, 'sql_max_length': SQL_MAX_LENGTH,
        'sql_query_max_rows': SQL_QUERY_MAX_ROWS,
        'sql_query_timeout_ms': SQL_QUERY_TIMEOUT_MS,
        'sql_scope_enforcement': SQL_SCOPE_ENFORCEMENT,
        'sql_blocked_tables': SQL_BLOCKED_TABLES,
        'semantic_governance_enabled': SEMANTIC_GOVERNANCE_ENABLED,
        'semantic_model_dir': SEMANTIC_MODEL_DIR,
        'semantic_datasource': SEMANTIC_DATASOURCE,
        'semantic_context_max_chars': SEMANTIC_CONTEXT_MAX_CHARS,
        'semantic_context_max_items': SEMANTIC_CONTEXT_MAX_ITEMS,
        'sql_repair_max_attempts': SQL_REPAIR_MAX_ATTEMPTS,
        'sql_explain_enabled': SQL_EXPLAIN_ENABLED,
        'sql_explain_timeout_ms': SQL_EXPLAIN_TIMEOUT_MS,
        'sql_explain_max_estimated_rows': SQL_EXPLAIN_MAX_ESTIMATED_ROWS,
        'max_prepared_requests': MAX_PREPARED_REQUESTS,
        'prepared_request_ttl_seconds': PREPARED_REQUEST_TTL_SECONDS,
        'bm25_k1': BM25_K1, 'bm25_b': BM25_B,
        'bm25_weight': BM25_WEIGHT, 'dense_weight': DENSE_WEIGHT,
        'faiss_enabled': FAISS_ENABLED, 'faiss_embedding_dim': FAISS_EMBEDDING_DIM,
        'faiss_index_type': FAISS_INDEX_TYPE,
        'index_cache_enabled': INDEX_CACHE_ENABLED, 'index_cache_dir': INDEX_CACHE_DIR,
        'embedding_provider': EMBEDDING_PROVIDER, 'embedding_model': EMBEDDING_MODEL,
        'embedding_api_key': EMBEDDING_API_KEY, 'embedding_api_base': EMBEDDING_API_BASE,
        'few_shot_enabled': FEW_SHOT_ENABLED, 'few_shot_top_k': FEW_SHOT_TOP_K,
        'few_shot_min_similarity': FEW_SHOT_MIN_SIMILARITY,
    })

    if app_ctx.ensure_initialized():
        st.session_state.app_context = app_ctx
        st.session_state.initialized = True
        logger.info("系统初始化完成")
        return True
    else:
        st.session_state.initialization_error = app_ctx.initialization_error
        logger.error("系统初始化失败")
        return None
