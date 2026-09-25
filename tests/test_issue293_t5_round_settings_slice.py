import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"


def _function_span(node):
    return node.end_lineno - node.lineno + 1


def test_round_settings_moves_out_of_unified_root():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost")
    unified = next(node for node in host.body if isinstance(node, ast.FunctionDef) and node.name == "_open_unified_hole_editor")
    nested = [
        node.name
        for node in ast.walk(unified)
        if isinstance(node, ast.FunctionDef) and node is not unified
    ]
    assert "open_round_hole_settings" not in nested


def test_round_settings_has_view_entrypoint_and_authority_markers():
    source = VIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "open_round_hole_settings" in functions
    assert _function_span(functions["open_round_hole_settings"]) <= 150

    for marker in (
        "HoleEditorAction.commit_active",
        "HoleEditorAction.preview_all",
        "HoleEditorAction.cancel_active",
        "generate_round_fill",
        "generate_round_refill",
        "align_circle_to_neighbor",
        'WM_DELETE_WINDOW',
        '<Escape>',
    ):
        assert marker in source


def test_round_settings_view_does_not_import_gui_authority():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "gui" not in imported
    assert "compatibility.legacy_exports" not in imported
