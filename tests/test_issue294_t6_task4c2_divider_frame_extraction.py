from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
APP = ROOT / "gui_modules" / "application" / "render_snapshots.py"
DOOR_VIEW = ROOT / "gui_modules" / "rendering" / "door_view.py"


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


def test_task4c2_door_view_exports_divider_frame_presenter():
    source = DOOR_VIEW.read_text(encoding="utf-8")
    assert "def draw_door_layout_dividers_and_frames_preview(" in source, (
        "T6 TASK4C2 RED: divider/frame presenter missing"
    )


def test_task4c2_root_divider_frame_entrypoint_is_thin():
    _source, methods = _host_methods()
    node = methods["_draw_door_layout_dividers_and_frames"]
    span = _span(node)
    assert span <= 8, (
        f"T6 TASK4C2 RED: _draw_door_layout_dividers_and_frames span={span} > 8"
    )


def test_task4c2_application_keeps_assembly_derivation_and_placement_orchestration():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    body = ast.get_source_segment(
        source, functions["door_layout_divider_frame_snapshot"]
    ) or ""
    for token in (
        "_compose_phase6_project_snapshot_from_main_gui",
        "derive_box_body_dividers",
        "resolve_assembly_placement",
        "derive_inner_door_frame_sets",
        "inner_door_frame_stable_id",
    ):
        assert token in body, f"snapshot builder missing authority token: {token}"
def test_task4c2_presenter_is_placement_consumer_only():
    source = DOOR_VIEW.read_text(encoding="utf-8")
    forbidden = (
        "derive_box_body_dividers",
        "resolve_assembly_placement",
        "derive_inner_door_frame_sets",
        "inner_door_frame_stable_id",
        "_compose_phase6_project_snapshot_from_main_gui",
        "cabinet_family_policy",
        "assembly_placement",
        "door_dividers",
        "inner_door_frames",
    )
    hits = [token for token in forbidden if token in source]
    assert not hits, f"presenter stole derivation/placement authority: {hits}"

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))
