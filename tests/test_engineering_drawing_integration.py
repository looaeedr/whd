# -*- coding: utf-8 -*-
import ast
import importlib
import importlib.util
import inspect
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _engineering_module():
    spec = importlib.util.find_spec("ae_engine.engineering_drawing")
    assert spec is not None, (
        "R1: missing shared Engineering Drawing projection seam; "
        "2D and Engineering Drawing cannot consume one AnnotationPlan source"
    )
    return importlib.import_module("ae_engine.engineering_drawing")


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError(f"method not found: {class_name}.{method_name}")


def test_shared_engineering_drawing_projection_public_seam_exists():
    module = _engineering_module()
    builder = getattr(module, "build_engineering_drawing_projection", None)
    assert callable(builder), (
        "R1: missing build_engineering_drawing_projection public seam"
    )


def test_all_primary_2d_previews_delegate_annotation_projection():
    gui_path = ROOT / "gui.py"
    methods = (
        "draw_box_body",
        "draw_end_cap",
        "draw_door",
        "draw_base_plate",
        "draw_indicator_box",
        "draw_indicator_door",
    )
    missing = []
    for method in methods:
        src = _class_method_source(gui_path, "BoxCalculatorGUI", method)
        if "_draw_phase6_annotation_projection" not in src:
            missing.append(method)
    assert not missing, (
        "R1: primary 2D previews still bypass shared AnnotationPlan projection: "
        + ", ".join(missing)
    )


def test_projection_is_annotation_only_and_manufacturing_scene_is_immutable():
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, TextPrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    scene = DrawingScene()
    scene.add(LinePrimitive(Vec2(0.0, 0.0), Vec2(100.0, 0.0), "CUTTING"))
    render_data = SimpleNamespace(scene=scene, material=box(0.0, 0.0, 100.0, 60.0))
    before = tuple(scene.primitives)

    projection = _engineering_module().build_engineering_drawing_projection(
        render_data, part_key="probe"
    )

    assert tuple(scene.primitives) == before
    assert projection.annotation_plan is not None
    assert projection.primitives
    assert all(
        isinstance(item, (LinePrimitive, TextPrimitive))
        and item.layer in {"DIMENSION", "TEXT"}
        for item in projection.primitives
    )


def test_production_dxf_serializer_stays_on_original_manufacturing_scene():
    from ae_engine import manufacturing_api

    src = inspect.getsource(manufacturing_api.save_part_render_data_dxf)
    assert "build_engineering_drawing_projection" not in src
    assert "render_data.scene" in src
    assert "_save_scene_dxf" in src
