"""模型配置辅助函数（自 app.py「模型配置辅助函数」段迁入）。"""
import streamlit as st
from loguru import logger

from app.ui_icons import icon_header
from config import (
    EMBEDDING_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    EMBEDDING_PROVIDERS,
    FAISS_EMBEDDING_DIM,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_PROVIDERS,
)
from core.app_context import ApplicationConfigurationError
from core.utils.log_sanitizer import log_safe_exception


_CONFIG_LOG_HINT = "详情请查看 logs/app.log 中的错误编号"


def _apply_llm_config(provider: str, model: str, api_key: str, base_url: str) -> tuple[bool, str]:
    """应用 LLM 配置变更，热重载 LLM 相关组件。

    返回 (是否成功, 可直接展示的详情)。成功时详情是"提供商 / 模型"，由调用方
    加自己的前缀；失败时详情就是完整消息。`ApplicationConfigurationError` 的
    消息按设计只含配置键名、不含取值，因此可以原样呈现；其他异常只给日志指引，
    避免把连接串或栈信息带回浏览器。
    """
    ctx = st.session_state.get("app_context")
    if not ctx:
        return False, "系统未初始化，无法切换 LLM"
    label = LLM_PROVIDERS.get(provider, {}).get("label", provider)
    try:
        ctx.reload_llm(
            llm_provider=provider,
            llm_model=model,
            llm_api_key=api_key,
            llm_base_url=base_url,
        )
    except ApplicationConfigurationError as e:
        log_safe_exception("llm_config_reload", e)
        return False, f"LLM 配置未生效：{e}"
    except Exception as e:
        log_safe_exception("llm_config_reload", e)
        return False, f"LLM 加载失败，{_CONFIG_LOG_HINT}"
    logger.info(f"LLM 配置已更新：{provider}/{model}")
    return True, f"{label} / {model}"


def _apply_embedding_config(provider: str, model: str, api_key: str) -> tuple[bool, str]:
    """应用 Embedding 配置变更，热重载 Embedding 和检索器。返回值语义同 LLM。"""
    ctx = st.session_state.get("app_context")
    if not ctx:
        return False, "系统未初始化，无法切换 Embedding"
    label = EMBEDDING_PROVIDERS.get(provider, {}).get("label", provider)
    # 维度回落到 FAISS_EMBEDDING_DIM，与既有索引保持一致
    dim = EMBEDDING_PROVIDERS.get(provider, {}).get("dimensions", FAISS_EMBEDDING_DIM)
    try:
        ctx.reload_embedding(
            embedding_provider=provider,
            embedding_model=model,
            embedding_api_key=api_key,
            faiss_embedding_dim=dim,
        )
    except ApplicationConfigurationError as e:
        log_safe_exception("embedding_config_reload", e)
        return False, f"Embedding 配置未生效：{e}"
    except Exception as e:
        log_safe_exception("embedding_config_reload", e)
        return False, f"Embedding 加载失败，{_CONFIG_LOG_HINT}"
    logger.info(f"Embedding 配置已更新：{provider}/{model}")
    return True, f"{label} / {model}"


def _active_model_config() -> dict:
    """当前生效的模型配置。

    `ctx.config` 是热重载后原子发布的只读快照，因此它是唯一真相源；不再另存
    一份 `_llm_*` / `_emb_*` 覆盖键，避免"界面显示的值"与"实际生效的值"分叉。
    """
    values = {
        'llm_provider': LLM_PROVIDER,
        'llm_model': LLM_MODEL,
        'llm_api_key': LLM_API_KEY,
        'llm_base_url': LLM_BASE_URL,
        'embedding_provider': EMBEDDING_PROVIDER,
        'embedding_model': EMBEDDING_MODEL,
        'embedding_api_key': EMBEDDING_API_KEY,
    }
    ctx = st.session_state.get("app_context")
    if ctx:
        try:
            live = ctx.config
        except Exception as e:
            log_safe_exception("model_config_read", e)
            live = {}
        values.update({k: v for k, v in live.items() if k in values})
    return values


