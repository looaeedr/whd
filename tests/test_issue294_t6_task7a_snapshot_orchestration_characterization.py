from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"

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


def test_task7a_keeps_all_snapshot_entrypoints_on_host():
    methods = _host_methods()
    missing = sorted(name for name in SNAPSHOT_METHODS if name not in methods)
    assert not missing, f"Task7A may not remove host snapshot entrypoints: {missing}"


def test_task7a_keeps_t7_manufacturing_authority_on_host():
    methods = _host_methods()
    missing = sorted(name for name in T7_HOLD_METHODS if name not in methods)
    if not missing:
        return
    owner_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "gui_modules" / "application" / "fold_designer_adapter.py",
            ROOT / "gui_modules" / "application" / "manufacturing_adapter.py",
        )
    )
    unresolved = sorted(name for name in missing if f"def {name}" not in owner_source)
    assert not unresolved, f"Task7A HOLD authority missing current T7 owner: {unresolved}"
