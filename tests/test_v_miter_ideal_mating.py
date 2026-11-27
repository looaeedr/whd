"""#3317 formed-plane V-miter diagnostic; no false manufacturing approval."""
import math

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_ideal_mating import VMiterIdealMatingCandidate


def _corner(*, second_to=(0, 100), mirror=False):
    sign = -1 if mirror else 1
    first = LinePrimitive(Vec2(-100 * sign, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(second_to[0] * sign, second_to[1]), "BEND")
    return DrawingScene([first, second]), first, second


def _project(*, angle=90, heights=(20, 30), second_to=(0, 100), mirror=False):
    scene, first, second = _corner(second_to=second_to, mirror=mirror)
    candidate = manufacturing_api.project_ideal_v_miter_mating_candidate(
        scene, first, second,
        thickness_mm=2,
        first_flange_height_mm=heights[0],
        second_flange_height_mm=heights[1],
        second_fold_angle_deg=angle,
        relief_mode="ROUND_R",
    )
    return scene, candidate


def _formed_first(point):
    # For test axes first -X and outward -Y, 90-degree fold maps -Y to +Z.
    return (point.x, 0.0, -point.y)


def _formed_second(point, angle):
    # For test axes second +Y and outward +X.
    theta = math.radians(angle)
    return (point.x * math.cos(theta), point.y, point.x * math.sin(theta))


@pytest.mark.parametrize("angle", (60, 90, 120))
def test_ideal_3d_shared_edge_inverts_to_both_flat_miter_rays(angle):
    scene, result = _project(angle=angle)
    assert isinstance(result, VMiterIdealMatingCandidate)
    assert result.geometry_model == "IDEAL_SHARP_ZERO_RADIUS_MID_SURFACE_ONLY"
    assert result.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"
    assert result.source.first_fold_angle_deg == 90
    assert result.source.second_fold_angle_deg == angle
    first = result.first_flat_miter_ray[1]
    second = result.second_flat_miter_ray[1]
    assert _formed_first(first) == pytest.approx(result.formed_seam_end, abs=1e-7)
    assert _formed_second(second, angle) == pytest.approx(result.formed_seam_end, abs=1e-7)
    assert result.first_flat_height_reached_mm == pytest.approx(20)
    assert result.second_flat_height_reached_mm <= 30 + 1e-8
    # The ideal diagnostic does not add any CUTTING layer, leak a fabricated
    # V polygon, or mutate the source scene.
    assert len(scene.primitives) == 2
    assert all(p.layer == "BEND" for p in scene.primitives)


def test_variable_second_angle_changes_first_unfolded_cut_ray():
    first_60 = _project(angle=60)[1].first_flat_miter_ray[1]
    first_90 = _project(angle=90)[1].first_flat_miter_ray[1]
    first_120 = _project(angle=120)[1].first_flat_miter_ray[1]
    assert first_60.x == pytest.approx(20 / math.sqrt(3))
    assert first_90.x == pytest.approx(0, abs=1e-8)
    assert first_120.x == pytest.approx(-20 / math.sqrt(3))
    assert first_60.y == pytest.approx(-20)
    assert first_90.y == pytest.approx(-20)
    assert first_120.y == pytest.approx(-20)


def test_unequal_heights_limit_shared_mating_seam_but_do_not_trim_tall_flange():
    small_first = _project(angle=90, heights=(20, 30))[1]
    small_second = _project(angle=90, heights=(30, 20))[1]
    assert small_first.formed_contact_length_mm == pytest.approx(20)
    assert small_second.formed_contact_length_mm == pytest.approx(20)
    assert small_first.source.second_flange_height_mm == 30
    assert small_second.source.first_flange_height_mm == 30
    assert small_first.first_flat_miter_ray[1].y == pytest.approx(-20)
    assert small_second.first_flat_miter_ray[1].y == pytest.approx(-20)


@pytest.mark.parametrize("angle", [60, 90, 120])
def test_x_mirror_preserves_contact_and_mirrors_both_flat_rays(angle):
    original = _project(angle=angle)[1]
    mirrored = _project(angle=angle, mirror=True)[1]
    assert mirrored.formed_contact_length_mm == pytest.approx(original.formed_contact_length_mm)
    for name in ("first_flat_miter_ray", "second_flat_miter_ray"):
        a = getattr(original, name)[1]
        b = getattr(mirrored, name)[1]
        assert b.x == pytest.approx(-a.x)
        assert b.y == pytest.approx(a.y)


def test_oblique_bend_source_gives_both_flat_rays_without_orthogonal_assumption():
    _, result = _project(angle=60, second_to=(100, 100))
    assert result.source.flat_bend_line_angle_deg == pytest.approx(45)
    assert result.first_flat_height_reached_mm == pytest.approx(20)
    assert result.second_flat_height_reached_mm > 0
    assert result.second_flat_miter_ray[1].y != pytest.approx(0)
    assert result.formed_seam_end[2] > 0


@pytest.mark.parametrize("angle", (60, 90, 120))
def test_both_relief_choices_remain_candidates_without_r_or_hole_cut(angle):
    scene, first, second = _corner()
    for mode in ("ROUND_R", "RELIEF_HOLE"):
        proposal = manufacturing_api.project_ideal_v_miter_mating_candidate(
            scene, first, second, thickness_mm=2,
            first_flange_height_mm=20,
            second_flange_height_mm=30, second_fold_angle_deg=angle,
            relief_mode=mode, relief_t_factor=1.5,
        )
        assert proposal.source.relief_t_factor == 1.5
        assert proposal.source.relief_mode == mode
        assert proposal.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"


def test_crossing_bend_lines_mid_segment_do_not_guess_flange_material_side():
    first = LinePrimitive(Vec2(-100, 0), Vec2(100, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    with pytest.raises(GeometryError, match="bend endpoint"):
        manufacturing_api.project_ideal_v_miter_mating_candidate(
            DrawingScene([first, second]), first, second, thickness_mm=2,
            first_flange_height_mm=20, second_flange_height_mm=20,
            second_fold_angle_deg=90, relief_mode="ROUND_R",
        )


def test_source_with_no_two_positive_contact_rays_refuses_ideal_projection():
    scene, first, second = _corner()
    # Both BEND segments must be sourced, not a copied/guessed coordinate.
    fake = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.project_ideal_v_miter_mating_candidate(
            scene, fake, second, thickness_mm=2,
            first_flange_height_mm=20, second_flange_height_mm=20,
            second_fold_angle_deg=90, relief_mode="ROUND_R",
        )
