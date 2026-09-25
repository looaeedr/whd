import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
MODULE = ROOT / "gui_modules" / "parts" / "panels" / "assembly_corner.py"

SLICE = {
    "sync_endcap_fw_controls",
    "sync_fold_designer_manual_corner_context",
    "fixed_corner_summary",
    "normalize_manual_corner_target",
    "corner_parameter_summary",
}

ROOT_METHODS = {
    "_sync_endcap_fw_controls",
    "_sync_fold_designer_manual_corner_context",
    "_fixed_corner_summary",
    "_normalize_manual_corner_target",
    "_corner_parameter_summary",
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


def test_first_corner_slice_has_focused_module_owners():
    functions = _functions(MODULE)
    missing = sorted(SLICE - functions.keys())
    assert not missing, f"assembly_corner.py missing T4 slice implementations: {missing}"


def test_first_corner_slice_root_methods_are_thin_delegates():
    methods = _host_methods()
    fat = {
        name: methods[name].end_lineno - methods[name].lineno + 1
        for name in ROOT_METHODS
        if name not in methods or methods[name].end_lineno - methods[name].lineno + 1 > 4
    }
    assert not fat, f"first T4 corner slice still implemented in gui.py: {fat}"


def test_corner_slice_module_does_not_import_root_gui_or_compatibility():
    text = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name == "gui" or name.startswith("gui.") for name in imports)
    assert not any("compatibility" in name for name in imports)
