# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect

from shapely.geometry import Point, box

import phase6_final_scene_view as view


def _flat_profile(length):
    return [{"len": float(length), "core": True}]


def test_final_scene_view_never_rebuilds_manufacturing_geometry():
    source = inspect.getsource(view)
    for forbidden in (
        "build_part_render_data(",
        "material_polygon_from_final_scene(",
        "fold_guides_from_final_scene(",
    ):
        assert forbidden not in source


def test_final_scene_view_does_not_call_assembly_collision_solver():
    source = inspect.getsource(view)

    assert "assembly_collision" not in source
    assert "solve_boxbody_endcap_relief" not in source
    assert "detect_planar_collision" not in source


def test_folded_mesh_consumes_authoritative_material_with_hole():
    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    triangles = view._phase6_folded_mesh_from_polygon(
        material,
        _flat_profile(100),
        _flat_profile(60),
        fold_guides=(),
    )

    assert triangles
    # A 3D View may triangulate the supplied material, but it must not recreate
    # the removed CUTTING hole as filled material.
    for tri in triangles:
        cx = sum(p[0] for p in tri) / 3.0 + 50.0
        cy = sum(p[1] for p in tri) / 3.0 + 30.0
        assert not (40 < cx < 60 and 20 < cy < 40)


def test_view_render_consumes_part_render_data_without_manufacturing_query():
    from types import SimpleNamespace
    from ae_engine.sheetmetal_drawing import DrawingScene

    class Axis:
        def __init__(self):
            self.collections = []
            self.lines = []
            self.transAxes = object()
        def add_collection3d(self, obj): self.collections.append(obj)
        def plot(self, *args, **kwargs): return None
        def text(self, *args, **kwargs): return None
        def text2D(self, *args, **kwargs): return None
        def set_xlim3d(self, *args): self.xlim = args
        def set_ylim3d(self, *args): self.ylim = args
        def set_zlim3d(self, *args): self.zlim = args
        def set_box_aspect(self, *args, **kwargs): return None

    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    render_data = SimpleNamespace(scene=DrawingScene(), material=material, fold_guides=())
    renderer = SimpleNamespace(ax3d=Axis())
    scene_view = view.Phase6FinalSceneView(renderer)
    request = view.FinalSceneViewRequest(
        render_data=render_data,
        x_profile=tuple(_flat_profile(100)),
        y_profile=tuple(_flat_profile(60)),
        part_key="door",
        alpha_bend=0.85,
        finished_dimensions=(100.0, 60.0),
        thickness=2.0,
    )

    triangles = scene_view.render(request)

    assert triangles
    assert scene_view.last_cutting_material is material
    assert scene_view.last_cutting_mesh == triangles


def test_designer_compatibility_view_state_has_one_backing_owner():
    from types import SimpleNamespace
    import fold_designer_bridge as bridge

    designer = bridge.Phase6FoldDesignerApp.__new__(bridge.Phase6FoldDesignerApp)
    designer.final_scene_view = SimpleNamespace(
        zoom_scale=1.0,
        last_cutting_mesh=[("mesh",)],
        last_cutting_material=object(),
        cutting_mesh_error=None,
        view_initialized=False,
        base_renderer_render=None,
        scroll_cid=None,
    )

    assert "_phase6_zoom_scale" not in designer.__dict__
    assert "_phase6_last_cutting_mesh" not in designer.__dict__
    assert designer._phase6_zoom_scale == designer.final_scene_view.zoom_scale
    assert designer._phase6_last_cutting_mesh is designer.final_scene_view.last_cutting_mesh
    designer._phase6_zoom_scale = 0.75
    assert designer.final_scene_view.zoom_scale == 0.75
    assert "_phase6_zoom_scale" not in designer.__dict__



def test_bridge_contains_adapters_but_no_final_scene_view_implementation():
    import ast
    from pathlib import Path

    bridge_path = Path(__file__).resolve().parents[1] / "fold_designer_bridge.py"
    source = bridge_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for moved in (
        "_phase6_profile_geometry",
        "_phase6_folded_mesh_from_polygon",
        "_phase6_fitted_limits_from_vertices",
        "_phase6_remove_original_bend_surfaces",
        "_phase6_add_mesh_boundary_lines",
        "_phase6_draw_scene_bends",
        "_phase6_draw_scene_markings",
        "_phase6_configure_3d_only_figure",
        "_phase6_scale_current_3d_limits",
        "_phase6_adjust_zoom_scale",
    ):
        assert moved not in definitions
    for forbidden in (
        "Poly3DCollection",
        "Line3DCollection",
        "triangulate(",
        "set_box_aspect",
        "set_axis_off",
    ):
        assert forbidden not in source


def _assembly_line_segments(*, head_material, head_x_profile, head_y_profile, head_scene=None):
    from types import SimpleNamespace
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from ae_engine.sheetmetal_drawing import DrawingScene

    body_material = box(0, 0, 100, 80)
    body_data = SimpleNamespace(scene=DrawingScene(), material=body_material, fold_guides=())
    if head_scene is None:
        head_scene = DrawingScene()
    head_data = SimpleNamespace(scene=head_scene, material=head_material, fold_guides=())
    render_data = view.AssemblySceneRenderData(assembly_parts=(
        view.AssemblyScenePart(
            part_key="box_body", render_data=body_data,
            x_profile=tuple(_flat_profile(100)), y_profile=tuple(_flat_profile(80)),
            placement="box_body",
        ),
        view.AssemblyScenePart(
            part_key="head", render_data=head_data,
            x_profile=tuple(head_x_profile), y_profile=tuple(head_y_profile),
            placement="head",
        ),
    ))
    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    renderer = SimpleNamespace(ax3d=ax)
    scene_view = view.Phase6FinalSceneView(renderer)
    request = view.FinalSceneViewRequest(
        render_data=render_data, x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=(100.0, 80.0, 60.0), thickness=2.0,
    )
    scene_view.render(request)
    return [
        segment
        for collection in ax.collections
        if isinstance(collection, Line3DCollection)
        for segment in collection._segments3d
    ]


