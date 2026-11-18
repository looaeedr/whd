"""#3317 measured-R/BA trial removes detected true-T crossings without CNC promotion."""
from __future__ import annotations

import math
import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _source(angle=90, mode="RELIEF_HOLE"):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    inputs = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=angle,
        relief_mode=mode, relief_t_factor=1.5,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **inputs,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    outline = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y), Vec2(b.x, 0),
        Vec2(30, 10), Vec2(30, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    return DrawingScene([outline, first, second]), first, second, inputs


def _calibrated(angle=90, *, radius=0.5, k=0.4):
    t = 2
    return dict(
        first_inner_radius_mm=radius,
        second_inner_radius_mm=radius,
        first_bend_allowance_mm=(math.pi / 2) * (radius + k * t),
        second_bend_allowance_mm=math.radians(angle) * (radius + k * t),
        max_permitted_edge_trim_mm=12,
    )


def test_90deg_hole_real_radius_ba_trial_is_source_bound_and_only_uncertified():
    scene, first, second, args = _source(mode="RELIEF_HOLE")
    original = tuple(scene.primitives)
    calibrated = _calibrated()
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **calibrated,
    )
    assert trial.first_neutral_axis_k == pytest.approx(.4)
    assert trial.second_neutral_axis_k == pytest.approx(.4)
    assert trial.geometry_model.endswith("TRIM_TRIAL")
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.no_detected_noncoplanar_crossings
    assert trial.trimmed_surface_interference_pairs == 0
    assert 0 <= trial.first_edge_trim_mm <= 12
    assert trial.first_flat_trimmed_area_mm2 <= trial.first_flat_source_area_mm2
    assert trial.second_flat_source_area_mm2 > 0
    assert len(trial.first_thick_solid_triangles) > len(trial.first_formed_skin_triangles)
    assert len(trial.second_thick_solid_triangles) > len(trial.second_formed_skin_triangles)
    # This returned CHECK patch is NOT a canonical full-sheet CUTTING source.
    assert all(p.layer in {"BEND", "CUTTING"} for p in scene.primitives)
    assert tuple(scene.primitives) == original
    assert "V_MITER" not in [x.value for x in manufacturing_api.EDITABLE_CORNER_TYPE_IDS] if hasattr(manufacturing_api, "EDITABLE_CORNER_TYPE_IDS") else True


@pytest.mark.parametrize("angle", (90, 120))
def test_measured_radius_change_changes_actual_formed_arc_not_only_metadata(angle):
    scene, first, second, args = _source(angle)
    r1 = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(angle, radius=.5),
    )
    r2 = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(angle, radius=1.0),
    )
    assert r1.second_formed_skin_triangles != r2.second_formed_skin_triangles
    assert r1.manufacturing_status.endswith("UNCERTIFIED")
    assert r2.manufacturing_status.endswith("UNCERTIFIED")


@pytest.mark.parametrize("change", [
    {"first_inner_radius_mm": True},
    {"second_inner_radius_mm": float("nan")},
    {"first_bend_allowance_mm": float("inf")},
    {"first_bend_allowance_mm": .05},
    {"second_bend_allowance_mm": 500},
    {"max_permitted_edge_trim_mm": 0},
])
def test_invalid_measurements_or_missing_allowance_fail_closed(change):
    scene, first, second, args = _source()
    params = _calibrated()
    params.update(change)
    with pytest.raises(GeometryError):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **params,
        )


def test_cannot_use_detached_bend_or_invent_60deg_material_extension():
    scene, first, second, args = _source(90)
    clone = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, clone, second, **args, **_calibrated(),
        )
    scene, first, second, args = _source(60)
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(60),
        )


def test_compensation_does_not_promote_new_corner_type_or_cutting():
    from ae_engine.sheetmetal_geometry_core import CornerTypeId, EDITABLE_CORNER_TYPE_IDS
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4
    with pytest.raises(ValueError):
        CornerTypeId("V_MITER")



def test_real_round_R_thick_joint_keeps_R_BA_source_but_only_returns_check_candidate():
    # The original 1:1 taper failed this 90-degree, T=2 specimen with true
    # noncoplanar crossings. A *new shifted same-R tangency* now produces a
    # different candidate; verify actual 3D material rather than freezing
    # an old MUST-RAISE assertion as the geometry specification.
    from ae_engine.assembly_geometry import (
        detect_world_mesh_surface_interference,
        detect_world_mesh_enclosed_volume_witness,
    )
    scene, first, second, args = _source(mode="ROUND_R")
    before = tuple(scene.primitives)
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(),
    )
    assert trial.geometry_model.endswith("ASYMMETRIC_SAME_R_TANGENT_TRIM_TRIAL")
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.first_edge_trim_mm > 0
    assert trial.first_edge_trim_mm <= _calibrated()["max_permitted_edge_trim_mm"]
    assert trial.untrimmed_surface_interference_pairs > 0
    assert trial.trimmed_surface_interference_pairs == 0
    assert trial.full_corrected_check_outline
    assert len(trial.first_thick_solid_triangles) > len(trial.first_formed_skin_triangles)
    assert len(trial.second_thick_solid_triangles) > len(trial.second_formed_skin_triangles)
    assert not detect_world_mesh_surface_interference(
        trial.first_thick_solid_triangles, trial.second_thick_solid_triangles,
    ).has_interference
    assert not detect_world_mesh_enclosed_volume_witness(
        trial.first_thick_solid_triangles, trial.second_thick_solid_triangles,
    ).has_enclosed_overlap
    # No Factory R/K/BA, kerf or mating gap certificate is implied by zero
    # detected surface crossings / finite containment samples.
    assert tuple(scene.primitives) == before


