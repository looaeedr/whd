from pathlib import Path
import ast
import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"


def _function_source(name):
    text = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1: node.end_lineno])
    raise AssertionError(f"missing function: {name}")


def test_3d_render_path_consumes_scene_callback_only():
    src = _function_source("_phase6_final_scene_view_request")
    assert "_phase6_query_final_render_data" in src
    forbidden = (
        "_phase6_cutting_polygon_from_scene",
        "_phase6_cutting_contours_from_scene",
        "_phase6_cutting_polygon_from_scene",
        "_phase6_current_cutting_scene",
        "_phase6_current_baseline_cutting_scene",
        "_phase6_material_with_baseline_holes",
        "_phase6_current_fold_exemptions",
        "_phase6_corner_policy_for",
        "get_stretched_",
        "build_unknown_",
        "build_door_result",
    )
    for token in forbidden:
        assert token not in src


def test_bridge_has_no_second_manufacturing_scene_builder():
    text = BRIDGE.read_text(encoding="utf-8")
    # These functions were the accidental second manufacturing engine in 3D.
    for name in (
        "_phase6_current_cutting_scene",
        "_phase6_current_baseline_cutting_scene",
        "_phase6_align_baseline_scene_to_current",
        "_phase6_material_with_baseline_holes",
        "_phase6_current_fold_exemptions",
        "_phase6_retained_fold_exemptions",
    ):
        assert f"def {name}(" not in text


def test_final_render_callback_returns_exact_manufacturing_object():
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene

    from types import SimpleNamespace
    expected = SimpleNamespace(scene=DrawingScene(), material=object())
    calls = []

    from phase6_designer_workspace import Phase6DesignerWorkspace
    class Dummy:
        designer_workspace = Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "door"], "active_part": "door"
        })
        _scene_query_callback = staticmethod(lambda part, payload: calls.append((part, payload)) or expected)
        _phase6_input_snapshot = {}
        _settings_values = {}
        _phase6_box_whd = {}
        _phase6_corner_state = {}
        _phase6_endcap_fw_state = {}

    got = bridge._phase6_query_final_render_data(Dummy())
    assert got is expected
    assert calls and calls[0][0] == "door"


def test_retain_ownership_is_derived_from_final_material_not_corner_policy():
    import fold_designer_bridge as bridge
    from shapely.geometry import Polygon
    from ae_engine.sheetmetal_part_adapters import build_door_result

    result = build_door_result(
        w=500, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
    )
    material = Polygon([(p.x, p.y) for p in result.outline])
    xb = (0.0, 19.0, 450.0, 465.0)
    yb = (0.0, 15.0, 546.0, 561.0)
    ex = bridge._phase6_fold_ownership_exemptions(material, xb, yb)
    axes = [axis for axis, _ in ex]
    # Factory C02 retains width at all four corners => horizontal flange owns
    # each tongue, so only the perpendicular X fold is suppressed.
    assert axes.count("x") == 4
    assert "y" not in axes


def test_manufacturing_api_exposes_render_geometry_boundary():
    from ae_engine import manufacturing_api
    assert callable(getattr(manufacturing_api, "build_part_render_data", None))


def test_render_geometry_material_is_owned_by_manufacturing_boundary(monkeypatch):
    from ae_engine import manufacturing_api
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import Point

    scene = DrawingScene()
    # First CUTTING polyline is the authoritative structural material.
    scene.add_polyline([(0,0),(100,0),(100,60),(0,60)], layer='CUTTING', closed=True)
    # Legacy mapped structural outline may also exist in the final drawing scene;
    # it must not become a giant hole.
    scene.add_polyline([(0,0),(100,0),(100,58),(98,60),(0,60)], layer='CUTTING', closed=True)
    scene.add_circle((25,30), 5, layer='CUTTING')
    scene.add_circle((75,30), 6.5, layer='MARKING')
    monkeypatch.setattr(manufacturing_api, 'build_part_scene', lambda spec, context=None: scene)

    data = manufacturing_api.build_part_render_data(
        DoorPartSpec(width=120, height=80, thickness=2, frame_width=25)
    )

    assert data.scene is scene
    assert data.material.contains(Point(75,30))
    assert not data.material.contains(Point(25,30))
    assert data.material.area > 5000


