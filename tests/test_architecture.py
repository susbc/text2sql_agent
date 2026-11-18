# tests/test_architecture.py
"""架构守护：app.py 薄入口 + 模块入口 + 无循环 import + CSS 注入。"""
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]

def test_app_entry_is_thin():
    assert len((ROOT / "app.py").read_text(encoding="utf-8").splitlines()) <= 250

def test_ui_modules_expose_entry_points():
    entries = {
        "app.styles": "inject_global_styles",
        "app.state": "init_session_state",
        "app.bootstrap": "initialize_system",
        "app.sidebar": "render_sidebar",
        "app.model_config": "render_model_config_panel",
        "app.pages.sql_generation": "show_sql_generation",
        "app.pages.history": "show_history",
        "app.pages.system_info": "show_system_info",
    }
    for mod, fn in entries.items():
        assert callable(getattr(importlib.import_module(mod), fn)), f"{mod}.{fn}"

def test_no_cycle_to_entry():
    for p in list((ROOT / "app").glob("*.py")) + list((ROOT / "app" / "pages").glob("*.py")):
        src = p.read_text(encoding="utf-8")
        assert "from app import" not in src and "import app\n" not in src, p

def test_custom_css_injected():
    # 密封启动：复用 test_model_config_panel 的 FakeContext 模式，不依赖真实 DB
    from tests.test_model_config_panel import FakeContext, _base_config, _launch
    at = _launch(FakeContext(_base_config()))
    assert any(".main-title" in m.value for m in at.markdown)
