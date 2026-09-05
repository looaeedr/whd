# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box


def _flat_profile(length):
    return ({"len": float(length), "core": True},)


class Axis:
    def __init__(self):
        self.collections = []
        self.lines = []
        self.transAxes = object()

    def add_collection3d(self, obj):
        self.collections.append(obj)

    def plot(self, *args, **kwargs):
        return None

    def text2D(self, *args, **kwargs):
        return None

    def set_xlim3d(self, *args):
        self.xlim = args

    def set_ylim3d(self, *args):
        self.ylim = args

    def set_zlim3d(self, *args):
        self.zlim = args

    def set_box_aspect(self, *args, **kwargs):
        return None


def test_final_scene_view_can_render_multiple_authoritative_parts_as_one_assembly():
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene

    door_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40), fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart(
                part_key="door",
                render_data=door_data,
                x_profile=_flat_profile(100),
                y_profile=_flat_profile(80),
                placement="front",
            ),
            view.AssemblyScenePart(
                part_key="head",
                render_data=head_data,
                x_profile=_flat_profile(100),
                y_profile=_flat_profile(40),
                placement="top",
            ),
        ),
    )
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=Axis()))
    request = view.FinalSceneViewRequest(
        render_data=render_data,
        x_profile=(),
        y_profile=(),
        part_key="assembly",
        alpha_bend=0.85,
        finished_dimensions=(100.0, 80.0, 40.0),
        thickness=2.0,
    )

    triangles = scene_view.render(request)

    assert triangles
    assert scene_view.last_cutting_mesh == triangles
    assert scene_view.last_cutting_material == (door_data.material, head_data.material)
    assert len(scene_view.renderer.ax3d.collections) >= 2


def test_bridge_assembly_display_request_includes_all_available_sheet_parts(monkeypatch):
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    calls = []

    def callback(part_key, payload):
        calls.append((part_key, payload))
        return SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())

    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
            "active_part": "door",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
                "door": {"X": flat_x, "Y": flat_y},
                "base_plate": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(
            profiles={"X": flat_x, "Y": flat_y},
            profiles_vault={"箱身": flat_x},
            alpha_bend=0.85,
        ),
        _scene_query_callback=callback,
        _phase6_3d_display_mode="assembly",
        _phase6_input_snapshot={},
        _settings_values={},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    request = bridge._phase6_final_scene_view_request(app)

    assert request.part_key == "assembly"
    assert [part.part_key for part in request.render_data.assembly_parts] == [
        "box_body", "head", "tail", "door", "base_plate"
    ]
    # Raw parts are queried first; Head/Tail are queried once more to replay
    # the authoritative CERTIFIED relief into canonical render data.
    assert [part_key for part_key, _payload in calls] == [
        "box_body", "head", "tail", "door", "base_plate", "head", "tail"
    ]


def test_phase6_assembly_placement_delegates_to_shared_engine(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view

    calls = []

    def fake_place(triangles, placement, dimensions, offset):
        calls.append((triangles, placement, dimensions, offset))
        return (((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)),)

    monkeypatch.setattr(assembly_geometry, "place_assembly_triangles", fake_place)
    local = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)

    placed = view._phase6_place_assembly_triangles(
        local,
        "top",
        (100.0, 80.0, 40.0),
        (1.0, 2.0, 3.0),
    )

    assert placed == (((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)),)
    assert calls == [(local, "top", (100.0, 80.0, 40.0), (1.0, 2.0, 3.0))]



def test_real_tk_part_selector_starts_in_assembly_and_switches_to_single_part():
    import tkinter as tk

    import pytest

    from fold_designer_bridge import Phase6FoldDesignerApp

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless fallback
        pytest.skip(f"Tk unavailable: {exc}")
    try:
        app = Phase6FoldDesignerApp(root, {
            "w": 500,
            "h": 600,
            "d": 200,
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
            "settings": {"t": 2.0, "fw": 24.0},
        })
        root.update_idletasks()

        assert app.part_choice_menu.entrycget(0, "label") == "組合體"
        assert app.part_var.get() == "組合體"
        assert app._phase6_3d_display_mode == "assembly"

        app.activate_part("box_body")
        root.update_idletasks()
        assert app.part_var.get() == "箱身"
        assert app._phase6_3d_display_mode == "single"
    finally:
        root.destroy()