def _class_method_source(path, class_name, method_name):
    text = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return "\n".join(lines[item.lineno - 1:item.end_lineno])
    raise AssertionError(f"missing method: {class_name}.{method_name}")


def test_gui_3d_callback_does_not_construct_part_specs_directly():
    gui_path = ROOT / "gui.py"
    src = _class_method_source(gui_path, "BoxCalculatorGUI", "_query_fold_designer_render_data")
    assert "_fold_designer_part_spec_from_payload" in src
    assert "_authoritative_render_data" in src
    for ctor in (
        "DoorPartSpec(", "BoxBodyPartSpec(", "EndCapPartSpec(",
        "BasePlatePartSpec(", "IndicatorBoxPartSpec(",
    ):
        assert ctor not in src


def test_gui_authoritative_render_data_cache_reuses_exact_object(monkeypatch):
    import gui
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from types import SimpleNamespace

    app = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    calls = []
    expected = SimpleNamespace(scene=object(), material=object())
    monkeypatch.setattr(
        gui.manufacturing_api,
        "build_part_render_data",
        lambda spec, context=None: calls.append((spec, context)) or expected,
    )
    spec = DoorPartSpec(width=500, height=600, thickness=2, frame_width=25)
    ctx = ManufacturingContext(draw_stock=False)

    first = app._authoritative_render_data(spec, ctx)
    second = app._authoritative_render_data(spec, ctx)

    assert first is expected
    assert second is expected
    assert len(calls) == 1


def test_committed_and_fold_draft_door_use_identical_part_spec_mapping():
    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    class BoolVar:
        def get(self):
            return True

    class ModelVar:
        def get(self):
            return "金庫型"

    app = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    feature = CircleFeature(12.0, FeatureAnchor.PANEL_CENTER, Vec2(5.0, -7.0))
    app.surface_features = {"door": [feature]}
    app.door_indicator_offset_x = 11.0
    app.door_indicator_offset_y = -9.0
    app.is_box_dist_var = BoolVar()
    app.baseline_var = ModelVar()
    app._baseline_source_model = lambda: "金庫型"

    val = {
        "w": 900.0, "h": 1100.0, "t": 2.0, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 4.0,
        "door_fold_l": 19.0, "door_fold_r": 21.0,
        "door_fold_t": 22.0, "door_fold_b": 23.0,
    }
    committed = app._single_door_part_spec(val, door_indicator=(2, 3))
    draft, _ctx = app._fold_designer_part_spec_from_payload("door", {
        **val,
        "model": "金庫型",
        "features": [feature],
        "door_indicator_groups": [2, 3],
        "door_indicator_offset": (11.0, -9.0),
        "use_box_distance": True,
    })

    assert draft == committed


def test_single_door_2d_draw_consumes_authoritative_final_scene_only():
    gui_path = ROOT / "gui.py"
    src = _class_method_source(gui_path, "BoxCalculatorGUI", "draw_door")
    assert "_single_door_part_spec" in src
    assert "_authoritative_render_data" in src
    assert "render_drawing_scene" in src
    for forbidden in (
        "get_stretched_door_data",
        "render_structural_result",
        "render_secondary_scene",
        "render_surface_user_features",
    ):
        assert forbidden not in src


def test_2d_and_3d_equal_door_state_share_exact_render_data_object(monkeypatch):
    import gui
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.sheetmetal_drawing import DrawingScene
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from shapely.geometry import box
    from types import SimpleNamespace

    class FalseVar:
        def get(self):
            return False

    class ModelVar:
        def get(self):
            return "金庫型"

    app = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    feature = CircleFeature(10.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0))
    app.surface_features = {"door": [feature]}
    app.door_indicator_offset_x = 0.0
    app.door_indicator_offset_y = 0.0
    app.is_box_dist_var = FalseVar()
    app.baseline_var = ModelVar()
    app._baseline_source_model = lambda: "金庫型"
    app._authoritative_part_render_cache = {}

    scene = DrawingScene()
    expected = SimpleNamespace(scene=scene, material=box(0, 0, 100, 80))
    calls = []
    monkeypatch.setattr(
        gui.manufacturing_api,
        "build_part_render_data",
        lambda spec, context=None: calls.append((spec, context)) or expected,
    )

    val = {
        "w": 900.0, "h": 1100.0, "t": 2.0, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 19.0,
        "door_fold_t": 19.0, "door_fold_b": 19.0,
    }
    spec2d = app._single_door_part_spec(val)
    data2d = app._authoritative_render_data(spec2d, ManufacturingContext(draw_stock=False))
    data3d = app._query_fold_designer_render_data("door", {
        **val, "model": "金庫型", "features": [feature],
        "door_indicator_offset": (0.0, 0.0), "use_box_distance": False,
    })

    assert data3d is data2d is expected
    assert len(calls) == 1


