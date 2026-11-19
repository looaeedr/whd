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


def test_opt_in_smooth_r_ba_thickening_closes_shared_physical_hinge_vertices():
    from ae_engine.assembly_geometry import diagnose_world_mesh_triangle_edge_incidence
    from ae_engine.assembly_geometry_primitives import thicken_triangle_surface

    # Two truly shared source triangles meet on a non-coplanar hinge. A
    # per-face normal creates different T/2 skin vertices at the same
    # physical hinge and leaves an open shell. Opt-in smoothing uses one
    # source vertex and one T/2 offset for both incident faces.
    skin = (
        ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        ((1., 0., 0.), (1., 1., 1.), (0., 1., 0.)),
    )
    solid = thicken_triangle_surface(
        skin, 2., smooth_vertex_normals=True,
    )
    topo = diagnose_world_mesh_triangle_edge_incidence(solid)
    assert topo.edges_manifold_closed
    assert topo.boundary_edge_count == 0
    assert topo.nonmanifold_edge_count == 0
    assert topo.degenerate_triangle_count == 0
    # The legacy sharp-fold mode must remain callable and independent.
    assert thicken_triangle_surface(skin, 2.) != solid


@pytest.mark.parametrize("mode", ("RELIEF_HOLE", "ROUND_R"))
def test_true_source_r_ba_curved_shells_close_without_inventing_material(mode):
    from ae_engine.assembly_geometry import diagnose_world_mesh_triangle_edge_incidence

    scene, first, second, args = _source(mode=mode)
    original = tuple(scene.primitives)
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(),
    )
    for solid, reported_edges, reported_nonmanifold, reported_degenerate in (
        (trial.first_thick_solid_triangles,
         trial.first_thick_solid_boundary_edge_count,
         trial.first_thick_solid_nonmanifold_edge_count,
         trial.first_thick_solid_degenerate_triangle_count),
        (trial.second_thick_solid_triangles,
         trial.second_thick_solid_boundary_edge_count,
         trial.second_thick_solid_nonmanifold_edge_count,
         trial.second_thick_solid_degenerate_triangle_count),
    ):
        topological_truth = diagnose_world_mesh_triangle_edge_incidence(solid)
        assert reported_edges == topological_truth.boundary_edge_count == 0
        assert reported_nonmanifold == topological_truth.nonmanifold_edge_count == 0
        assert reported_degenerate == topological_truth.degenerate_triangle_count == 0
        assert topological_truth.edges_manifold_closed
    assert trial.formed_volume_containment_meshes_closed
    assert "SAMPLED_NO_POSITIVE_WITNESS" in trial.true_t_volume_check_status
    assert trial.first_source_cut_face.has_source_tagged_cut_faces
    assert trial.second_source_cut_face.has_source_tagged_cut_faces
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == original


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
    # A geometry CHECK candidate is NOT a full 3D volume-clear verdict.
    # Publish actual source mesh topology, never infer closure from zero hits.
    assert trial.true_t_volume_check_status.endswith("UNCERTIFIED")
    if trial.formed_volume_containment_meshes_closed:
        assert "SAMPLED_NO_POSITIVE_WITNESS" in trial.true_t_volume_check_status
    else:
        assert "UNKNOWN_OPEN_MESH" in trial.true_t_volume_check_status
        assert (
            trial.first_thick_solid_boundary_edge_count
            + trial.second_thick_solid_boundary_edge_count
            + trial.first_thick_solid_nonmanifold_edge_count
            + trial.second_thick_solid_nonmanifold_edge_count
            + trial.first_thick_solid_degenerate_triangle_count
            + trial.second_thick_solid_degenerate_triangle_count
        ) > 0
    # Real T-solid world sections are independent of local flat source XY.
    # Missing first/second section is NOT a zero contact gap.
    gap = trial.seam_section_gap_trial
    assert gap is not None
    assert gap.manufacturing_status == "V_MITER_SEAM_GAP_UNCERTIFIED"
    assert len(gap.sections) == 7
    assert gap.measured_section_count + gap.missing_section_count == 7
    first_cut = trial.first_source_cut_face
    second_cut = trial.second_source_cut_face
    assert first_cut is not None and second_cut is not None
    assert first_cut.manufacturing_status.endswith("UNCERTIFIED")
    assert second_cut.manufacturing_status.endswith("UNCERTIFIED")
    assert first_cut.source_new_v_cut_length_mm > 0
    assert second_cut.source_new_v_cut_length_mm > 0
    assert first_cut.selected_flat_v_cut_length_mm <= first_cut.source_new_v_cut_length_mm + 1e-6
    assert second_cut.selected_flat_v_cut_length_mm <= second_cut.source_new_v_cut_length_mm + 1e-6
    assert first_cut.has_source_tagged_cut_faces
    assert second_cut.has_source_tagged_cut_faces
    assert first_cut.formed_boundary_edge_count > 0
    assert second_cut.formed_boundary_edge_count > 0
    assert len(first_cut.true_cut_face_triangles) == first_cut.formed_boundary_edge_count * 2
    assert len(second_cut.true_cut_face_triangles) == second_cut.formed_boundary_edge_count * 2
    assert trial.source_cut_face_section_gap_trial is not None
    assert trial.source_cut_face_section_gap_trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.source_cut_face_section_gap_trial.measured_section_count + (
        trial.source_cut_face_section_gap_trial.missing_section_count
    ) == 7
    continuity = trial.source_cut_face_continuity_trial
    assert continuity is not None
    assert continuity.manufacturing_status.endswith("UNCERTIFIED")
    assert continuity.intervals
    assert continuity.both_face_interval_count + continuity.missing_face_interval_count == len(
        continuity.intervals
    )
    assert sum(span.length_mm for span in continuity.intervals) == pytest.approx(
        continuity.seam_length_mm
    )
    assert sum((
        continuity.both_face_span_mm, continuity.first_missing_span_mm,
        continuity.second_missing_span_mm, continuity.both_missing_span_mm,
    )) == pytest.approx(continuity.seam_length_mm)
    for span in continuity.intervals:
        if span.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK":
            assert span.has_both_cut_faces
            assert span.max_gap_lower_bound_mm <= span.midpoint_section.measured_gap_mm + 1e-5
            assert span.max_gap_upper_bound_mm >= span.midpoint_section.measured_gap_mm
            assert span.min_gap_lower_bound_mm <= span.midpoint_section.measured_gap_mm
            assert span.min_gap_upper_bound_mm >= span.midpoint_section.measured_gap_mm
        else:
            assert span.max_gap_upper_bound_mm is None
    if continuity.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK":
        assert continuity.missing_face_interval_count == 0
        assert continuity.max_gap_upper_bound_mm >= continuity.max_sampled_cut_face_gap_mm
        assert continuity.min_gap_lower_bound_mm <= continuity.min_sampled_cut_face_gap_mm
    else:
        assert continuity.max_gap_upper_bound_mm is None
    assert all(0 <= span.start_mm < span.end_mm <= continuity.seam_length_mm + 1e-6
               for span in continuity.intervals)
    assert all(span.start_fraction < span.midpoint_section.fraction < span.end_fraction
               for span in continuity.intervals)
    for section in gap.sections:
        assert 0 < section.fraction < 1
        assert section.station_mm > 0
        if section.status == "MEASURED":
            assert section.measured_gap_mm is not None
            assert section.measured_gap_mm >= 0
            assert section.nearest_first_xyz is not None
            assert section.nearest_second_xyz is not None
            assert math.dist(
                section.nearest_first_xyz, section.nearest_second_xyz,
            ) == pytest.approx(section.measured_gap_mm, abs=1e-6)
            # The independently source-datum-anchored seam points are
            # measured from the SAME true T-solid world 3D meshes.
            assert section.datum_anchored_gap_mm is not None
            assert section.datum_anchored_gap_mm >= section.measured_gap_mm - 1e-6
            assert section.datum_first_xyz is not None
            assert section.datum_second_xyz is not None
            assert math.dist(
                section.datum_first_xyz, section.datum_second_xyz,
            ) == pytest.approx(section.datum_anchored_gap_mm, abs=1e-6)
            assert section.datum_first_reach_mm >= 0
            assert section.datum_second_reach_mm >= 0
            assert section.datum_first_reach_mm <= section.global_first_reach_mm + 1e-6
            assert section.datum_second_reach_mm <= section.global_second_reach_mm + 1e-6
        else:
            assert section.measured_gap_mm is None
            assert section.nearest_first_xyz is None
            assert section.nearest_second_xyz is None
            assert section.datum_anchored_gap_mm is None
            assert section.datum_first_xyz is None
            assert section.datum_second_xyz is None
            assert not section.off_datum_shortcut
    assert gap.off_datum_shortcut_station_count == sum(
        1 for section in gap.sections if section.off_datum_shortcut
    )
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
    assert trial.true_t_volume_check_status.endswith("UNCERTIFIED")
    if not trial.formed_volume_containment_meshes_closed:
        assert "UNKNOWN_OPEN_MESH" in trial.true_t_volume_check_status
        assert (
            trial.first_thick_solid_boundary_edge_count
            + trial.second_thick_solid_boundary_edge_count
            + trial.first_thick_solid_nonmanifold_edge_count
            + trial.second_thick_solid_nonmanifold_edge_count
            + trial.first_thick_solid_degenerate_triangle_count
            + trial.second_thick_solid_degenerate_triangle_count
        ) > 0
    assert trial.full_corrected_check_outline
    assert trial.seam_section_gap_trial is not None
    assert trial.first_source_cut_face is not None
    assert trial.second_source_cut_face is not None
    assert trial.first_source_cut_face.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.second_source_cut_face.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.first_source_cut_face.has_source_tagged_cut_faces
    assert trial.second_source_cut_face.has_source_tagged_cut_faces
    assert trial.source_cut_face_section_gap_trial is not None
    assert trial.source_cut_face_section_gap_trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.source_cut_face_continuity_trial is not None
    assert trial.source_cut_face_continuity_trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.source_cut_face_continuity_trial.intervals
    assert sum(span.length_mm for span in trial.source_cut_face_continuity_trial.intervals) == pytest.approx(
        trial.source_cut_face_continuity_trial.seam_length_mm
    )
    assert trial.seam_section_gap_trial.geometry_model.endswith("SAMPLED_CHECK")
    assert trial.seam_section_gap_trial.off_datum_shortcut_station_count == sum(
        row.off_datum_shortcut for row in trial.seam_section_gap_trial.sections
    )
    assert trial.seam_section_gap_trial.measured_section_count + (
        trial.seam_section_gap_trial.missing_section_count
    ) == 7
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