def test_assembly_endcap_keeps_cut_hole_outline_visible_after_physical_thickening():
    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    segments = _assembly_line_segments(
        head_material=material,
        head_x_profile=_flat_profile(100),
        head_y_profile=_flat_profile(60),
    )

    # Box Body contributes its own outline.  The physical EndCap must also draw
    # the pre-thickening surface boundary, which includes both outer perimeter
    # and the through-hole perimeter.  A closed solid alone has no open edge.
    # 4 BoxBody outline edges + at least 8 EndCap outer/hole perimeter edges.
    assert len(segments) >= 12


def test_assembly_endcap_keeps_real_first_fold_crease_visible_after_physical_thickening():
    material = box(0, 0, 100, 60)
    segments = _assembly_line_segments(
        head_material=material,
        head_x_profile=_flat_profile(100),
        head_y_profile=[
            {"len": 20.0, "angle": -90.0},
            {"len": 40.0, "core": "D-T"},
        ],
    )

    # The first formed fold is the shared non-coplanar edge across the full X
    # span. Thickness-only side edges are X-constant and cannot satisfy this.
    assert any(
        abs(float(a[2])) > 1.0
        and abs(float(a[1]) - float(b[1])) < 1e-6
        and abs(float(a[2]) - float(b[2])) < 1e-6
        and abs(float(a[0]) - float(b[0])) > 90.0
        for a, b in segments
    )


def test_endcap_physical_sheet_feature_edges_put_hole_rim_on_outer_skins_not_mid_surface():
    from ae_engine.assembly_geometry import thicken_triangle_surface

    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    surface = view._phase6_folded_mesh_from_polygon(
        material,
        _flat_profile(100),
        _flat_profile(60),
        fold_guides=(),
    )
    solid = thicken_triangle_surface(surface, 2.0)

    segments = view._phase6_mesh_feature_segments(solid)

    # Hole rim must be drawn on the physical skins z=+/-T/2.  Drawing only the
    # folded mid-surface z=0 makes the rim disappear behind the opaque sheet.
    skin_hole_edges = [
        (a, b) for a, b in segments
        if abs(abs(float(a[2])) - 1.0) < 1e-6
        and abs(float(a[2]) - float(b[2])) < 1e-6
        and max(abs(float(a[0])), abs(float(b[0]))) <= 10.000001
        and max(abs(float(a[1])), abs(float(b[1]))) <= 10.000001
    ]
    assert len(skin_hole_edges) >= 8
    assert all(abs(float(a[2])) > 0.5 for a, _b in skin_hole_edges)


def test_assembly_physical_sheet_feature_lines_are_explicit_solid_lines():
    from types import SimpleNamespace
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from ae_engine.assembly_geometry import thicken_triangle_surface

    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    surface = view._phase6_folded_mesh_from_polygon(
        material,
        _flat_profile(100),
        [
            {"len": 20.0, "angle": -90.0},
            {"len": 40.0, "core": "D-T"},
        ],
        fold_guides=(),
    )
    solid = thicken_triangle_surface(surface, 2.0)

    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=ax))
    scene_view._add_mesh_feature_lines(solid, "#111111")

    collections = [c for c in ax.collections if isinstance(c, Line3DCollection)]
    assert collections
    assert all(offset == 0.0 and dash is None for offset, dash in collections[-1].get_linestyle())


def test_scene_bend_guides_render_as_solid_lines():
    from types import SimpleNamespace
    from ae_engine.sheetmetal_drawing import DrawingScene

    calls = []

    class Axis:
        def plot(self, *args, **kwargs):
            calls.append((args, kwargs))

    scene = DrawingScene()
    scene.add_line((0.0, 20.0), (100.0, 20.0), layer="BEND")
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=Axis()))
    scene_view._draw_scene_bends(
        scene,
        _flat_profile(100),
        _flat_profile(60),
        fold_guides=(),
    )

    assert calls
    assert calls[0][1].get("linestyle") == "-"


def test_assembly_box_body_draws_authoritative_bend_guides_as_solid_lines():
    from types import SimpleNamespace
    from matplotlib.figure import Figure
    from ae_engine.sheetmetal_drawing import DrawingScene

    body_scene = DrawingScene()
    body_scene.add_line((20.0, 0.0), (20.0, 80.0), layer="BEND")
    body_data = SimpleNamespace(
        scene=body_scene,
        material=box(0, 0, 100, 80),
        fold_guides=(),
    )
    render_data = view.AssemblySceneRenderData(assembly_parts=(
        view.AssemblyScenePart(
            part_key="box_body",
            render_data=body_data,
            x_profile=tuple([
                {"len": 20.0, "angle": -90.0},
                {"len": 80.0, "core": "W"},
            ]),
            y_profile=tuple(_flat_profile(80)),
            placement="box_body",
        ),
    ))
    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    scene_view = view.Phase6FinalSceneView(SimpleNamespace(ax3d=ax))
    scene_view.render(view.FinalSceneViewRequest(
        render_data=render_data,
        x_profile=(),
        y_profile=(),
        part_key="assembly",
        finished_dimensions=(100.0, 80.0, 60.0),
        thickness=2.0,
    ))

    bend_lines = [line for line in ax.lines if line.get_color() == "#2563eb"]
    assert bend_lines, "assembly Box Body must render its authoritative BEND guide"
    assert all(line.get_linestyle() == "-" for line in bend_lines)
