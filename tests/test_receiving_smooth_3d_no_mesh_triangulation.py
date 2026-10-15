# -*- coding: utf-8 -*-
"""Smooth display excludes mesh-generated diagonal artifacts, not real bends."""
from types import SimpleNamespace

from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_final_scene_projection import _phase6_mesh_feature_segments
from phase6_final_scene_contracts import FinalSceneViewRequest


def test_smooth_3d_ignores_coplanar_triangle_diagonal_but_retains_real_crease():
    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    view = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    # Two coplanar triangular pieces are one rectangle, not a diagonal line.
    coplanar = (
        ((0., 0., 0.), (10., 0., 0.), (10., 10., 0.)),
        ((0., 0., 0.), (10., 10., 0.), (0., 10., 0.)),
    )
    assert len(_phase6_mesh_feature_segments(coplanar)) == 4
    view._add_mesh_boundary_and_crease_lines(coplanar, "#123456", creases_only=True)
    assert not [x for x in ax.collections if isinstance(x, Line3DCollection)]

    # Fold adjacent to another face is a legitimate physical edge.
    noncoplanar = (
        ((0., 0., 0.), (10., 0., 0.), (10., 10., 0.)),
        ((10., 0., 0.), (10., 10., 0.), (10., 10., 10.)),
    )
    view._add_mesh_boundary_and_crease_lines(noncoplanar, "#123456", creases_only=True)
    collections = [x for x in ax.collections if isinstance(x, Line3DCollection)]
    assert len(collections) == 1
    assert len(collections[0]._segments3d) == 1


def test_flat_part_keeps_authoritative_bend_and_marking_with_no_mesh_lines(monkeypatch):
    from shapely.geometry import box
    material = box(0., 0., 100., 80.)
    scene = DrawingScene()
    scene.add_line((25., 0.), (25., 80.), layer="BEND")
    scene.add_line((40., 15.), (60., 15.), layer="MARKING")
    fig=Figure()
    ax=fig.add_subplot(111,projection="3d")
    renderer=Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    def forbidden_mesh_boundary(*args,**kwargs):
        raise AssertionError("mesh triangle boundaries must never appear in 3D")
    monkeypatch.setattr(renderer,"_add_mesh_boundary_lines",forbidden_mesh_boundary)
    monkeypatch.setattr(renderer,"_add_mesh_feature_lines",forbidden_mesh_boundary)
    request=FinalSceneViewRequest(
        render_data=SimpleNamespace(material=material,scene=scene,fold_guides=()),
        part_key="head",
        x_profile=({"len":100.},),
        y_profile=({"len":80.},),
        finished_dimensions=(100.,80.,40.),thickness=2.,
    )
    tris=renderer.render(request)
    assert tris
    assert len(ax.collections)==1   # only shaded physical surface; no triangle overlay
    # Dimensions are also authored geometry, so these are 3D plotting lines
    # not mesh-edge collections. Preserve BEND blue and MARKING amber.
    colors = {str(line.get_color()) for line in ax.lines}
    assert "#2563eb" in colors
    assert "#f59e0b" in colors


def test_real_receiving_all_panels_shaded_without_triangle_edges(monkeypatch):
    """WHD actual folded W800 Receiving, not a fabricated graphics example."""
    from tests.test_issue1050_receiving_mother_plate_marking import (
        _snapshot,_full_receiving_geometry,
    )
    from phase6_manufacturing_geometry import _phase6_resolve_family_divider_reliefs
    from phase6_final_scene_contracts import AssemblyScenePart, AssemblySceneRenderData
    snap=_snapshot()
    geometry=_full_receiving_geometry(snap)
    parts,diagnostics,_=_phase6_resolve_family_divider_reliefs(
        geometry.parts,
        finished_dimensions=(snap["w"],snap["h"],snap["d"]),
        sheet_thickness=snap["t"],
    )
    assert diagnostics and all(not x.illegal_penetration for x in diagnostics)

    def as_rows(values):
        return tuple(
            dict(x) if isinstance(x,dict)
            else {"len":float(x.length),
                  **({"angle":float(x.angle)} if x.angle is not None else {}),
                  **({"phase6_key":str(x.phase6_key)} if x.phase6_key else {})}
            for x in values
        )
    actual_parts=tuple(AssemblyScenePart(
        part_key=p.part_key,render_data=p.render_data,
        x_profile=as_rows(p.x_profile), y_profile=as_rows(p.y_profile),
        placement=p.placement,offset=p.offset
    ) for p in parts)
    fig=Figure(figsize=(5,4))
    ax=fig.add_subplot(111,projection="3d")
    renderer=Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    def forbidden(*_args,**_kw):
        raise AssertionError("3D physical meshes must not draw their triangle boundaries")
    monkeypatch.setattr(renderer, "_add_mesh_boundary_lines", forbidden)
    from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin
    real_features=Phase6FinalSceneRenderHelpersMixin._add_mesh_feature_lines
    features=[]
    def record_features(triangles,color):
        features.append(len(triangles))
        return real_features(renderer,triangles,color)
    monkeypatch.setattr(renderer, "_add_mesh_feature_lines",record_features)
    tris=renderer.render(FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(
            assembly_parts=actual_parts,show_interference=False,
            preserve_endcap_core_origin=True,
            collision_certification_diagnostics=tuple(diagnostics),
        ),
        x_profile=(),y_profile=(),part_key="assembly",
        thickness=snap["t"],finished_dimensions=(snap["w"],snap["h"],snap["d"]),
    ))
    assert len(tris)>1000
    # Only the small real back reference outline is explicitly drawn; the
    # thousands of side/head/frame/divider triangle edges are all hidden.
    assert features == [4]
    assert renderer.last_all_parts_collision_audit is None


def test_outer_door_assembly_renders_real_cutting_rim_and_source_bend():
    """Do not hide the real door cutout or fold behind the opaque 3D skin."""
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_contracts import AssemblyScenePart, AssemblySceneRenderData

    material = box(0, 0, 100, 80).difference(box(40, 25, 60, 35))
    scene = DrawingScene()
    scene.add_line((10, 0), (10, 80), layer="BEND")
    door = AssemblyScenePart(
        part_key="door_c1_r1",
        render_data=SimpleNamespace(scene=scene, material=material, fold_guides=()),
        x_profile=({"len": 100., "core": True},),
        y_profile=({"len": 80., "core": True},),
        placement="front", offset=(0., 0., 0.),
    )
    fig = Figure()
    ax = fig.add_subplot(111, projection="3d")
    view = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    request = FinalSceneViewRequest(
        part_key="assembly", render_data=AssemblySceneRenderData(
            assembly_parts=(door,), show_interference=False,
        ),
        x_profile=(), y_profile=(), finished_dimensions=(100., 80., 100.),
        thickness=2.,
    )
    view.render(request)
    assert any(isinstance(item, Line3DCollection) and len(item._segments3d) >= 4
               for item in ax.collections)  # actual physical inner-hole boundary
    assert "#2563eb" in {str(item.get_color()) for item in ax.lines}
