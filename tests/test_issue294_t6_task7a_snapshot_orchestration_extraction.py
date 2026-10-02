from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
APP = ROOT / "gui_modules" / "application" / "render_snapshots.py"

SNAPSHOT_METHODS = (
    "_indicator_box_render_snapshot",
    "_indicator_door_render_snapshot",
    "_door_layout_overview_snapshot",
    "_door_layout_divider_frame_snapshot",
    "_single_door_render_snapshot",
    "_base_plate_render_snapshot",
    "_box_body_render_snapshot",
    "_end_cap_render_snapshot",
)

APP_HELPERS = (
    "indicator_box_render_snapshot",
    "indicator_door_render_snapshot",
    "door_layout_overview_snapshot",
    "door_layout_divider_frame_snapshot",
    "single_door_render_snapshot",
    "base_plate_render_snapshot",
    "box_body_render_snapshot",
    "end_cap_render_snapshot",
)

T7_HOLD_METHODS = (
    "_authoritative_render_data",
    "_manufacturing_context",
    "_box_body_part_spec_from_values",
    "_box_body_part_spec",
    "_end_cap_part_spec_from_values",
    "_end_cap_part_spec",
    "_door_part_spec_from_values",
    "_single_door_part_spec",
    "_door_layout_part_spec",
    "_base_plate_part_spec_from_values",
    "_base_plate_part_spec",
    "_indicator_box_part_spec_from_values",
    "_indicator_box_part_spec",
    "_indicator_door_part_spec_from_values",
    "_indicator_door_part_spec",
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
    return source, {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_task7a_application_snapshot_module_exists_with_all_helpers():
    assert APP.is_file(), "T6 TASK7A RED: application render_snapshots.py missing"
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(name for name in APP_HELPERS if name not in functions)
    assert not missing, f"T6 TASK7A RED: snapshot helpers missing: {missing}"


def test_task7a_root_snapshot_methods_are_thin_delegates():
    _source, methods = _host_methods()
    oversized = []
    for name in SNAPSHOT_METHODS:
        node = methods[name]
        if _span(node) > 3:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK7A RED: root snapshot orchestration is not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task7a_application_module_does_not_define_t7_hold_authority():
    if not APP.is_file():
        return
    source = APP.read_text(encoding="utf-8")
    stolen = sorted(name for name in T7_HOLD_METHODS if f"def {name}(" in source)
    assert not stolen, f"Task7A application module stole T7 HOLD authority: {stolen}"
    assert "import gui" not in source
    assert "compatibility.legacy_exports" not in source
