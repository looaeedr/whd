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


def _module_function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"function not found: {function_name}")

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


def test_shared_finished_dimension_provider_is_the_2d_3d_authority():
    spec = importlib.util.find_spec("ae_engine.display_dimensions")
    assert spec is not None, (
        "R2: missing shared finished-dimension provider for 2D/3D"
    )
    module = importlib.import_module("ae_engine.display_dimensions")
    assert callable(getattr(module, "resolve_operator_finished_dimensions", None))
    assert callable(getattr(module, "folded_outside_envelope", None))

    bridge_src = _module_function_source(
        ROOT / "fold_designer_bridge.py", "_phase6_operator_finished_dimensions"
    )
    view_src = _class_method_source(
        ROOT / "phase6_final_scene_view.py",
        "Phase6FinalSceneView",
        "_resolved_finished_dimensions",
    )
    assert "resolve_operator_finished_dimensions" in bridge_src
    assert "box_body_height_from_corner_policies" not in bridge_src
    assert "resolve_operator_finished_dimensions" in view_src


def test_all_primary_2d_previews_consume_shared_finished_dimension_summary():
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
        if "_draw_phase6_finished_dimension_summary" not in src:
            missing.append(method)
    assert not missing, (
        "R2: primary 2D previews still bypass shared finished-dimension provider: "
        + ", ".join(missing)
    )


def test_family_switch_projection_does_not_keep_stale_feature_ids():
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene
    from ae_engine.sheetmetal_geometry import Vec2

    module = _engineering_module()

    old_scene = DrawingScene()
    old_scene.add(CirclePrimitive(
        Vec2(20.0, 20.0), 5.0, "CUTTING",
        source_type="baseline_hole", source_id="OLD:FAMILY:HOLE",
    ))
    new_scene = DrawingScene()
    new_scene.add(CirclePrimitive(
        Vec2(30.0, 30.0), 4.0, "CUTTING",
        source_type="baseline_hole", source_id="NEW:FAMILY:HOLE",
    ))

    old_projection = module.build_engineering_drawing_projection(
        SimpleNamespace(scene=old_scene, material=box(0.0, 0.0, 100.0, 60.0)),
        part_key="door",
    )
    new_projection = module.build_engineering_drawing_projection(
        SimpleNamespace(scene=new_scene, material=box(0.0, 0.0, 120.0, 70.0)),
        part_key="door",
    )

    assert {item.source_id for item in old_projection.annotation_plan.feature_callouts} == {
        "OLD:FAMILY:HOLE"
    }
    assert {item.source_id for item in new_projection.annotation_plan.feature_callouts} == {
        "NEW:FAMILY:HOLE"
    }
    assert all(
        item.source_id != "OLD:FAMILY:HOLE"
        for item in new_projection.annotation_plan.feature_callouts
    )


def test_folded_mesh_dimensions_override_snapshot_fallback():
    from ae_engine.display_dimensions import (
        folded_outside_envelope,
        resolve_operator_finished_dimensions,
    )

    triangles = (
        ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 60.0, 0.0)),
        ((0.0, 0.0, 0.0), (100.0, 60.0, 0.0), (0.0, 60.0, 0.0)),
    )
    expected, _bounds = folded_outside_envelope(triangles, 2.0)
    resolved = resolve_operator_finished_dimensions(
        "box_body",
        snapshot={"w": 999.0, "h": 888.0, "d": 777.0, "t": 2.0},
        triangles=triangles,
        thickness=2.0,
    )

    assert resolved == expected
    assert resolved != (999.0, 888.0, 777.0)


def test_shared_provider_preserves_box_body_corner_policy_fallback_dimensions():
    from ae_engine.corner_type_ui import (
        apply_box_assembly_type,
        new_manual_corner_pair_same_state,
        new_manual_corner_state,
        policy_from_corner_state,
    )
    from ae_engine.display_dimensions import resolve_operator_finished_dimensions
    from ae_engine.sheetmetal_geometry import CornerTypeId

    state = new_manual_corner_state(["head", "tail"])
    pairs = new_manual_corner_pair_same_state(["head", "tail"])
    apply_box_assembly_type(state, pairs, CornerTypeId.INSERT_OVERLAY)

    resolved = resolve_operator_finished_dimensions(
        "box_body",
        snapshot={"w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0},
        settings={"w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0},
        thickness=2.0,
        head_corner_policy=policy_from_corner_state(state["head"], fw=25.0),
        tail_corner_policy=policy_from_corner_state(state["tail"], fw=25.0),
    )

    assert resolved == (400.0, 596.0, 250.0)