def test_real_tk_menu_can_switch_from_assembly_to_boxbody_after_radiobutton_sets_label_first():
    import tkinter as tk

    import pytest

    from fold_designer_bridge import Phase6FoldDesignerApp

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless fallback
        pytest.skip(f"Tk unavailable: {exc}")
    try:
        app = Phase6FoldDesignerApp(root, {
            "w": 500,
            "h": 600,
            "d": 200,
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
            "settings": {"t": 2.0, "fw": 24.0},
        })
        root.update_idletasks()
        assert app._phase6_3d_display_mode == "assembly"
        assert app.part_var.get() == "組合體"

        # Tk Menu radiobutton changes the StringVar BEFORE invoking the command.
        # Reproduce the real user path instead of calling activate_part directly
        # while the variable still says 組合體.
        app.part_var.set("箱身")
        app.activate_part("box_body")
        root.update_idletasks()

        assert app._phase6_3d_display_mode == "single"
        assert app.part_var.get() == "箱身"
        assert app.fold_editor_host.winfo_manager() != ""
    finally:
        root.destroy()


def test_final_scene_assembly_uses_box_body_world_mesh_as_head_tail_mating_datum(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene

    body_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40), fold_guides=())
    tail_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 30), fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body"),
            view.AssemblyScenePart("head", head_data, _flat_profile(100), _flat_profile(40), "top"),
            view.AssemblyScenePart("tail", tail_data, _flat_profile(100), _flat_profile(30), "bottom"),
        ),
    )
    local_mesh = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    body_world = (((-1.0, -40.0, 0.0), (1.0, -40.0, 0.0), (1.0, 40.0, 0.0)),)
    head_world = (((10.0, 40.0, 1.0), (11.0, 40.0, 1.0), (10.0, 35.0, -1.0)),)
    tail_world = (((20.0, -40.0, 1.0), (19.0, -40.0, 1.0), (20.0, -45.0, -1.0)),)
    mating_calls = []

    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", lambda *args, **kwargs: local_mesh)

    def fake_regular_place(triangles, placement, dimensions, offset):
        if placement == "box_body":
            return body_world
        return (((999.0, 999.0, 999.0),) * 3,)

    monkeypatch.setattr(view, "_phase6_place_assembly_triangles", fake_regular_place)

    def fake_mate(
        triangles, placement, body_triangles, offset=(0.0, 0.0, 0.0), sheet_thickness=0.0
    ):
        mating_calls.append((placement, body_triangles, offset, float(sheet_thickness)))
        return head_world if placement == "top" else tail_world

    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", fake_mate)
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", lambda triangles, thickness: tuple(triangles))

    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=Axis()))
    request = view.FinalSceneViewRequest(
        render_data=render_data,
        x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    )

    triangles = scene_view.render(request)

    assert [call[0] for call in mating_calls] == ["top", "bottom"]
    assert all(call[1] == body_world for call in mating_calls)
    assert all(call[3] == 2.0 for call in mating_calls)
    assert head_world[0] in triangles
    assert tail_world[0] in triangles
    assert all(point != (999.0, 999.0, 999.0) for tri in triangles for point in tri)


def test_assembly_view_renders_head_tail_as_physical_sheet_and_offsets_mating_midplane(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene

    body_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40), fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body"),
            view.AssemblyScenePart("head", head_data, _flat_profile(100), _flat_profile(40), "top"),
        ),
    )
    local_mesh = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    body_world = (((-1.0, -40.0, 0.0), (1.0, -40.0, 0.0), (1.0, 40.0, 0.0)),)
    head_surface = (((10.0, 41.0, 1.0), (11.0, 41.0, 1.0), (10.0, 36.0, -1.0)),)
    head_solid = (
        ((10.0, 40.0, 1.0), (11.0, 40.0, 1.0), (10.0, 36.0, -1.0)),
        ((10.0, 42.0, 1.0), (10.0, 38.0, -1.0), (11.0, 42.0, 1.0)),
    )
    calls = {"mate": [], "thicken": []}

    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", lambda *args, **kwargs: local_mesh)
    monkeypatch.setattr(
        view,
        "_phase6_place_assembly_triangles",
        lambda triangles, placement, dimensions, offset: body_world if placement == "box_body" else triangles,
    )

    def fake_mate(triangles, placement, body_triangles, offset=(0.0, 0.0, 0.0), sheet_thickness=0.0):
        calls["mate"].append((placement, body_triangles, float(sheet_thickness)))
        return head_surface

    def fake_thicken(triangles, thickness, **kwargs):
        calls["thicken"].append((triangles, float(thickness)))
        return head_solid

    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", fake_mate)
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", fake_thicken)

    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=Axis()))
    request = view.FinalSceneViewRequest(
        render_data=render_data,
        x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    )

    triangles = scene_view.render(request)

    assert calls["mate"] == [("top", body_world, 2.0)]
    assert calls["thicken"] == [(head_surface, 2.0)]
    assert head_solid[0] in triangles and head_solid[1] in triangles


