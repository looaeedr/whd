from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
INTERACTION = ROOT / "gui_modules" / "rendering" / "interaction.py"

ROOT_METHODS = {
    "_door_layout_cell_at_canvas_point",
    "on_door_canvas_press",
    "on_door_canvas_drag",
    "on_door_canvas_release",
    "on_door_canvas_double_click",
}

EXPECTED_FUNCTIONS = {
    "door_layout_cell_at_canvas_point",
    "on_door_canvas_press",
    "on_door_canvas_drag",
    "on_door_canvas_release",
    "on_door_canvas_double_click",
}


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


def test_task5_interaction_module_exists_with_explicit_functions():
    assert INTERACTION.is_file(), "T6 TASK5 RED: interaction.py missing"
    source = INTERACTION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(EXPECTED_FUNCTIONS - functions)
    assert not missing, f"T6 TASK5 RED: interaction functions missing: {missing}"


def test_task5_root_interaction_methods_are_thin_delegates():
    methods = _host_methods()
    oversized = []
    for name in sorted(ROOT_METHODS):
        node = methods[name]
        if _span(node) > 4:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK5 RED: root interaction methods are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task5_interaction_module_has_no_manufacturing_or_committed_state_authority():
    if not INTERACTION.is_file():
        return

    source = INTERACTION.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_tokens = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_single_door_part_spec",
        "_door_layout_part_spec",
        "host.surface_features =",
        "host.door_layout_columns =",
        "host.project_controller =",
        "host.workspace_controller =",
        "host.phase6_project =",
    )
    hits = [token for token in forbidden_tokens if token in source]
    assert not hits, f"interaction stole committed/manufacturing authority: {hits}"

    import_violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "gui":
                    import_violations.append(alias.name)
                if alias.name.startswith("compatibility.legacy_exports"):
                    import_violations.append(alias.name)
                if alias.name.startswith("ae_engine.manufacturing_api"):
                    import_violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "gui":
                import_violations.append(module)
            if module.startswith("compatibility.legacy_exports"):
                import_violations.append(module)
            if module.startswith("ae_engine.manufacturing_api"):
                import_violations.append(module)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))

    assert not import_violations, import_violations
