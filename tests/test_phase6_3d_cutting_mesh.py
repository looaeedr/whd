# -*- coding: utf-8 -*-
import math
from types import SimpleNamespace

import pytest
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from shapely.geometry import Point

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene
from fold_designer_bridge import (
    _phase6_folded_mesh_from_polygon,
    _phase6_add_mesh_boundary_lines,
    _phase6_fitted_limits_from_vertices,
    _phase6_query_final_render_data,
)


def _triangle_area3(tri):
    a, b, c = tri
    ab = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
    ac = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
    cross = (
        ab[1]*ac[2] - ab[2]*ac[1],
        ab[2]*ac[0] - ab[0]*ac[2],
        ab[0]*ac[1] - ab[1]*ac[0],
    )
    return 0.5 * math.sqrt(sum(v*v for v in cross))


def _flat_profile(length):
    return [{"len": float(length)}]


def test_cutting_scene_subtracts_circle_and_profile_holes():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_circle((25, 30), 5, layer="CUTTING")
    scene.add_polyline([(60, 20), (80, 20), (80, 40), (60, 40)], layer="CUTTING", closed=True)

    geom = manufacturing_api.material_polygon_from_final_scene(scene)

    assert geom.contains(Point(10, 10))
    assert not geom.contains(Point(25, 30))
    assert not geom.contains(Point(70, 30))
    assert geom.area == pytest.approx(6000 - math.pi * 25 - 400, rel=2e-3)


def test_flat_folded_mesh_preserves_true_cutting_area_with_hole():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_circle((50, 30), 8, layer="CUTTING")
    geom = manufacturing_api.material_polygon_from_final_scene(scene)

    tris = _phase6_folded_mesh_from_polygon(geom, _flat_profile(100), _flat_profile(60))

    assert tris
    mesh_area = sum(_triangle_area3(tri) for tri in tris)
    assert mesh_area == pytest.approx(geom.area, rel=2e-3)
    # A real hole means no generated triangle centroid is inside it.
    for tri in tris:
        cx = sum(p[0] for p in tri) / 3.0 + 50.0  # flat mapping is centered
        cy = sum(p[1] for p in tri) / 3.0 + 30.0
        assert (cx - 50.0) ** 2 + (cy - 30.0) ** 2 >= 8.0 ** 2 - 1e-6


def test_corner_notch_is_preserved_in_3d_mesh():
    scene = DrawingScene()
    scene.add_polyline(
        [(10, 0), (100, 0), (100, 60), (0, 60), (0, 10), (10, 10)],
        layer="CUTTING", closed=True,
    )
    geom = manufacturing_api.material_polygon_from_final_scene(scene)
    tris = _phase6_folded_mesh_from_polygon(geom, _flat_profile(100), _flat_profile(60))

    assert geom.area == pytest.approx(5900.0)
    assert sum(_triangle_area3(t) for t in tris) == pytest.approx(5900.0, rel=1e-6)


def test_fold_mapping_keeps_cut_geometry_and_creates_real_z_depth():
    geom_scene = DrawingScene()
    geom_scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    geom = manufacturing_api.material_polygon_from_final_scene(geom_scene)
    x_profile = [
        {"len": 10.0, "angle": -90},
        {"len": 80.0, "angle": -90},
        {"len": 10.0},
    ]
    tris = _phase6_folded_mesh_from_polygon(geom, x_profile, _flat_profile(60))

    zs = [p[2] for tri in tris for p in tri]
    assert max(zs) - min(zs) > 9.0
    assert sum(_triangle_area3(t) for t in tris) == pytest.approx(geom.area, rel=1e-6)


def test_fitted_limits_follow_real_xyz_spans_instead_of_cube_max_b():
    vertices = [(0, 0, 0), (1000, 0, 0), (1000, 100, 50), (0, 100, 50)]
    xlim, ylim, zlim = _phase6_fitted_limits_from_vertices(vertices, padding=0.06)

    xspan = xlim[1] - xlim[0]
    yspan = ylim[1] - ylim[0]
    zspan = zlim[1] - zlim[0]
    assert xspan / yspan == pytest.approx(10.0, rel=0.05)
    assert xspan / zspan == pytest.approx(20.0, rel=0.05)
    assert xspan < 1200
    assert yspan < 130



def test_mesh_boundary_is_batched_into_one_line_collection():
    fig = Figure()
    ax = fig.add_subplot(111, projection='3d')
    app = SimpleNamespace(renderer=SimpleNamespace(ax3d=ax))
    triangles = [
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
        ((0.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)),
    ]

    _phase6_add_mesh_boundary_lines(app, triangles, '#111111')

    boundary_collections = [c for c in ax.collections if isinstance(c, Line3DCollection)]
    assert len(ax.lines) == 0
    assert len(boundary_collections) == 1
    assert len(boundary_collections[0]._segments3d) == 4

def test_real_tk_active_door_uses_features_and_corner_state_in_cutting_mesh():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2, CornerTypeSelection, CornerTypeId, CrossCornerMode, CornerDirection

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.surface_features["door"] = [
            CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0), layer="CUTTING")
        ]
        designer = app.open_original_fold_designer()
        designer.activate_part("door")
        root.update_idletasks(); root.update()

        render1 = _phase6_query_final_render_data(designer)
        scene1 = render1.scene
        material1 = render1.material
        assert len(material1.interiors) >= 1

        designer._phase6_corner_state["door"] = {
            "top_left": {"type_id": "CROSS", "cross_mode": "extra_cut", "direction": "both", "amount_t": 2.0},
            "top_right": {"type_id": "CROSS", "cross_mode": "standard"},
            "bottom_left": {"type_id": "CROSS", "cross_mode": "standard"},
            "bottom_right": {"type_id": "CROSS", "cross_mode": "standard"},
        }
        render2 = _phase6_query_final_render_data(designer)
        scene2 = render2.scene
        material2 = render2.material
        assert material2.area != pytest.approx(material1.area)

        designer.renderer.render()
        assert getattr(designer, "_phase6_last_cutting_mesh", None)
        assert getattr(designer, "_phase6_last_cutting_material", None) is not None
        spans = [
            hi - lo for lo, hi in (
                designer.renderer.ax3d.get_xlim3d(),
                designer.renderer.ax3d.get_ylim3d(),
                designer.renderer.ax3d.get_zlim3d(),
            )
        ]
        assert max(spans) / min(spans) > 5.0  # no max_b cube
        assert designer.renderer.ax3d.get_position().width > 0.95

        # Optional shared indicator parts require their configured global baseline.
        # Their material-hole behavior is covered by baseline/resource tests with
        # an explicit temporary resource root; this Tk smoke stays baseline-free.
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_mesh_tessellation_simplifies_dense_curves_without_changing_authoritative_material():
    """3D may simplify tessellation only; the shared Final Part Geometry stays untouched."""
    from shapely.geometry import box, Point
    from fold_designer_bridge import _phase6_folded_mesh_from_polygon

    material = box(0, 0, 100, 60).difference(Point(50, 30).buffer(10, quad_segs=64))
    before_wkb = material.wkb
    tris = _phase6_folded_mesh_from_polygon(material, [{"len": 100.0}], [{"len": 60.0}])

    assert material.wkb == before_wkb
    # A 256-edge display circle must not generate hundreds of 3D triangles.
    assert len(tris) < 100