def test_fold_draft_adapter_reuses_canonical_part_spec_helpers():
    gui_path = ROOT / "gui.py"
    src = _class_method_source(gui_path, "BoxCalculatorGUI", "_fold_designer_part_spec_from_payload")
    for ctor in (
        "DoorPartSpec(", "BoxBodyPartSpec(", "EndCapPartSpec(",
        "BasePlatePartSpec(", "IndicatorBoxPartSpec(",
    ):
        assert ctor not in src
    for helper in (
        "_box_body_part_spec_from_values",
        "_end_cap_part_spec_from_values",
        "_door_part_spec_from_values",
        "_base_plate_part_spec_from_values",
        "_indicator_box_part_spec_from_values",
        "_indicator_door_part_spec_from_values",
    ):
        assert helper in src


def test_all_primary_2d_part_previews_use_authoritative_render_data():
    gui_path = ROOT / "gui.py"
    for method in (
        "draw_box_body", "draw_end_cap", "draw_door", "draw_base_plate",
        "draw_indicator_box", "draw_indicator_door",
    ):
        src = _class_method_source(gui_path, "BoxCalculatorGUI", method)
        assert "_authoritative_render_data" in src, method


def test_baseline_reload_invalidates_authoritative_render_cache():
    import gui
    app = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    app._authoritative_part_render_cache = {("old", "ctx"): object()}
    app._door_layout_baseline_cache = {"old": object()}
    app._box_body_baseline_face_cache = {"old": object()}
    app._reload_current_baseline_features()
    assert app._authoritative_part_render_cache == {}


def test_3d_view_never_calls_legacy_geometry_renderer(monkeypatch):
    """Phase6 3D must render Final Part Geometry directly, not draw old geometry first."""
    import fold_designer_bridge as bridge
    from types import SimpleNamespace

    calls = []

    class Canvas:
        def __init__(self):
            self.draw = lambda *a, **k: calls.append("draw")
        def mpl_connect(self, *a, **k):
            return 123

    class Axis:
        elev = 30
        azim = -45
        transAxes = object()
        def clear(self): calls.append("clear")
        def view_init(self, **kwargs): pass
        def text2D(self, *a, **k): pass

    renderer = SimpleNamespace(
        render=lambda: calls.append("legacy-render"),
        canvas=Canvas(),
        ax3d=Axis(),
        ax2d=None,
    )
    app = SimpleNamespace(renderer=renderer, state=SimpleNamespace(holes={}), on_3d_scroll=lambda event: None)

    monkeypatch.setattr(bridge, "_phase6_final_scene_view_request", lambda self: object())
    monkeypatch.setattr(bridge.Phase6FinalSceneView, "render", lambda self, request: calls.append("final-material") or [])
    monkeypatch.setattr(bridge, "_phase6_update_unfolded_size_label", lambda self: None)

    bridge._phase6_install_renderer_view(app)
    app.renderer.render()

    assert "final-material" in calls
    assert "legacy-render" not in calls


