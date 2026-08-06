"""
Every tool declared to Gemini in core/tool_declarations.py must be handled
somewhere in main.py (TOOL_REGISTRY or an inline special case), and every
registered handler must correspond to a declared tool.
"""
import ast
import re
from pathlib import Path

from core.tool_declarations import TOOL_DECLARATIONS

ROOT    = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"

# Handled inline in UltronLive._execute_tool (not in TOOL_REGISTRY).
SPECIAL_CASES = {"save_memory"}
# Registered handlers for tools that are intentionally not exposed to Gemini.
ALIASES = {"shutdown_jarvis": "shutdown_ultron"}


def _registry_keys() -> set[str]:
    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "TOOL_REGISTRY"
                and isinstance(node.value, ast.Dict)):
            keys = set()
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
            return keys
    raise AssertionError("TOOL_REGISTRY dict not found in main.py")


DECLARED = {d["name"] for d in TOOL_DECLARATIONS if isinstance(d, dict) and "name" in d}
REGISTERED = _registry_keys()


def test_all_declarations_are_handled():
    missing = DECLARED - REGISTERED - SPECIAL_CASES
    assert not missing, f"Declared tools with no handler: {sorted(missing)}"


def test_all_handlers_are_declared():
    orphaned = REGISTERED - DECLARED - set(ALIASES)
    assert not orphaned, f"Registered handlers for undeclared tools: {sorted(orphaned)}"


def test_alias_points_to_real_tool():
    for alias, target in ALIASES.items():
        assert alias in REGISTERED, f"Alias {alias} not registered"
        assert target in DECLARED, f"Alias {alias} target {target} not declared"


def test_declarations_have_unique_names():
    assert len(DECLARED) == len(TOOL_DECLARATIONS)


def test_required_params_are_declared():
    for d in TOOL_DECLARATIONS:
        props = set(d.get("parameters", {}).get("properties", {}))
        required = set(d.get("parameters", {}).get("required", []))
        assert required <= props, (
            f"Tool '{d['name']}' requires params not in properties: "
            f"{sorted(required - props)}")


def test_shutdown_jarvis_is_aliased_to_same_handler():
    src = MAIN_PY.read_text(encoding="utf-8")
    m = re.search(
        r'"(shutdown_ultron|shutdown_jarvis)"\s*:\s*(_handle_shutdown)',
        src,
    )
    assert m, "shutdown handlers must reference _handle_shutdown"