def test_assembly_fixed_relief_diagnostic_collides_only_restored_delta_not_whole_endcap(monkeypatch):
    import pytest
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box

    body_material = box(0, 0, 100, 80)
    head_material = box(0, 0, 100, 40).difference(box(0, 0, 12, 10))
    body_data = SimpleNamespace(scene=DrawingScene(), material=body_material, fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=head_material, fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body"),
            view.AssemblyScenePart("head", head_data, _flat_profile(100), _flat_profile(40), "top"),
        ),
        show_interference=True,
        ignore_fixed_corner_relief=True,
    )

    folded_areas = []
    def fake_fold(material, *args, **kwargs):
        area = round(float(material.area), 6)
        folded_areas.append(area)
        marker = area / 1000.0
        return (((marker, 0.0, 0.0), (marker, 1.0, 0.0), (marker, 0.0, 1.0)),)

    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", fake_fold)
    monkeypatch.setattr(view, "_phase6_place_assembly_triangles", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", lambda tris, *a, **k: tuple(tris))

    detected_targets = []
    def fake_detect(source, target, **kwargs):
        detected_targets.append(tuple(target))
        return assembly_geometry.MeshInterferenceDiagnostic((), (), 0, ())
    monkeypatch.setattr(assembly_geometry, "detect_world_mesh_surface_interference", fake_detect)

    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=Axis()))
    request = view.FinalSceneViewRequest(
        render_data=render_data, x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    )
    scene_view.render(request)

    # Full restored head is still rendered, but collision probing must fold the
    # fixed-relief delta (12*10) as a separate target instead of the whole head.
    assert round(body_material.area, 6) in folded_areas
    assert round(4000.0, 6) in folded_areas
    assert round(120.0, 6) in folded_areas
    assert len(detected_targets) == 1
    marker = detected_targets[0][0][0][0]
    assert marker == pytest.approx(0.12)


def test_interference_overlay_renders_local_target_zone_fill_and_solid_crossing_lines(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box

    body_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40).difference(box(0, 0, 12, 10)), fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body"),
            view.AssemblyScenePart("head", head_data, _flat_profile(100), _flat_profile(40), "top"),
        ),
        show_interference=True,
        ignore_fixed_corner_relief=True,
    )
    local = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    target = (((10.0, 10.0, 10.0), (11.0, 10.0, 10.0), (10.0, 11.0, 10.0)),)
    seg = (((10.0, 10.0, 10.0), (11.0, 10.0, 10.0)),)

    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", lambda *a, **k: local)
    monkeypatch.setattr(view, "_phase6_place_assembly_triangles", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(
        assembly_geometry,
        "detect_world_mesh_surface_interference",
        lambda *a, **k: assembly_geometry.MeshInterferenceDiagnostic(target, seg[0], 1, seg),
    )

    axis = Axis()
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=axis))
    scene_view.render(view.FinalSceneViewRequest(
        render_data=render_data, x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    ))

    names = [type(obj).__name__ for obj in axis.collections]
    assert names.count("Poly3DCollection") >= 3  # body + head + red collision zone
    assert "Line3DCollection" in names


def test_fixed_relief_diagnostic_does_not_treat_normal_full_sheet_mating_as_collision_when_restore_is_off(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene
    from shapely.geometry import box

    body_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    head_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40), fold_guides=())
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(
            view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body"),
            view.AssemblyScenePart("head", head_data, _flat_profile(100), _flat_profile(40), "top"),
        ),
        show_interference=True,
        ignore_fixed_corner_relief=False,
    )
    local = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", lambda *a, **k: local)
    monkeypatch.setattr(view, "_phase6_place_assembly_triangles", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", lambda tris, *a, **k: tuple(tris))

    calls = []
    monkeypatch.setattr(
        assembly_geometry,
        "detect_world_mesh_surface_interference",
        lambda *a, **k: calls.append((a, k)) or assembly_geometry.MeshInterferenceDiagnostic((), (), 0, ()),
    )

    axis = Axis()
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=axis))
    scene_view.render(view.FinalSceneViewRequest(
        render_data=render_data, x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    ))

    assert calls == []
    assert scene_view.last_interference_diagnostic.has_interference is False


