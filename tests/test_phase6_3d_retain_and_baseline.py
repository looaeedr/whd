# -*- coding: utf-8 -*-
"""3D renderer regression: consume one final DrawingScene, never baseline twice."""
from types import SimpleNamespace

import pytest
from shapely.geometry import Point, box

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene
import fold_designer_bridge as bridge


def _final_scene_with_bends():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_line((20, 0), (20, 60), layer="BEND")
    scene.add_line((80, 0), (80, 60), layer="BEND")
    scene.add_line((0, 15), (100, 15), layer="BEND")
    scene.add_line((0, 45), (100, 45), layer="BEND")
    return scene


def test_final_scene_cutting_circle_and_exploded_loop_are_material_holes():
    scene = _final_scene_with_bends()
    scene.add_circle((25, 30), 5, layer="CUTTING")
    for a, b in [((60, 20), (80, 20)), ((80, 20), (80, 40)), ((80, 40), (60, 40)), ((60, 40), (60, 20))]:
        scene.add_line(a, b, layer="CUTTING")

    material = manufacturing_api.material_polygon_from_final_scene(scene)

    assert not material.contains(Point(25, 30))
    assert not material.contains(Point(70, 30))


def test_final_scene_marking_and_blind_hole_do_not_cut_material():
    scene = _final_scene_with_bends()
    scene.add_circle((30, 30), 6.5, layer="MARKING")
    scene.add_circle((50, 30), 4.0, layer="BLIND_HOLE")
    scene.add_circle((70, 30), 3.0, layer="CUTTING")

    material = manufacturing_api.material_polygon_from_final_scene(scene)

    assert material.contains(Point(30, 30))
    assert material.contains(Point(50, 30))
    assert not material.contains(Point(70, 30))


def test_fold_ownership_is_inferred_from_final_material_topology_only():
    # Bottom-left corner tongue touches the horizontal outside edge but not the
    # vertical outside edge. It belongs to the bottom flange, so X fold is suppressed.
    main = box(20, 15, 80, 45)
    bottom = box(20, 0, 80, 15)
    left = box(0, 15, 20, 45)
    right = box(80, 15, 100, 45)
    top = box(20, 45, 80, 60)
    tongue = box(18, 0, 20, 15)
    material = main.union(bottom).union(left).union(right).union(top).union(tongue)

    exemptions = bridge._phase6_fold_ownership_exemptions(
        material, (0.0, 20.0, 80.0, 100.0), (0.0, 15.0, 45.0, 60.0)
    )

    assert any(axis == "x" and region.covers(Point(19, 7)) for axis, region in exemptions)
    assert not any(axis == "y" and region.covers(Point(19, 7)) for axis, region in exemptions)


def test_retained_tongue_does_not_receive_suppressed_fold_transform():
    tongue = box(18, 0, 20, 15)
    x_profile = [
        {"len": 20.0, "angle": -90},
        {"len": 60.0, "angle": 90},
        {"len": 20.0},
    ]
    y_profile = [
        {"len": 15.0, "angle": -90},
        {"len": 30.0, "angle": 90},
        {"len": 15.0},
    ]

    tris = bridge._phase6_folded_mesh_from_polygon(
        tongue, x_profile, y_profile, fold_exemptions=[("x", tongue)]
    )
    xs = {round(p[0], 6) for tri in tris for p in tri}
    assert xs == {-32.0, -30.0}


def _real_3d_axis():
    from matplotlib.figure import Figure
    fig = Figure(figsize=(4, 3))
    return fig, fig.add_subplot(111, projection="3d")


def test_true_mesh_renderer_uses_exact_final_scene_without_baseline_merge(monkeypatch):
    scene = _final_scene_with_bends()
    scene.add_circle((50, 30), 7, layer="CUTTING")
    _fig, ax = _real_3d_axis()
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "door"], "active_part": "door"
    })
    app = SimpleNamespace(
        designer_workspace=workspace,
        state=SimpleNamespace(alpha_bend=0.85),
        renderer=SimpleNamespace(ax3d=ax),
        _scene_query_callback=lambda part, payload: manufacturing_api.PartRenderData(
            scene=scene, material=manufacturing_api.material_polygon_from_final_scene(scene)
        ),
        _phase6_input_snapshot={}, _settings_values={}, _phase6_box_whd={},
        _phase6_corner_state={},
    )
    monkeypatch.setattr(bridge, "_phase6_active_mesh_profiles", lambda self, material: (
        [{"len":20.0},{"len":60.0},{"len":20.0}],
        [{"len":15.0},{"len":30.0},{"len":15.0}],
    ))
    monkeypatch.setattr(bridge, "_phase6_remove_original_bend_surfaces", lambda self: None)
    monkeypatch.setattr(bridge, "_phase6_add_mesh_boundary_lines", lambda *args, **kwargs: None)
    monkeypatch.setattr(bridge, "_phase6_draw_scene_bends", lambda *args, **kwargs: None)
    monkeypatch.setattr(bridge, "_phase6_draw_scene_markings", lambda *args, **kwargs: None)

    bridge._phase6_render_true_cutting_mesh(app)

    assert app._phase6_last_cutting_material is not None
    assert not app._phase6_last_cutting_material.contains(Point(50, 30))


def test_removed_second_engine_helpers_stay_absent():
    for name in (
        "_phase6_cutting_holes_from_scene",
        "_phase6_material_with_baseline_holes",
        "_phase6_retained_fold_exemptions",
        "_phase6_current_cutting_scene",
        "_phase6_current_baseline_cutting_scene",
        "_phase6_align_baseline_scene_to_current",
    ):
        assert not hasattr(bridge, name), name