def _reseed_model_widgets(prefix: str) -> None:
    """在实例化控件之前清掉指定前缀的控件状态。

    Streamlit 禁止在控件实例化之后改写其 session_state，因此清理必须发生在
    面板顶部；标记由上一次保存/恢复动作设置。
    """
    flag = f"_{prefix}_reseed"
    if not st.session_state.get(flag, False):
        return
    # 本轮若由保存/恢复按钮触发，cfg_* 里是用户随点击一并提交的新值，
    # 此刻清除会用旧配置覆盖它，导致本次保存静默写回旧模型；保留标记，
    # 待下一轮（无按钮触发）再重新播种。
    save_key, reset_key = (
        ("btn_save_llm", "btn_reset_llm")
        if prefix == "llm"
        else ("btn_save_emb", "btn_reset_emb")
    )
    if st.session_state.get(save_key) or st.session_state.get(reset_key):
        return
    st.session_state.pop(flag, None)
    for key in list(st.session_state.keys()):
        if key.startswith(f"cfg_{prefix}_"):
            st.session_state.pop(key, None)


def render_model_config_panel():
    """渲染模型配置 UI 面板（LLM + Embedding）"""
    st.markdown(icon_header("模型配置", "sliders-horizontal", level=3), unsafe_allow_html=True)
    st.caption("切换大语言模型或向量模型后点击保存，系统将自动重载相关组件。")

    # 清理必须早于任何控件实例化
    _reseed_model_widgets("llm")
    _reseed_model_widgets("emb")

    # 读取当前生效配置（来自 ctx.config 快照，否则回落到环境变量）
    active = _active_model_config()
    current_llm_provider = active['llm_provider']
    current_llm_model = active['llm_model']
    # 密钥只在服务端用于"留空即沿用"判定，绝不作为控件初值下发到浏览器
    current_llm_api_key = active['llm_api_key']
    current_llm_base_url = active['llm_base_url']

    current_emb_provider = active['embedding_provider']
    current_emb_model = active['embedding_model']
    current_emb_api_key = active['embedding_api_key']

    # ── LLM 配置 ──
    with st.expander("── 大语言模型 (LLM) ──", expanded=False):
        provider_labels = {k: v["label"] for k, v in LLM_PROVIDERS.items()}
        provider_keys = list(LLM_PROVIDERS.keys())
        provider_display = [provider_labels[k] for k in provider_keys]

        current_idx = provider_keys.index(current_llm_provider) if current_llm_provider in provider_keys else 0

        selected_label = st.selectbox(
            "提供商",
            options=provider_display,
            index=current_idx,
            key="cfg_llm_provider",
        )
        selected_provider = provider_keys[provider_display.index(selected_label)]
        provider_info = LLM_PROVIDERS[selected_provider]

        # 默认模型：如果用户手动填过就用用户的，否则用提供商推荐
        if selected_provider == current_llm_provider:
            default_model = current_llm_model
        else:
            default_model = provider_info["default_model"]

        st.text_input(
            "模型名称",
            value=default_model,
            key="cfg_llm_model",
            help="输入模型名称，如 gpt-4o、qwen-max、qwen2.5 等",
        )

        if provider_info["needs_api_key"]:
            st.text_input(
                "API Key",
                value="",
                type="password",
                key="cfg_llm_api_key",
                help="出于安全考虑不回显已生效的密钥；留空表示沿用当前密钥，填写则替换",
            )
        else:
            st.caption("此提供商无需 API Key")
            st.session_state["cfg_llm_api_key"] = ""

        if provider_info["needs_base_url"]:
            st.text_input(
                "Base URL",
                value=current_llm_base_url or provider_info["default_base_url"],
                key="cfg_llm_base_url",
                help=f"默认：{provider_info['default_base_url'] or '（无）'}",
            )
        else:
            st.caption("使用官方默认 API 地址")
            st.session_state["cfg_llm_base_url"] = ""

        col_save_llm, col_reset_llm = st.columns([1, 1])
        with col_save_llm:
            if st.button(" 保存并重新加载 LLM", use_container_width=True, type="primary", key="btn_save_llm"):
                new_provider = selected_provider
                new_model = st.session_state.get("cfg_llm_model", provider_info["default_model"])
                entered_key = st.session_state.get("cfg_llm_api_key", "")
                # 留空表示沿用当前生效的密钥；无需密钥的提供商不下发任何密钥
                if provider_info["needs_api_key"]:
                    new_api_key = entered_key or current_llm_api_key
                else:
                    new_api_key = ""
                new_base_url = st.session_state.get("cfg_llm_base_url", "")

                with st.spinner("正在重新加载 LLM..."):
                    ok, detail = _apply_llm_config(
                        new_provider, new_model, new_api_key, new_base_url
                    )

                if ok:
                    # ctx.config 已成为唯一真相源；只需让控件在下一轮重新播种
                    st.session_state["_llm_reseed"] = True
                    st.success(f"LLM 已切换为：{detail}")
                else:
                    st.error(detail)

        with col_reset_llm:
            if st.button("恢复默认 LLM 配置", use_container_width=True, key="btn_reset_llm"):
                with st.spinner("正在恢复 .env 默认 LLM 配置..."):
                    ok, detail = _apply_llm_config(
                        LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL
                    )
                if ok:
                    st.session_state["_llm_reseed"] = True
                    st.success(f"已恢复 .env 默认 LLM：{detail}")
                else:
                    st.error(f"恢复默认失败，当前生效配置保持不变。{detail}")

    st.markdown("")

    # ── Embedding 配置 ──
    with st.expander("── 向量模型 (Embedding) ─", expanded=False):
        emb_provider_labels = {k: v["label"] for k, v in EMBEDDING_PROVIDERS.items()}
        emb_provider_keys = list(EMBEDDING_PROVIDERS.keys())
        emb_provider_display = [emb_provider_labels[k] for k in emb_provider_keys]

        current_emb_idx = emb_provider_keys.index(current_emb_provider) if current_emb_provider in emb_provider_keys else 0

        selected_emb_label = st.selectbox(
            "提供商",
            options=emb_provider_display,
            index=current_emb_idx,
            key="cfg_emb_provider",
        )
        selected_emb_provider = emb_provider_keys[emb_provider_display.index(selected_emb_label)]
        emb_provider_info = EMBEDDING_PROVIDERS[selected_emb_provider]

        if selected_emb_provider == current_emb_provider:
            emb_default_model = current_emb_model
        else:
            emb_default_model = emb_provider_info["default_model"]

        st.text_input(
            "模型名称",
            value=emb_default_model,
            key="cfg_emb_model",
            help="输入 Embedding 模型名称，如 text-embedding-v3、nomic-embed-text 等",
        )

        if emb_provider_info["needs_api_key"]:
            st.text_input(
                "API Key",
                value="",
                type="password",
                key="cfg_emb_api_key",
                help="出于安全考虑不回显已生效的密钥；留空表示沿用当前密钥，填写则替换",
            )
        else:
            st.caption("此提供商无需 API Key（本地模型）")
            st.session_state["cfg_emb_api_key"] = ""

        col_save_emb, col_reset_emb = st.columns([1, 1])
        with col_save_emb:
            if st.button("保存并重新加载 Embedding", use_container_width=True, type="primary", key="btn_save_emb"):
                new_emb_provider = selected_emb_provider
                new_emb_model = st.session_state.get("cfg_emb_model", emb_provider_info["default_model"])
                entered_emb_key = st.session_state.get("cfg_emb_api_key", "")
                # 留空表示沿用当前生效的密钥；无需密钥的提供商不下发任何密钥
                if emb_provider_info["needs_api_key"]:
                    new_emb_api_key = entered_emb_key or current_emb_api_key
                else:
                    new_emb_api_key = ""

                with st.spinner("正在重新加载 Embedding 和知识库索引..."):
                    ok, detail = _apply_embedding_config(
                        new_emb_provider, new_emb_model, new_emb_api_key
                    )

                if ok:
                    st.session_state["_emb_reseed"] = True
                    st.success(f"Embedding 已切换为：{detail}")
                else:
                    st.error(detail)

        with col_reset_emb:
            if st.button("↩恢复默认 Embedding 配置", use_container_width=True, key="btn_reset_emb"):
                with st.spinner("正在恢复 .env 默认 Embedding 配置..."):
                    ok, detail = _apply_embedding_config(
                        EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_API_KEY
                    )
                if ok:
                    st.session_state["_emb_reseed"] = True
                    st.success(f"已恢复 .env 默认 Embedding：{detail}")
                else:
                    st.error(f"恢复默认失败，当前生效配置保持不变。{detail}")