def test_bridge_assembly_query_applies_verified_backprojected_relief_with_clearance(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    solved_head = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 95, 75), fold_guides=())
    solved_tail = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 94, 74), fold_guides=())
    calls = []

    def callback(part_key, payload):
        if payload.get("resolved_assembly_relief_cuts") and part_key in {"head", "tail"}:
            return solved_head if part_key == "head" else solved_tail
        return raw[part_key]

    def fake_solver(**kwargs):
        calls.append(kwargs)
        placement = kwargs["endcap_placement"]
        solved = solved_head if placement == "top" else solved_tail
        measurement = SimpleNamespace(
            corner_name="bottom_left" if placement == "top" else "top_left",
            primary_u=39.0,
            primary_v=38.0,
            secondary_u=14.0,
            secondary_depth=4.0,
            clearance_a=5.0,
        )
        return SimpleNamespace(
            verified=True,
            cut_polygon_2d=box(0, 0, 7, 9),
            solved_render_data=solved,
            corner_reliefs=(SimpleNamespace(corner_name=measurement.corner_name, measurement=measurement),),
            residual_projection=SimpleNamespace(segments_2d=()),
        )

    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={
            "t": 2.0,
            "assembly_type": "INSERT",
            "existing_parts": ["box_body", "head", "tail"],
        },
        _phase6_assembly_type="INSERT",
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: True),
        assembly_show_interference_var=SimpleNamespace(get=lambda: True),
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "5"),
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    bundle = bridge._phase6_query_assembly_render_data(app)

    by_key = {part.part_key: part for part in bundle.assembly_parts}
    assert by_key["head"].render_data is solved_head
    assert by_key["tail"].render_data is solved_tail
    assert [call["clearance"] for call in calls] == [5.0, 5.0]
    assert bundle.ignore_fixed_corner_relief is False
    assert set(app._phase6_last_relief_solutions) == {"head", "tail"}


def test_assembly_diagnostic_status_reports_actual_corner_dimensions_and_verification():
    import fold_designer_bridge as bridge

    class Var:
        def __init__(self, value=None):
            self.value = value
        def get(self):
            return self.value
        def set(self, value):
            self.value = value

    def solution(corner):
        m = SimpleNamespace(
            corner_name=corner,
            primary_u=39.0,
            primary_v=38.0,
            secondary_u=14.0,
            secondary_depth=4.0,
            clearance_a=0.0,
        )
        return SimpleNamespace(
            verified=True,
            corner_reliefs=(SimpleNamespace(corner_name=corner, measurement=m),),
        )

    size = Var("等待")
    status = Var("等待")
    app = SimpleNamespace(
        assembly_relief_size_var=size,
        assembly_collision_status_var=status,
        assembly_ignore_fixed_corner_var=Var(True),
        assembly_show_interference_var=Var(True),
        _phase6_last_relief_solutions={
            "head": solution("bottom_left"),
            "tail": solution("top_left"),
        },
        _phase6_last_relief_errors={},
    )

    bridge._phase6_update_assembly_diagnostic_status(app)

    assert "封頭" in size.value
    assert "39×38 + 14×4" in size.value
    assert "封尾" in size.value
    assert status.value == "3D驗證：封頭✓ 封尾✓（零材料穿透）"


def test_bridge_assembly_bundle_is_backward_compatible_with_legacy_scene_contract(monkeypatch):
    """Mixed UPDATE installs must not crash on legacy AssemblySceneRenderData."""
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    class LegacyAssemblySceneRenderData:
        def __init__(self, assembly_parts, warnings=()):
            self.assembly_parts = tuple(assembly_parts)
            self.warnings = tuple(warnings)

    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]

    def callback(part_key, payload):
        return SimpleNamespace(
            scene=DrawingScene(),
            material=box(0, 0, 100, 80),
            fold_guides=(),
        )

    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body"],
            "active_part": "box_body",
        }),
        state=SimpleNamespace(
            profiles={"X": flat_x, "Y": flat_y},
            profiles_vault={"箱身": flat_x},
        ),
        _scene_query_callback=callback,
        _phase6_input_snapshot={},
        _settings_values={},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: False),
        assembly_show_interference_var=SimpleNamespace(get=lambda: True),
    )
    monkeypatch.setattr(bridge, "AssemblySceneRenderData", LegacyAssemblySceneRenderData)

    bundle = bridge._phase6_query_assembly_render_data(app)

    assert isinstance(bundle, LegacyAssemblySceneRenderData)
    assert [part.part_key for part in bundle.assembly_parts] == ["box_body"]


