import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
MODULE = ROOT / "gui_modules" / "parts" / "panels" / "assembly_corner.py"

MODULE_FUNCTIONS = {
    "refresh_corner_type_panel",
    "select_manual_corner",
    "draw_corner_type_icon",
    "selection_from_manual_corner_controls",
    "refresh_manual_corner_parameter_rows",
    "toggle_manual_corner_parameter_lock",
}
ROOT_METHODS = {
    "refresh_corner_type_panel",
    "select_manual_corner",
    "_draw_corner_type_icon",
    "_selection_from_manual_corner_controls",
    "_refresh_manual_corner_parameter_rows",
    "toggle_manual_corner_parameter_lock",
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


def test_corner_ui_slice_has_focused_module_owners():
    functions = _functions(MODULE)
    missing = sorted(MODULE_FUNCTIONS - functions.keys())
    assert not missing, f"assembly_corner.py missing corner UI owners: {missing}"


def test_corner_ui_slice_root_methods_are_thin_delegates():
    methods = _host_methods()
    fat = {}
    for name in ROOT_METHODS:
        node = methods.get(name)
        if node is None:
            continue
        span = node.end_lineno - node.lineno + 1
        if span > 4:
            fat[name] = span
    assert not fat, f"corner UI presentation still implemented in gui.py: {fat}"