def test_real_open_true_T_volume_is_explicitly_unknown_in_source_CHECK(monkeypatch):
    from ae_engine import v_miter_radius_ba_interface_trial as owner
    from ae_engine.assembly_geometry import MeshEnclosedVolumeDiagnostic

    scene, first, second, args = _source(mode="RELIEF_HOLE")
    original_primitives = tuple(scene.primitives)
    # Reuse the GENUINE source CUTTING, measured R/BA, curved 3D thickness
    # meshes and same CHECK-only trim solver. The independent strict-parity
    # checker reports an open shell; it cannot claim no penetration.
    monkeypatch.setattr(
        owner, "detect_world_mesh_enclosed_volume_witness",
        lambda *_: MeshEnclosedVolumeDiagnostic(False, 0, ()),
    )
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(),
    )
    assert trial.trimmed_surface_interference_pairs == 0
    assert trial.trimmed_enclosed_volume_witness_count == 0
    assert trial.formed_volume_containment_meshes_closed is False
    assert trial.true_t_volume_check_status == (
        "V_MITER_TRUE_T_VOLUME_UNKNOWN_OPEN_MESH_UNCERTIFIED"
    )
    # The mocked parity result is UNKNOWN independently of the *actual*
    # topology: the repaired R/BA source now yields a closed physical shell.
    # Never fabricate open edges just to agree with a parity failure.
    assert (
        trial.first_thick_solid_boundary_edge_count
        + trial.second_thick_solid_boundary_edge_count
        + trial.first_thick_solid_nonmanifold_edge_count
        + trial.second_thick_solid_nonmanifold_edge_count
        + trial.first_thick_solid_degenerate_triangle_count
        + trial.second_thick_solid_degenerate_triangle_count
    ) == 0
    assert len(trial.first_thick_solid_boundary_edge_examples_xyz) <= 8
    assert len(trial.second_thick_solid_boundary_edge_examples_xyz) <= 8
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == original_primitives