def test_bridge_verified_relief_requeries_authoritative_render_provider_with_solver_cuts(monkeypatch):
    """Assembly 3D must display the same Manufacturing PartRenderData that 2D/DXF replay uses."""
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    canonical = {
        "head": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 91, 71), fold_guides=()),
        "tail": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 92, 72), fold_guides=()),
    }
    callback_calls = []

    def callback(part_key, payload):
        callback_calls.append((part_key, dict(payload)))
        if part_key in canonical and payload.get("resolved_assembly_relief_cuts"):
            return canonical[part_key]
        return raw[part_key]

    def fake_solver(**kwargs):
        placement = kwargs["endcap_placement"]
        cut = box(0, 0, 7, 9)
        measurement = SimpleNamespace(
            corner_name="bottom_left" if placement == "top" else "top_left",
            primary_u=7.0, primary_v=9.0, secondary_u=None, secondary_depth=None, clearance_a=0.0,
        )
        # Same geometry, different object: final display must still come from the provider.
        solver_private = SimpleNamespace(
            scene=DrawingScene(),
            material=(canonical["head"].material if placement == "top" else canonical["tail"].material),
            fold_guides=(),
        )
        return SimpleNamespace(
            verified=True, cut_polygon_2d=cut, solved_render_data=solver_private,
            corner_reliefs=(SimpleNamespace(corner_name=measurement.corner_name, measurement=measurement),),
            residual_projection=SimpleNamespace(segments_2d=()),
        )

    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"], "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0, "assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"]}, _phase6_assembly_type="INSERT", _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={}, _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: True),
        assembly_show_interference_var=SimpleNamespace(get=lambda: True),
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "0"),
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    bundle = bridge._phase6_query_assembly_render_data(app)
    by_key = {part.part_key: part for part in bundle.assembly_parts}

    assert by_key["head"].render_data is canonical["head"]
    assert by_key["tail"].render_data is canonical["tail"]
    replay_calls = [payload for key, payload in callback_calls if key in {"head", "tail"} and payload.get("resolved_assembly_relief_cuts")]
    assert len(replay_calls) == 2
    assert all(len(payload["resolved_assembly_relief_cuts"]) == 1 for payload in replay_calls)


def test_assembly_relief_is_atomic_when_one_endcap_fails_verification(monkeypatch):
    """Never display half-new/half-old EndCaps; both must verify before either is applied."""
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    replayed = {
        "head": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 91, 71), fold_guides=()),
        "tail": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 92, 72), fold_guides=()),
    }

    def callback(part_key, payload):
        if part_key in replayed and payload.get("resolved_assembly_relief_cuts"):
            return replayed[part_key]
        return raw[part_key]

    def fake_solver(**kwargs):
        placement = kwargs["endcap_placement"]
        verified = placement == "top"
        return SimpleNamespace(
            verified=verified,
            cut_polygon_2d=box(0, 0, 7, 9),
            solved_render_data=replayed["head" if placement == "top" else "tail"],
            corner_reliefs=(),
            residual_projection=SimpleNamespace(segments_2d=((1, 2),) if not verified else ()),
        )

    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"], "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0, "assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"]}, _phase6_assembly_type="INSERT", _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={}, _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: True),
        assembly_show_interference_var=SimpleNamespace(get=lambda: True),
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "0"),
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    bundle = bridge._phase6_query_assembly_render_data(app)
    by_key = {part.part_key: part for part in bundle.assembly_parts}

    assert by_key["head"].render_data is raw["head"]
    assert by_key["tail"].render_data is raw["tail"]
    assert "tail" in app._phase6_last_relief_errors


def test_serialize_assembly_relief_rejects_partial_verified_transaction():
    import fold_designer_bridge as bridge
    from phase6_designer_workspace import Phase6DesignerWorkspace

    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    verified_head = SimpleNamespace(
        verified=True, cut_polygon_2d=box(0, 0, 7, 9), corner_reliefs=(),
    )
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"], "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: True),
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "0"),
        _phase6_last_relief_solutions={"head": verified_head},
        _phase6_input_snapshot={"w":100.0,"h":80.0,"d":40.0,"t":2.0,"fw":24.0},
        _settings_values={}, _phase6_box_whd={},
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        state=SimpleNamespace(profiles_vault={"箱身": flat_x}),
    )

    state = bridge._phase6_serialize_assembly_relief_state(app)

    assert state["enabled"] is False
    assert state["parts"] == {}


