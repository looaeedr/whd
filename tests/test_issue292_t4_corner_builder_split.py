import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
MODULE = ROOT / "gui_modules" / "parts" / "panels" / "assembly_corner.py"

REQUIRED_MODULE_FUNCTIONS = {
    "create_corner_type_panel",
    "_build_corner_pair_controls",
    "_build_corner_type_selector",
    "_build_corner_parameter_controls",
}


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _host_methods():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_corner_panel_builder_is_split_into_focused_module_helpers():
    functions = _functions(MODULE)
    missing = sorted(REQUIRED_MODULE_FUNCTIONS - functions.keys())
    assert not missing, f"assembly_corner.py missing split builder owners: {missing}"
    oversized = {
        name: functions[name].end_lineno - functions[name].lineno + 1
        for name in REQUIRED_MODULE_FUNCTIONS
        if functions[name].end_lineno - functions[name].lineno + 1 > 150
    }
    assert not oversized, f"corner builder helper exceeds 150-line method gate: {oversized}"


def test_root_corner_panel_builder_is_thin_delegate():
    node = _host_methods()["create_corner_type_panel"]
    span = node.end_lineno - node.lineno + 1
    assert span <= 4, f"create_corner_type_panel still rooted in gui.py: {span} lines"


def test_module_builder_delegates_sections_instead_of_recreating_giant_method():
    node = _functions(MODULE).get("create_corner_type_panel")
    assert node is not None, "module builder owner is missing"
    calls = {
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    }
    expected = {
        "_build_corner_pair_controls",
        "_build_corner_type_selector",
        "_build_corner_parameter_controls",
    }
    assert expected <= calls, f"module builder must compose focused sections: missing {sorted(expected - calls)}"
