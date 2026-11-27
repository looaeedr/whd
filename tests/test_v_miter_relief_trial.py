"""V-miter ROUND_R and RELIEF_HOLE actual geometry trials, not CNC approval."""
import math

import ezdxf
import pytest
from shapely.geometry import Point, Polygon

from ae_engine import manufacturing_api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_corner_source import VMiterReliefMode


def _source(angle):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), layer="BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), layer="BEND")
    args = dict(
        thickness_mm=2.0, first_flange_height_mm=20.0,
        second_flange_height_mm=30.0, second_fold_angle_deg=angle,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second,
        **args, relief_mode="ROUND_R",
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    original = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y),
        Vec2(b.x, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    return DrawingScene([original, first, second]), first, second, args


def _run(scene, first, second, args, mode, factor):
    return manufacturing_api.project_v_miter_relief_trial(
        scene, first, second, **args,
        relief_mode=mode, relief_t_factor=factor,
    )


@pytest.mark.parametrize("angle", [60, 90, 120])
def test_round_R_and_hole_change_real_material_contour_differently(angle):
    scene, first, second, args = _source(angle)
    before = list(scene.primitives)
    sharp = manufacturing_api.project_v_miter_source_material_trial(
        scene, first, second, **args, relief_mode="ROUND_R",
    )
    rounded = _run(scene, first, second, args, "ROUND_R", 1.5)
    hole = _run(scene, first, second, args, "RELIEF_HOLE", 1.5)
    assert rounded.relief_mode is VMiterReliefMode.ROUND_R
    assert hole.relief_mode is VMiterReliefMode.RELIEF_HOLE
    assert rounded.relief_t_factor == pytest.approx(1.5)
    assert rounded.relief_dimension_mm == pytest.approx(3)  # R = 1.5 T
    assert rounded.relief_radius_mm == pytest.approx(3)
    assert hole.relief_dimension_mm == pytest.approx(3)     # ØD = 1.5 T
    assert hole.relief_radius_mm == pytest.approx(1.5)
    assert rounded.removed_material_area_mm2 < sharp.removed_material_area_mm2
    assert hole.removed_material_area_mm2 > sharp.removed_material_area_mm2
    for candidate in (rounded, hole):
        remaining = Polygon((p.x, p.y) for p in candidate.trial_remaining_outline)
        assert remaining.is_valid and not remaining.interiors
        assert remaining.area == pytest.approx(candidate.remaining_material_area_mm2)
        assert candidate.remaining_material_area_mm2 > 0
        assert candidate.manufacturing_status == "V_MITER_RELIEF_CUTTING_UNCERTIFIED"
        assert candidate.source_trial.ideal.source.thickness_mm == pytest.approx(2)
    assert scene.primitives == before


def test_round_arc_has_true_tangent_points_and_relief_radius():
    scene, first, second, args = _source(90)
    rounded = _run(scene, first, second, args, "ROUND_R", 1.5)
    # Sharp tip A=(0,0), first V leg toward -Y and second leg toward +X.
    # For R=3, circle center is (3,-3); tangent points are (0,-3),(3,0).
    remaining = Polygon((p.x, p.y) for p in rounded.trial_remaining_outline)
    assert remaining.exterior.distance(Point(0, -3)) < 1e-6
    assert remaining.exterior.distance(Point(3, 0)) < 1e-6
    assert remaining.contains(Point(0, 0))  # Rounded tip leaves sharp apex as stock.
    assert not remaining.contains(Point(3, -3))  # Circle center is in cut material.


def test_hole_actual_circular_union_keeps_apex_removed_and_grows_notch():
    scene, first, second, args = _source(90)
    hole = _run(scene, first, second, args, "RELIEF_HOLE", 2)
    remaining = Polygon((p.x, p.y) for p in hole.trial_remaining_outline)
    assert hole.relief_radius_mm == pytest.approx(2)
    assert not remaining.covers(Point(0, 0))
    assert not remaining.contains(Point(-1.8, 0))


@pytest.mark.parametrize("mode", ["ROUND_R", "RELIEF_HOLE"])
def test_no_unknown_T_multipliers_are_assumed(mode):
    scene, first, second, args = _source(90)
    with pytest.raises(GeometryError, match="explicit trial factor"):
        manufacturing_api.project_v_miter_relief_trial(
            scene, first, second, **args, relief_mode=mode,
        )


@pytest.mark.parametrize("mode", ["ROUND_R", "RELIEF_HOLE"])
def test_oversized_tip_refuses_to_destroy_original_sheet(mode):
    scene, first, second, args = _source(90)
    with pytest.raises(GeometryError, match="exceeds"):
        _run(scene, first, second, args, mode, 50)


@pytest.mark.parametrize("mode", ["ROUND_R", "RELIEF_HOLE"])
def test_invalid_T_ratio_rejected_without_mutating_source(mode):
    scene, first, second, args = _source(90)
    for factor in (-1, 0, float("nan"), float("inf"), True, "invalid"):
        with pytest.raises(GeometryError):
            _run(scene, first, second, args, mode, factor)
    assert len(scene.primitives) == 3


@pytest.mark.parametrize("mode", ["ROUND_R", "RELIEF_HOLE"])
def test_relief_trial_dxf_reopens_as_datum_and_check_only(mode, tmp_path):
    scene, first, second, args = _source(120)
    candidate = _run(scene, first, second, args, mode, 1.25)
    preview = manufacturing_api.build_v_miter_relief_trial_check_scene(
        scene, first, second, **args,
        relief_mode=mode, relief_t_factor=1.25,
    )
    assert scene.primitives[0].layer == "CUTTING"  # input source untouched
    assert [p.layer for p in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[1].points == candidate.trial_remaining_outline
    target = tmp_path / f"{mode}_candidate_check.dxf"
    save_scene_dxf(target, preview)
    dxf = ezdxf.readfile(target)
    entities = list(dxf.modelspace())
    assert [e.dxf.layer for e in entities] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert all(e.dxf.layer not in {"CUTTING", "MARKING", "BEND"}
               for e in entities)
    expected = [(p.x, p.y) for p in candidate.trial_remaining_outline]
    got = [(x, y) for x, y in entities[1].get_points("xy")]
    assert len(got) == len(expected)
    for actual, wanted in zip(got, expected):
        assert actual == pytest.approx(wanted)


def test_forged_bend_is_rejected_even_if_coordinates_match():
    scene, first, second, args = _source(90)
    forged = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        _run(scene, forged, second, args, "RELIEF_HOLE", 1.5)



def _folded_first_for_90_source(point):
    # Canonical test fold: first BEND axis points -X, flange starts toward -Y.
    return (point.x, 0.0, -point.y)


def _folded_second_for_90_source(point, angle):
    # Second BEND points +Y, flange starts toward +X, rises into +Z.
    theta = math.radians(angle)
    return (point.x * math.cos(theta), point.y, point.x * math.sin(theta))


@pytest.mark.parametrize("angle", (60, 90, 120))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_both_relief_modes_shift_3d_shared_contact_start_consistent_with_2d(angle, mode):
    scene, first, second, args = _source(angle)
    before = list(scene.primitives)
    contact = manufacturing_api.project_v_miter_relief_mating_trial(
        scene, first, second, **args,
        relief_mode=mode, relief_t_factor=1.5,
    )
    ideal = contact.relief.source_trial.ideal
    offset = (
        (args["thickness_mm"] * 1.5) /
        math.tan(math.radians(angle) / 2)
        if mode == "ROUND_R" else args["thickness_mm"] * 1.5 / 2
    )
    assert contact.manufacturing_status == "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED"
    assert contact.relief.flat_leg_tip_cutback_mm == pytest.approx(offset)
    assert contact.formed_open_relief_length_mm == pytest.approx(offset)
    assert contact.formed_contact_length_mm == pytest.approx(
        ideal.formed_contact_length_mm - offset
    )
    assert contact.formed_contact_length_mm > 0
    assert contact.formed_contact_end == ideal.formed_seam_end
    assert math.dist(contact.formed_contact_start, ideal.formed_seam_start) == pytest.approx(offset)
    assert _folded_first_for_90_source(
        contact.first_flat_contact_start
    ) == pytest.approx(contact.formed_contact_start, abs=1e-7)
    assert _folded_second_for_90_source(
        contact.second_flat_contact_start, angle
    ) == pytest.approx(contact.formed_contact_start, abs=1e-7)
    assert scene.primitives == before


def test_round_R_has_larger_open_tip_than_same_T_multiple_hole_for_90_degree_bend():
    scene, first, second, args = _source(90)
    rounded = manufacturing_api.project_v_miter_relief_mating_trial(
        scene, first, second, **args,
        relief_mode="ROUND_R", relief_t_factor=2,
    )
    hole = manufacturing_api.project_v_miter_relief_mating_trial(
        scene, first, second, **args,
        relief_mode="RELIEF_HOLE", relief_t_factor=2,
    )
    assert rounded.formed_open_relief_length_mm == pytest.approx(4)
    assert hole.formed_open_relief_length_mm == pytest.approx(2)
    assert rounded.formed_contact_length_mm == pytest.approx(16)
    assert hole.formed_contact_length_mm == pytest.approx(18)


def test_3d_mating_trial_preserves_trial_check_dxf_2d_source(tmp_path):
    scene, first, second, args = _source(120)
    mating = manufacturing_api.project_v_miter_relief_mating_trial(
        scene, first, second, **args, relief_mode="ROUND_R",
        relief_t_factor=1,
    )
    preview = manufacturing_api.build_v_miter_relief_trial_check_scene(
        scene, first, second, **args, relief_mode="ROUND_R",
        relief_t_factor=1,
    )
    assert preview.primitives[1].points == mating.relief.trial_remaining_outline
    out = tmp_path / "reconciled_2d3d_check.dxf"
    save_scene_dxf(out, preview)
    dxf = ezdxf.readfile(out)
    check = [entity for entity in dxf.modelspace() if entity.dxf.layer == "CHECK"]
    assert len(check) == 1
    assert len(check[0].get_points("xy")) == len(mating.relief.trial_remaining_outline)
    assert not any(entity.dxf.layer in {"CUTTING", "BEND", "MARKING"}
                   for entity in dxf.modelspace())


def test_missing_trial_multiplier_blocks_3d_mating_without_source_mutation():
    scene, first, second, args = _source(90)
    original = list(scene.primitives)
    with pytest.raises(GeometryError, match="explicit trial factor"):
        manufacturing_api.project_v_miter_relief_mating_trial(
            scene, first, second, **args, relief_mode="ROUND_R",
        )
    assert scene.primitives == original