def test_bridge_keeps_pre_solve_endcap_probe_for_interference_overlay(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    solved = {
        "head": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 90, 70), fold_guides=()),
        "tail": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 89, 69), fold_guides=()),
    }

    def callback(part_key, payload):
        if payload.get("resolved_assembly_relief_cuts") and part_key in solved:
            return solved[part_key]
        return raw[part_key]

    def fake_solver(**kwargs):
        key = "head" if kwargs["endcap_placement"] == "top" else "tail"
        measurement = SimpleNamespace(
            corner_name="bottom_left" if key == "head" else "top_left",
            primary_u=10.0, primary_v=12.0,
            secondary_u=None, secondary_depth=None, clearance_a=0.0,
        )
        return SimpleNamespace(
            verified=True,
            cut_polygon_2d=box(0, 0, 10, 12),
            solved_render_data=solved[key],
            corner_reliefs=(SimpleNamespace(corner_name=measurement.corner_name, measurement=measurement),),
            residual_projection=SimpleNamespace(segments_2d=()),
        )

    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0, "assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"]},
        _phase6_assembly_type="INSERT",
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={},
        _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=SimpleNamespace(get=lambda: True),
        assembly_show_interference_var=SimpleNamespace(get=lambda: True),
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: "0"),
    )
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    bundle = bridge._phase6_query_assembly_render_data(app)

    displayed = {part.part_key: part.render_data for part in bundle.assembly_parts}
    probes = {part.part_key: part.render_data for part in bundle.interference_probe_parts}
    assert displayed["head"] is solved["head"]
    assert displayed["tail"] is solved["tail"]
    assert probes["head"] is raw["head"]
    assert probes["tail"] is raw["tail"]


def test_final_scene_interference_overlay_uses_pre_solve_probe_while_rendering_solved_endcap(monkeypatch):
    import ae_engine.assembly_geometry as assembly_geometry
    import phase6_final_scene_view as view
    from ae_engine.sheetmetal_drawing import DrawingScene

    body_data = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
    raw_head = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40).difference(box(0, 0, 12, 10)), fold_guides=())
    solved_head = SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 40).difference(box(0, 0, 20, 12)), fold_guides=())
    body_part = view.AssemblyScenePart("box_body", body_data, _flat_profile(100), _flat_profile(80), "box_body")
    solved_part = view.AssemblyScenePart("head", solved_head, _flat_profile(100), _flat_profile(40), "top")
    probe_part = view.AssemblyScenePart("head", raw_head, _flat_profile(100), _flat_profile(40), "top")
    render_data = view.AssemblySceneRenderData(
        assembly_parts=(body_part, solved_part),
        interference_probe_parts=(probe_part,),
        show_interference=True,
    )

    local = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    target = (((10.0, 10.0, 10.0), (11.0, 10.0, 10.0), (10.0, 11.0, 10.0)),)
    segment = (((10.0, 10.0, 10.0), (11.0, 10.0, 10.0)),)
    folded_areas = []

    def fake_fold(material, *args, **kwargs):
        folded_areas.append(round(float(material.area), 6))
        return local

    monkeypatch.setattr(view, "_phase6_folded_mesh_from_polygon", fake_fold)
    monkeypatch.setattr(view, "_phase6_place_assembly_triangles", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "place_endcap_against_box_body", lambda tris, *a, **k: tuple(tris))
    monkeypatch.setattr(assembly_geometry, "thicken_triangle_surface", lambda tris, *a, **k: tuple(tris))
    calls = []
    monkeypatch.setattr(
        assembly_geometry,
        "detect_world_mesh_surface_interference",
        lambda source, target_mesh, **k: calls.append(tuple(target_mesh)) or assembly_geometry.MeshInterferenceDiagnostic(target, segment[0], 1, segment),
    )

    axis = Axis()
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=axis))
    scene_view.render(view.FinalSceneViewRequest(
        render_data=render_data, x_profile=(), y_profile=(), part_key="assembly",
        alpha_bend=0.85, finished_dimensions=(100.0, 80.0, 40.0), thickness=2.0,
    ))

    assert calls, "pre-solve collision probe must reach the detector"
    assert round(120.0, 6) in folded_areas  # raw fixed-relief delta, not solved material
    assert scene_view.last_interference_diagnostic.has_interference is True
