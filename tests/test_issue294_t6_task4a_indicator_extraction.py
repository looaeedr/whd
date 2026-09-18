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


def test_task4a_door_view_module_exists():
    assert DOOR_VIEW.is_file(), "T6 TASK4A RED: door_view.py missing"


def test_task4a_indicator_entrypoints_are_thin_delegates():
    _source, methods = _host_methods()
    oversized = []
    for name in ("draw_indicator_box", "draw_indicator_door"):
        node = methods.get(name)
        if node is None:
            continue
        if _span(node) > 8:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK4A RED: indicator root implementations are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task4a_application_snapshot_helpers_call_host_authority():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    box_src = ast.get_source_segment(source, functions["indicator_box_render_snapshot"]) or ""
    door_src = ast.get_source_segment(source, functions["indicator_door_render_snapshot"]) or ""

    assert "_indicator_box_part_spec" in box_src
    assert "_authoritative_render_data" in box_src
    assert "_manufacturing_context" in box_src

    assert "_indicator_door_part_spec_from_values" in door_src
    assert "_authoritative_render_data" in door_src
    assert "door_finished_face_size" in door_src
def test_task4a_renderer_is_presentation_only():
    if not DOOR_VIEW.is_file():
        return

    source = DOOR_VIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_tokens = (
        "_authoritative_render_data",
        "_indicator_box_part_spec",
        "_indicator_door_part_spec_from_values",
        "_manufacturing_context",
        "door_finished_face_size",
        "manufacturing_api",
        "resolve_assembly_placement",
        "derive_box_body_dividers",
        "inner_door_frame",
    )
    hits = [token for token in forbidden_tokens if token in source]
    assert not hits, f"renderer stole authority/acquisition: {hits}"

    import_violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "gui" or alias.name.startswith("compatibility.legacy_exports"):
                    import_violations.append(alias.name)
                if alias.name.startswith("ae_engine.manufacturing_api"):
                    import_violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "gui" or module.startswith("compatibility.legacy_exports"):
                import_violations.append(module)
            if module.startswith("ae_engine.manufacturing_api"):
                import_violations.append(module)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))

    assert not import_violations, import_violations
