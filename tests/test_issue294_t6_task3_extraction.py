from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
RENDERING = ROOT / "gui_modules" / "rendering"

EXPECTED_TASK3_MODULES = {
    "__init__.py",
    "canvas_2d.py",
    "overlays.py",
    "transforms.py",
}

TASK3_ROOT_SYMBOLS = {
    "_YMirroredPreviewTransform",
    "_draw_phase6_annotation_projection",
    "_draw_phase6_corner_dimension_overlay",
    "_phase6_2d_material_viewport",
    "_rects_overlap",
    "feature_surface_from_drawing_scene",
    "layout_reference_overlay_rects",
    "render_resolved_features",
    "render_secondary_scene",
    "render_structural_result",
    "render_surface_user_features",
}


def _span(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def test_task3_rendering_modules_exist():
    assert RENDERING.is_dir(), "T6 TASK3 RED: rendering package missing"
    present = {path.name for path in RENDERING.glob("*.py")}
    missing = sorted(EXPECTED_TASK3_MODULES - present)
    assert not missing, f"T6 TASK3 RED: missing modules: {missing}"


def test_task3_root_symbols_are_aliases_or_thin_delegates():
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    oversized = []
    for name in sorted(TASK3_ROOT_SYMBOLS):
        node = top.get(name)
        if node is not None and _span(node) > 8:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK3 RED: root still owns Task3 implementation: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task3_root_wrappers_preserve_existing_authority_injection_seams():
    source = GUI.read_text(encoding="utf-8")
    required = (
        "scene_renderer=render_drawing_scene",
        "resolver=resolve_surface_features",
        "feature_renderer=render_resolved_features",
        "ae_module=ae",
        "projection_builder=build_engineering_drawing_projection",
        "text_builder=render_data_corner_dimension_text",
        "transform_type=CanvasTransform",
    )
    missing = [token for token in required if token not in source]
    assert not missing, f"T6 TASK3 RED: missing authority injection seams: {missing}"


def test_task3_rendering_import_direction_and_authority_contract():
    if not RENDERING.is_dir():
        return

    violations = []
    combined = []
    for path in sorted(RENDERING.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        combined.append(source)
        tree = ast.parse(source)

        if len(source.splitlines()) > 1_500:
            violations.append(f"{path.name}: module >1500 LOC")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "gui":
                        violations.append(f"{path.name}: imports gui")
                    if alias.name.startswith("compatibility.legacy_exports"):
                        violations.append(f"{path.name}: imports legacy compatibility")
                    if alias.name.startswith("ae_engine.manufacturing_api"):
                        violations.append(f"{path.name}: imports manufacturing_api")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "gui":
                    violations.append(f"{path.name}: imports gui")
                if module.startswith("compatibility.legacy_exports"):
                    violations.append(f"{path.name}: imports legacy compatibility")
                if module.startswith("ae_engine.manufacturing_api"):
                    violations.append(f"{path.name}: imports manufacturing_api")

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _span(node) > 150:
                violations.append(f"{path.name}:{node.name} >150 LOC")
            if isinstance(node, ast.ClassDef) and _span(node) > 800:
                violations.append(f"{path.name}:{node.name} >800 LOC")

    joined = "\n".join(combined)
    for forbidden in (
        "def _authoritative_render_data",
        "def _manufacturing_context",
        "def _box_body_part_spec",
        "def _end_cap_part_spec",
        "def _door_layout_part_spec",
        "def _base_plate_part_spec",
    ):
        if forbidden in joined:
            violations.append(f"forbidden authority definition: {forbidden}")

    canvas = (RENDERING / "canvas_2d.py")
    if canvas.exists():
        canvas_source = canvas.read_text(encoding="utf-8")
        if "resolver=resolve_surface_features" not in canvas_source:
            violations.append("canvas_2d.py: missing injected existing feature resolver")
        if "resolved = resolver(" not in canvas_source:
            violations.append("canvas_2d.py: bypasses injected feature resolver")
        if "ae_module=ae" not in canvas_source:
            violations.append("canvas_2d.py: missing injected AE surface authority")
        if "return ae_module.feature_surface_from_drawing_scene(" not in canvas_source:
            violations.append("canvas_2d.py: bypasses AE surface authority")

    assert not violations, "\n".join(violations)
