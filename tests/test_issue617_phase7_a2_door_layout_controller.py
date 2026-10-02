from __future__ import annotations

import ast
from pathlib import Path

from gui_modules.application.door_layout_controller import (
    DoorLayoutColumnState,
    recompute_door_layout,
    remap_owned_data,
    validate_height_commit,
    validate_width_commit,
)

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
CONTROLLER = ROOT / "gui_modules" / "application" / "door_layout_controller.py"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_issue617_controller_is_tk_and_gui_independent():
    source = CONTROLLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name == "tkinter" or name.startswith("tkinter.") for name in imports)
    assert "gui" not in imports
    assert "fold_designer_bridge" not in imports


def test_issue617_recompute_generates_width_and_height_remainders():
    result = recompute_door_layout(
        (
            DoorLayoutColumnState(400.0, False, (500.0,), (False,)),
        ),
        total_width=1000.0,
        total_height=1200.0,
        selected_key="9:9",
    )
    assert [(c.width, c.width_auto) for c in result.columns] == [
        (400.0, False),
        (600.0, True),
    ]
    assert result.columns[0].heights == (500.0, 700.0)
    assert result.columns[0].height_auto == (False, True)
    assert result.selected_key == "1:0"


def test_issue617_commit_validation_preserves_auto_only_at_exact_remainder():
    columns = (
        DoorLayoutColumnState(400.0, False, (500.0, 700.0), (False, True)),
        DoorLayoutColumnState(600.0, True, (1200.0,), (True,)),
    )
    ok = validate_width_commit(columns, 1, 1000.0, 600.0)
    changed = validate_width_commit(columns, 1, 1000.0, 550.0)
    assert ok.valid and ok.keep_auto
    assert changed.valid and not changed.keep_auto

    height_ok = validate_height_commit(columns, 0, 1, 1200.0, 700.0)
    height_changed = validate_height_commit(columns, 0, 1, 1200.0, 650.0)
    assert height_ok.valid and height_ok.keep_auto
    assert height_changed.valid and not height_changed.keep_auto


def test_issue617_remap_owned_data_is_pure():
    source = {"0:0": "a", "0:1": "b", "1:0": "c"}
    result = remap_owned_data(
        source,
        lambda c, r: None if (c, r) == (0, 0) else (c + 1, r),
    )
    assert result == {"1:1": "b", "2:0": "c"}
    assert source == {"0:0": "a", "0:1": "b", "1:0": "c"}


def test_issue617_host_delegates_numeric_door_layout_logic():
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    methods = {
        node.name: node for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_recompute_column_height_remainder" not in methods
    assert _span(methods["_recompute_door_layout_remainders"]) <= 35
    assert _span(methods["_remap_door_layout_owned_data"]) <= 12
    host_source = ast.get_source_segment(source, host) or ""
    assert "complete_partition(" not in host_source
    assert "validate_door_layout_dimensions(" not in host_source
    assert "_recompute_door_layout_impl(" in host_source
    assert "_validate_door_layout_width_commit_impl(" in host_source
    assert "_validate_door_layout_height_commit_impl(" in host_source
