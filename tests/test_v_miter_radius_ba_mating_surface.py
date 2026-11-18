# -*- coding: utf-8 -*-
"""#3317 直接驗接合面、板厚逆映射及缺料，不 mock 幾何結果。"""
import math

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def source(angle=90, mode="RELIEF_HOLE", height=30, mirror=False):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    params = dict(thickness_mm=2, first_flange_height_mm=20,
                  second_flange_height_mm=height, second_fold_angle_deg=angle,
                  relief_mode=mode, relief_t_factor=1.5)
    ideal = api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **params)
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    cut = PolylinePrimitive((
        Vec2(-100, -20), Vec2(a.x, -20), a,
        Vec2(b.x, a.y), Vec2(b.x, 0),
        Vec2(height, 10), Vec2(height, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    if mirror:
        reflect = lambda p: Vec2(-p.x, p.y)
        cut = PolylinePrimitive(tuple(reflect(p) for p in cut.points),
                                "CUTTING", closed=True)
        first = LinePrimitive(reflect(first.p1), reflect(first.p2), "BEND")
        second = LinePrimitive(reflect(second.p1), reflect(second.p2), "BEND")
    calibration = dict(
        first_inner_radius_mm=.5, second_inner_radius_mm=.5,
        first_bend_allowance_mm=math.pi / 2 * 1.3,
        second_bend_allowance_mm=math.radians(angle) * 1.3)
    return DrawingScene([cut, first, second]), first, second, params, calibration


def solve(parts):
    scene, first, second, params, calibration = parts
    return api.solve_v_miter_radius_ba_mating_surface_trial(
        scene, first, second, **params, **calibration)


def test_orthogonal_face_has_analytic_area_and_exposes_actual_missing_stock():
    parts = source()
    scene = parts[0]
    before = tuple(scene.primitives)
    out = solve(parts)
    ba = parts[-1]["first_bend_allowance_mm"]
    # 90/90、R=.5、T=2：x=-y 位於 [.5,2.5]，z 由1.5到1.5+20-BA。
    assert out.interface_area_mm2 == pytest.approx(math.sqrt(2) * 2 * (20 - ba))
    assert min(p[0] for p in out.interface_vertices) == pytest.approx(.5)
    assert max(p[0] for p in out.interface_vertices) == pytest.approx(2.5)
    assert min(p[2] for p in out.interface_vertices) == pytest.approx(1.5)
    assert max(p[2] for p in out.interface_vertices) == pytest.approx(21.5 - ba)
    assert all(abs(p[0] + p[1]) < 1e-8 for p in out.interface_vertices)
    assert out.first_axial_extension_mm == pytest.approx(2.5)
    assert out.second_axial_extension_mm == pytest.approx(2.5)
    assert out.first_missing_source_area_mm2 == pytest.approx(2 * (20 - ba))
    assert out.second_missing_source_area_mm2 == pytest.approx(2 * (20 - ba))
    assert out.source_status == "SOURCE_EXTENSION_REQUIRED"
    assert out.root_status == "CURVED_ROOT_UNSOLVED"
    assert out.solid_penetration_status == "WHOLE_SHEET_VOLUME_NOT_VERIFIED"
    assert out.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == before


@pytest.mark.parametrize("angle", (60, 90, 120))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("height", (20, 30))
@pytest.mark.parametrize("mirror", (False, True))
def test_actual_face_inverse_maps_refold_to_identical_world_points(angle, mode, height, mirror):
    parts = source(angle, mode, height, mirror)
    out = solve(parts)
    assert out.interface_area_mm2 > 0
    assert out.interface_triangles
    assert out.source_status == "SOURCE_EXTENSION_REQUIRED"
    remaining = Polygon([(p.x, p.y) for p in out.source_remaining_outline])
    assert remaining.is_valid and remaining.geom_type == "Polygon"
    assert not remaining.interiors
    # 獨立依兩側實際圓弧末端、直折方向與材料厚度重新成形。
    for i, vertices in enumerate((out.first_material_vertices, out.second_material_vertices)):
        theta = math.pi / 2 if i == 0 else math.radians(angle)
        ba = parts[-1]["first_bend_allowance_mm" if i == 0 else "second_bend_allowance_mm"]
        for material, world in zip(vertices, out.interface_vertices):
            x = -material.flat.x if mirror else material.flat.x
            y = material.flat.y
            u = -y if i == 0 else x
            linear = u - ba
            assert linear >= -1e-7
            assert u <= (20 if i == 0 else height) + 1e-7
            depth = -material.normal_offset_mm if mirror else material.normal_offset_mm
            assert abs(depth) <= 1 + 1e-7
            if i == 0:
                folded = (x, -1.5 + depth, 1.5 + linear)
            else:
                folded = (1.5 * math.sin(theta) + linear * math.cos(theta) + depth * math.sin(theta),
                          y,
                          1.5 * (1 - math.cos(theta)) + linear * math.sin(theta) - depth * math.cos(theta))
            if mirror:
                folded = (-folded[0], folded[1], folded[2])
            assert folded == pytest.approx(world, abs=1e-7)
    # 同一真正平面，三角形面積不靠欄位值冒充。
    area = 0
    for a, b, c in out.interface_triangles:
        u = tuple(b[j] - a[j] for j in range(3))
        v = tuple(c[j] - a[j] for j in range(3))
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        area += math.hypot(*cross) / 2
    assert area == pytest.approx(out.interface_area_mm2)
    assert all(math.isfinite(v) for p in out.interface_vertices for v in p)


@pytest.mark.parametrize("change", (
    {"first_inner_radius_mm": True},
    {"second_inner_radius_mm": float("nan")},
    {"first_bend_allowance_mm": .05},
    {"second_bend_allowance_mm": float("inf")},
))
def test_invalid_radius_allowance_are_not_invented(change):
    scene, first, second, params, calibration = source()
    calibration.update(change)
    with pytest.raises(GeometryError):
        api.solve_v_miter_radius_ba_mating_surface_trial(
            scene, first, second, **params, **calibration)


def test_radius_and_allowance_change_geometry_without_shortening_source():
    parts = source()
    old = solve(parts)
    scene, first, second, params, calibration = parts
    calibration = dict(calibration, first_inner_radius_mm=1, second_inner_radius_mm=1,
                       first_bend_allowance_mm=math.pi / 2 * 1.8,
                       second_bend_allowance_mm=math.pi / 2 * 1.8)
    new = solve((scene, first, second, params, calibration))
    assert new.interface_vertices != old.interface_vertices
    assert new.source_remaining_outline == old.source_remaining_outline
    assert new.first_neutral_axis_k == pytest.approx(.4)
    assert new.second_neutral_axis_k == pytest.approx(.4)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_project_save_reload_recomputes_same_uncertified_surface(tmp_path, family):
    from phase6_project_file import PROJECT_SCHEMA_V1, write_project, read_project
    from ae_engine.receiving_layout import new_receiving_layout

    scene, first, second, params, calibration = source()
    captured = api.capture_v_miter_relief_trial_snapshot(scene, first, second, **params)
    snapshot = dict(model=family, w=800, h=1600, d=350, t=2,
                    v_miter_trial_preview=captured,
                    v_miter_r_ba_trial_inputs=calibration)
    if family == "受電箱":
        snapshot.update(active_mode="set_bay", receiving_layout=new_receiving_layout(
            width=800, height=1600, depth=350))
    path = write_project(tmp_path / "接合面.p6fold",
                         {"schema": PROJECT_SCHEMA_V1, "snapshot": snapshot})
    saved = read_project(path)["snapshot"]
    api.replay_v_miter_relief_trial_snapshot(scene, saved["v_miter_trial_preview"])
    replay = api.solve_v_miter_radius_ba_mating_surface_trial(
        scene, first, second, **saved["v_miter_trial_preview"]["parameters"],
        **saved["v_miter_r_ba_trial_inputs"])
    assert replay == solve((scene, first, second, params, calibration))
    from ae_engine.sheetmetal_geometry_core import EDITABLE_CORNER_TYPE_IDS
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4