def test_true_cutting_mesh_uses_editor_profiles_directly_without_rederiving_from_scene(monkeypatch):
    """Bridge adapts the editor profiles directly; View receives no re-derived profile."""
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box
    from types import SimpleNamespace

    x_profile = [
        {"len": 20.0, "angle": 90.0},
        {"len": 160.0, "angle": -90.0},
        {"len": 20.0},
    ]
    y_profile = [
        {"len": 30.0, "angle": 90.0},
        {"len": 240.0, "angle": -90.0},
        {"len": 30.0},
    ]
    material = box(0.0, 0.0, 200.0, 300.0)
    scene = DrawingScene()
    scene.add_line((20, 0), (20, 300), layer="BEND")
    render_data = SimpleNamespace(scene=scene, material=material, fold_guides=())
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "door"], "active_part": "door"
    })
    app = SimpleNamespace(
        designer_workspace=workspace,
        state=SimpleNamespace(profiles={"X": x_profile, "Y": y_profile}, alpha_bend=0.85),
        _phase6_input_snapshot={}, _settings_values={}, _phase6_corner_state={},
    )
    monkeypatch.setattr(bridge, "_phase6_query_final_render_data", lambda self: render_data)

    request = bridge._phase6_final_scene_view_request(app)

    assert request.render_data is render_data
    assert list(request.x_profile) == x_profile
    assert list(request.y_profile) == y_profile


def test_opening_phase6_designer_does_not_execute_legacy_renderer(monkeypatch):
    """Entering 3D must not spend time drawing the obsolete prototype geometry."""
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui
    import fold_designer_original as original

    calls = []
    original_render = original.Renderer.render

    def counted_legacy_render(self):
        calls.append("legacy")
        return original_render(self)

    monkeypatch.setattr(original.Renderer, "render", counted_legacy_render)
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        assert calls == []
        app.open_original_fold_designer()
        assert calls == []
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_final_material_closes_visually_closed_cutting_gap_for_handle_profile():
    """2D-visible LINE/ARC-style handle contours with tiny endpoint gaps must become real holes."""
    from ae_engine.manufacturing_api import material_polygon_from_final_scene
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import Point

    scene = DrawingScene()
    scene.add_polyline([(0, 0), (200, 0), (200, 120), (0, 120)], layer="CUTTING", closed=True)
    # Typical exploded/flattened handle outline: visually closed in 2D but the
    # final segment misses the first endpoint by 0.05 mm after DXF arc flattening.
    scene.add_line((70, 50), (130, 50), layer="CUTTING")
    scene.add_line((130, 50), (130, 70), layer="CUTTING")
    scene.add_line((130, 70), (70, 70), layer="CUTTING")
    scene.add_line((70, 70), (70, 50.05), layer="CUTTING")

    material = material_polygon_from_final_scene(scene)

    assert not material.contains(Point(100, 60))


def test_gui_export_reuses_cached_final_scene_without_second_manufacturing_build(monkeypatch, tmp_path):
    import gui
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box
    from types import SimpleNamespace

    app = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    app._authoritative_part_render_cache = {}
    scene = DrawingScene()
    render_data = SimpleNamespace(scene=scene, material=box(0, 0, 100, 80), fold_guides=())
    builds = []
    saves = []
    monkeypatch.setattr(
        gui.manufacturing_api,
        "build_part_render_data",
        lambda spec, context=None: builds.append((spec, context)) or render_data,
    )
    monkeypatch.setattr(
        gui.manufacturing_api,
        "save_part_render_data_dxf",
        lambda data, path, overwrite=False: saves.append((data, str(path), overwrite)),
        raising=False,
    )

    spec = DoorPartSpec(width=500, height=600, thickness=2, frame_width=25)
    ctx = ManufacturingContext(draw_stock=False, overwrite=True)

    preview = app._authoritative_render_data(spec, ctx)
    app._export_authoritative_part(spec, tmp_path / "door.dxf", ctx)

    assert preview is render_data
    assert len(builds) == 1
    assert saves == [(render_data, str(tmp_path / "door.dxf"), True)]


def test_all_gui_dxf_export_paths_serialize_authoritative_render_data_not_generate_again():
    gui_path = ROOT / "gui.py"
    for method in (
        "export_selected_dxf",
        "export_multi_door_layout_dxfs",
        "export_multi_door_indicator_box_parts",
    ):
        src = _class_method_source(gui_path, "BoxCalculatorGUI", method)
        assert "manufacturing_api.generate_part" not in src, method
        assert "_export_authoritative_part" in src, method
