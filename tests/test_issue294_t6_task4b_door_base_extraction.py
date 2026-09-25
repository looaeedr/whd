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


def test_task4b_door_view_exports_single_door_and_base_plate_presenters():
    assert DOOR_VIEW.is_file()
    source = DOOR_VIEW.read_text(encoding="utf-8")
    missing = [
        name
        for name in ("draw_single_door_preview", "draw_base_plate_preview")
        if f"def {name}(" not in source
    ]
    assert not missing, f"T6 TASK4B RED: presenters missing: {missing}"


def test_task4b_single_door_and_base_plate_entrypoints_are_thin():
    _source, methods = _host_methods()
    oversized = []
    for name in ("draw_door", "draw_base_plate"):
        node = methods.get(name)
        if node is None:
            continue
        if _span(node) > 8:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK4B RED: root implementations are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task4b_application_snapshot_helpers_call_host_authority():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    door_src = ast.get_source_segment(source, functions["single_door_render_snapshot"]) or ""
    base_src = ast.get_source_segment(source, functions["base_plate_render_snapshot"]) or ""

    for token in (
        "_single_door_part_spec",
        "_authoritative_render_data",
        "_manufacturing_context",
        "door_finished_face_size",
    ):
        assert token in door_src
    for token in (
        "_base_plate_part_spec",
        "_authoritative_render_data",
        "_manufacturing_context",
    ):
        assert token in base_src
def test_task4b_door_view_stays_presentation_only():
    source = DOOR_VIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = (
        "manufacturing_api",
        "_single_door_part_spec",
        "_base_plate_part_spec",
        "_authoritative_render_data",
        "_manufacturing_context",
        "door_finished_face_size",
        "indicator_box_opening_size",
        "measure_door_indicator_position",
        "resolve_door_indicator_layout",
        "door_indicator_offset_for_position",
    )
    hits = [token for token in forbidden if token in source]
    assert not hits, f"renderer stole authority/acquisition: {hits}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "gui"
                assert not alias.name.startswith("compatibility.legacy_exports")
                assert not alias.name.startswith("ae_engine.manufacturing_api")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module != "gui"
            assert not module.startswith("compatibility.legacy_exports")
            assert not module.startswith("ae_engine.manufacturing_api")

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))
