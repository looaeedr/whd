from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
DOOR_PANEL = ROOT / "gui_modules" / "parts" / "panels" / "door.py"

ROOT_METHODS = (
    "_normalize_door_indicator_state",
    "_destroy_door_layout_entry_widgets",
    "_door_layout_entry_menu",
    "rebuild_door_layers_config_ui",
)

PANEL_FUNCTIONS = (
    "normalize_door_indicator_state",
    "destroy_door_layout_entry_widgets",
    "door_layout_entry_menu",
    "rebuild_door_layers_config_ui",
)


def _span(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def _host_methods():
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_task7b_door_panel_exports_shared_review_helpers():
    source = DOOR_PANEL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(name for name in PANEL_FUNCTIONS if name not in functions)
    assert not missing, f"T6 TASK7B RED: door panel helpers missing: {missing}"


def test_task7b_root_shared_review_methods_are_thin_delegates():
    methods = _host_methods()
    oversized = []
    for name in ROOT_METHODS:
        node = methods[name]
        if _span(node) > 3:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK7B RED: root shared review methods are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task7b_panel_does_not_create_committed_state_owner():
    source = DOOR_PANEL.read_text(encoding="utf-8")
    forbidden = (
        "host.door_layout_indicator_states =",
        "host.workspace_controller =",
        "host.project_controller =",
        "host.phase6_project =",
    )
    hits = [token for token in forbidden if token in source]
    assert not hits, f"Task7B panel created committed state owner: {hits}"