def test_round_R_real_source_fails_closed_if_all_three_profiles_physically_cross(monkeypatch):
    from ae_engine import v_miter_radius_ba_interface_trial as owner
    from ae_engine.assembly_geometry import MeshInterferenceDiagnostic

    scene, first, second, args = _source(mode="ROUND_R")
    before = tuple(scene.primitives)
    # Keep the *real* source cutting, R/BA mesh and physical area gates,
    # forcing a definite world-space crossing for each candidate as a
    # separate negative control. A synthetic zero-mesh path must not be
    # upgraded into production clearance when the actual 3D gate reports a hit.
    segment = (((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    monkeypatch.setattr(
        owner, "detect_world_mesh_surface_interference",
        lambda *_: MeshInterferenceDiagnostic(
            (), segment[0], 7, segment,
        ),
    )
    with pytest.raises(owner.VMiterRadiusBAContactError, match="source-preserving") as caught:
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(),
        )
    failure = caught.value
    assert failure.original_noncoplanar_pairs == 7
    assert failure.attempted_noncoplanar_pairs == 7
    assert failure.attempted_intersection_segments == segment
    assert failure.manufacturing_status.endswith("UNCERTIFIED")
    assert failure.attempted_trim_mm == pytest.approx(12)
    assert tuple(scene.primitives) == before


def test_enclosed_3d_volume_blocks_radius_ba_trial_even_when_surface_detector_is_clear(monkeypatch):
    from ae_engine import v_miter_radius_ba_interface_trial as owner
    from ae_engine.assembly_geometry import MeshEnclosedVolumeDiagnostic

    scene, first, second, inputs = _source(mode="RELIEF_HOLE")
    original = tuple(scene.primitives)

    # The shared 3D detector has separately proven a real fully enclosed
    # cuboid can have zero surface-crossing pairs. Inject that positive
    # physical-volume witness after real source/R/BA/2D/3D preparation here.
    monkeypatch.setattr(
        owner, "detect_world_mesh_enclosed_volume_witness",
        lambda *_: MeshEnclosedVolumeDiagnostic(
            True, 1, ((1.0, 2.0, 3.0),),
        ),
    )
    with pytest.raises(owner.VMiterRadiusBAContactError, match="strictly enclosed") as caught:
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **inputs, **_calibrated(),
        )
    failure = caught.value
    assert failure.attempted_containment_points == ((1.0, 2.0, 3.0),)
    assert failure.attempted_noncoplanar_pairs == 0
    assert failure.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == original


def test_round_r_source_tip_profile_search_uses_actual_cutback_if_legacy_cannot_clear():
    from ae_engine.v_miter_radius_ba_interface_trial import (
        VMiterRadiusBAContactError, _search_round_r_source_tip_profiles,
    )

    visited = []

    def evaluate(trim, transition):
        visited.append((trim, transition))
        # A too-slow 1:1 ramp retains near-root overlap; a source-R-scaled
        # ramp clears it after a sufficient finite offset. Synthetic counts
        # verify routing only, not a manufacturing or volume certificate.
        pairs = 0 if trim >= 2 and transition is not None and transition <= 1 else 3
        return ("one_sheet", "real_skin", "solid", pairs, (), (), True)

    def contact_error(original, rejected, attempted):
        return VMiterRadiusBAContactError(
            "R source retains collision",
            original_pairs=original[3], attempted_pairs=rejected[3],
            attempted_segments=(), attempted_trim_mm=attempted,
        )

    original, best, selected, run, is_local = _search_round_r_source_tip_profiles(
        evaluate, 10, 1,
        failure_message="R source retains collision",
        failure_factory=contact_error,
    )
    assert is_local
    assert original[3] == 3 and best[3] == 0
    assert 2 <= selected <= 10
    assert run == pytest.approx(1)
    assert (10, None) in visited and (10, 1) in visited
    assert (0, None) in visited
    assert all(t is None or t <= offset for offset, t in visited)


def test_round_r_alternate_failure_keeps_original_collision_evidence():
    from ae_engine.v_miter_radius_ba_interface_trial import (
        VMiterRadiusBAContactError, _search_round_r_source_tip_profiles,
    )

    def evaluate(trim, run):
        return ("one_sheet", "skin", "solid", 7 if run is None else 6, (), (), True)

    def contact_error(original, rejected, attempted):
        return VMiterRadiusBAContactError(
            "R source retains collision",
            original_pairs=original[3], attempted_pairs=rejected[3],
            attempted_segments=(), attempted_trim_mm=attempted,
        )

    with pytest.raises(VMiterRadiusBAContactError, match="retains collision") as caught:
        _search_round_r_source_tip_profiles(
            evaluate, 12, 3, failure_message="R source retains collision",
            failure_factory=contact_error,
        )
    assert caught.value.attempted_noncoplanar_pairs == 7
    assert caught.value.attempted_trim_mm == pytest.approx(12)
