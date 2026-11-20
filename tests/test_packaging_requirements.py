"""打包依赖 pin 回归测试（Task 8 C1/I4/I5）。

守护构建复现契约：
- C1：云端 LLM 栈（langchain-openai/openai/tiktoken）直 pin 入 requirements.txt，
  防 CI 全新构建产物因 collect_all 缺包告警跳过而云端路线全 ImportError；
- I4：构建工具链（pyinstaller/pyinstaller-hooks-contrib）pin PoC 验证组合；
- I5：packaging/constraints.txt 覆盖全部直接 pin 与关键传递依赖，CI 安装带 -c；
- spec 收集列表含云端栈与 tiktoken_ext 插件包。
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _pins(path: Path) -> dict[str, str]:
    """解析 requirements/constraints 文本中的 name==version 直 pin（归一化名）。"""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line and "==" in line:
            name, version = line.split("==", 1)
            pins[name.strip().lower().replace("_", "-")] = version.strip()
    return pins


def test_cloud_llm_stack_pinned():
    """C1：云端 OpenAI 兼容路线三包直 pin（PoC venv 验证版本）。"""
    pins = _pins(PROJECT_ROOT / "requirements.txt")
    assert pins.get("langchain-openai") == "0.1.0"
    assert pins.get("openai") == "1.109.1"
    assert pins.get("tiktoken") == "0.12.0"


def test_langchain_train_consistent():
    """Task 8：原 langchain 0.1.0/community 0.0.10 声明 langsmith<0.1.0，与
    core 0.1.53 的 langsmith>=0.1.0 交集为空（pip 全新解析必 ResolutionImpossible）。
    锁定上游 0.1.x 末代一致组合；langsmith 保持 PoC venv 验证版本。"""
    pins = _pins(PROJECT_ROOT / "requirements.txt")
    constraints = _pins(PROJECT_ROOT / "packaging" / "constraints.txt")
    assert pins.get("langchain") == "0.1.20"
    assert pins.get("langchain-community") == "0.0.38"
    assert pins.get("langchain-core") == "0.1.53"
    assert constraints.get("langsmith") == "0.1.147"
    assert constraints.get("langchain-text-splitters") == "0.0.2"


def test_build_toolchain_pinned():
    """I4：pyinstaller 与 hooks-contrib（月度 rev）均 pin PoC 验证版本。"""
    pins = _pins(PROJECT_ROOT / "requirements-build.txt")
    assert pins.get("pyinstaller") == "6.22.3"
    assert pins.get("pyinstaller-hooks-contrib") == "2026.10"


def test_constraints_cover_all_direct_pins():
    """I5：requirements*.txt 的每个直 pin 在 constraints.txt 同版本同步。"""
    constraints = _pins(PROJECT_ROOT / "packaging" / "constraints.txt")
    for req in ("requirements.txt", "requirements-build.txt"):
        for name, version in _pins(PROJECT_ROOT / req).items():
            assert constraints.get(name) == version, (
                f"{req}: {name}=={version} 未同步进 packaging/constraints.txt"
            )


def test_constraints_pin_key_transitives():
    """I5：审查点名的关键传递依赖（无约束漂移风险）均有 pin。"""
    constraints = _pins(PROJECT_ROOT / "packaging" / "constraints.txt")
    for name in (
        "altair", "pandas", "pyarrow", "scipy", "tornado", "cryptography",
        "numpy", "protobuf",
    ):
        assert name in constraints, f"缺传递依赖约束：{name}"


def test_ci_installs_with_constraints():
    """I5：CI 安装命令带 -c packaging/constraints.txt（缓存哈希亦含该文件）。"""
    yml = (PROJECT_ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "-c packaging/constraints.txt" in yml
    assert "packaging/constraints.txt" in yml.split("cache-dependency-path")[1]


def test_spec_collects_cloud_stack():
    """C1 配套：spec 收集列表含云端栈；tiktoken_ext 独立插件包显式收集。"""
    spec = (PROJECT_ROOT / "text2sql.spec").read_text(encoding="utf-8")
    for pkg in ('"langchain_openai"', '"openai"', '"tiktoken"'):
        assert pkg in spec
    assert 'collect_submodules("tiktoken_ext")' in spec