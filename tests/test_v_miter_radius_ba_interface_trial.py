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


def test_v_miter_true_source_self_intersection_gate_retains_valid_check(monkeypatch):
    from ae_engine import assembly_geometry as geo
    from ae_engine import v_miter_radius_ba_interface_trial as owner

    genuine = geo.diagnose_world_mesh_self_intersections
    invalid = []

    def observed(mesh, *, tolerance=None):
        result = genuine(mesh, tolerance=tolerance)
        if not result.permits_strict_volume_sampling and len(invalid) < 4:
            pair = result.first_source_triangle_pair
            sample = (mesh[pair[0]], mesh[pair[1]]) if pair else ()
            invalid.append((len(mesh), result, sample))
        return result

    monkeypatch.setattr(geo, "diagnose_world_mesh_self_intersections", observed)
    scene, first, second, args = _source(mode="RELIEF_HOLE")
    try:
        result = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(),
        )
    except owner.VMiterRadiusBAContactError:
        pytest.fail("real physical source was rejected: " + repr(invalid))
    assert result.formed_volume_containment_meshes_closed


def test_measured_cylindrical_radials_do_not_depend_on_skin_triangle_aspect_ratio():
    from shapely.geometry import box
    from ae_engine.assembly_geometry import (
        diagnose_world_mesh_triangle_edge_incidence,
        diagnose_world_mesh_self_intersections,
    )
    from ae_engine.assembly_geometry_primitives import thicken_triangle_surface
    from ae_engine.v_miter_radius_ba_interface_trial import (
        _formed_curved_skin, _measured_cylindrical_half_t_offsets,
    )
    from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES

    t, r, theta = 2.0, 0.5, math.pi / 2
    ba = theta * (r + .4 * t)
    apex = Vec2(0, 0)
    outside = (0.0, 1.0, 0.0)
    skin, flat = _formed_curved_skin(
        box(0, 0, 100, 20), apex,
        (1.0, 0.0, 0.0), outside,
        angle_rad=theta, inner_r=r,
        allowance=ba, thickness=t,
        axial_span=100, flange_height=20,
        return_flat_pairs=True,
    )
    radial = _measured_cylindrical_half_t_offsets(
        flat, skin, apex=apex, outside=outside,
        angle_rad=theta, allowance=ba, thickness=t,
    )
    tol = PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    for row_flat, row_world in zip(flat, skin):
        for (_, u), point in zip(row_flat, row_world):
            key = tuple(int(round(float(v) / tol)) for v in point)
            phi = min(theta, max(0.0, u / (ba / theta)))
            assert radial[key] == pytest.approx(
                (0, -math.sin(phi), math.cos(phi)), abs=1e-7,
            )
    solid = thicken_triangle_surface(
        skin, t, smooth_vertex_normals=True,
        physical_vertex_offsets=radial,
    )
    assert diagnose_world_mesh_triangle_edge_incidence(solid).edges_manifold_closed
    assert diagnose_world_mesh_self_intersections(solid).permits_strict_volume_sampling


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
    from ae_engine.assembly_geometry import (
        diagnose_world_mesh_triangle_edge_incidence,
        diagnose_world_mesh_self_intersections,
    )

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
        assert topological_truth.nonmanifold_vertex_count == 0
        assert topological_truth.nonmanifold_vertex_examples_xyz == ()
        assert reported_degenerate == topological_truth.degenerate_triangle_count == 0
        assert topological_truth.edges_manifold_closed
        # Closed source vertex links alone would still admit two crossing
        # manifold shells. The ORIGINAL R/Hole true-T geometry must also
        # have no detected forbidden non-neighbor surface intersections.
        own_surface = diagnose_world_mesh_self_intersections(solid)
        assert own_surface.permits_strict_volume_sampling
        assert own_surface.crossing_pair_count == 0
        assert own_surface.coplanar_overlap_pair_count == 0
        assert not own_surface.numerical_budget_exhausted
    assert trial.formed_volume_containment_meshes_closed
    assert "SAMPLED_NO_POSITIVE_WITNESS" in trial.true_t_volume_check_status
    assert trial.first_source_cut_face.has_source_tagged_cut_faces
    assert trial.second_source_cut_face.has_source_tagged_cut_faces
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == original


@pytest.mark.parametrize("mode", ("RELIEF_HOLE", "ROUND_R"))
@pytest.mark.parametrize("angle", (90, 120))
def test_real_source_trial_requires_closed_verified_true_t_volume_before_check(mode, angle):
    # The repaired R/BA true-T shells must be accepted based on the ACTUAL
    # strict-closure detector, not just zero noncoplanar intersections.
    scene, first, second, args = _source(angle=angle, mode=mode)
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(angle),
    )
    assert trial.formed_volume_containment_meshes_closed
    assert trial.first_thick_solid_boundary_edge_count == 0
    assert trial.second_thick_solid_boundary_edge_count == 0
    assert trial.trimmed_surface_interference_pairs == 0
    assert trial.trimmed_enclosed_volume_witness_count == 0
    assert trial.true_t_volume_check_status == (
        "V_MITER_TRUE_T_VOLUME_SAMPLED_NO_POSITIVE_WITNESS_UNCERTIFIED"
    )
    assert trial.manufacturing_status.endswith("UNCERTIFIED")


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



def _60_reverse_source_for_measured_rba(*, mode="RELIEF_HOLE", mirror=False):
    scene, first, second, inputs = _source(angle=60, mode=mode)
    if mirror:
        original = scene.primitives[0]
        original = PolylinePrimitive(
            tuple(Vec2(-p.x, p.y) for p in original.points),
            "CUTTING", closed=True,
        )
        first = LinePrimitive(Vec2(100, 0), Vec2(0, 0), "BEND")
        second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
        scene = DrawingScene([original, first, second])
    sign = -1 if mirror else 1
    extra = LinePrimitive(Vec2(0, 0), Vec2(sign * 20, 0), "BEND")
    scene.primitives.append(extra)
    return scene, first, second, extra, inputs


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("mirror", (False, True))
def test_60_measured_rba_curves_every_verified_real_reverse_bend_component(mode, mirror):
    scene, first, second, extra, inputs = _60_reverse_source_for_measured_rba(
        mode=mode, mirror=mirror,
    )
    initial = tuple(scene.primitives)
    measured = manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
        scene, first, second, **inputs, **{
            key: value for key, value in _calibrated(60).items()
            if key != "max_permitted_edge_trim_mm"
        }, second_leg_outer_perimeter_retract_mm=6,
    )
    sharp = manufacturing_api.diagnose_v_miter_reverse_crease_true_t_trial(
        scene, first, second, **inputs, second_leg_outer_perimeter_retract_mm=6,
    )
    assert measured.manufacturing_status == "V_MITER_REVERSE_CREASE_R_BA_UNCERTIFIED"
    assert measured.geometry_model.endswith("CYLINDRICAL_T_CHECK")
    assert measured.reverse_actual_bend_start_axial_mm == pytest.approx(-20)
    assert measured.first_actual_bend_end_axial_mm == pytest.approx(100)
    assert measured.second_actual_bend_end_axial_mm == pytest.approx(100)
    expected_components = 1 if mode == "ROUND_R" else 2
    assert len(measured.first_component_flat_areas_mm2) == expected_components
    assert measured.first_component_flat_areas_mm2 == pytest.approx(
        sharp.first_component_flat_areas_mm2
    )
    assert measured.first_component_real_bend_attachment_mm == pytest.approx(
        sharp.first_component_real_bend_attachment_mm
    )
    assert measured.first_flat_source_area_mm2 == pytest.approx(
        sharp.first_flange_flat_area_mm2
    )
    assert measured.second_flat_source_area_mm2 == pytest.approx(
        sharp.second_flange_flat_area_mm2
    )
    assert measured.source_cut_remaining_outline == sharp.cut.candidate_remaining_outline
    assert measured.first_formed_curved_skin_triangles
    assert measured.second_formed_curved_skin_triangles
    # Cylinder T/BA arc cannot silently reuse the old sharp-fold vertices.
    assert measured.first_formed_curved_skin_triangles != sharp.first_formed_skin_triangles
    assert measured.second_formed_curved_skin_triangles != sharp.second_formed_skin_triangles
    assert len(measured.first_thick_curved_solid_triangles) > len(
        measured.first_formed_curved_skin_triangles
    )
    assert len(measured.second_thick_curved_solid_triangles) > len(
        measured.second_formed_curved_skin_triangles
    )
    assert measured.surface_interference_pair_count >= 0
    assert measured.true_t_volume_check_status.endswith("UNCERTIFIED")
    # This is the NEW 60-degree asymmetric actual CUTTING sidewall, not
    # an inverse projection onto the obsolete ideal V-contact line.
    first_cut, second_cut = measured.first_source_cut_face, measured.second_source_cut_face
    assert first_cut is not None and second_cut is not None
    assert first_cut.manufacturing_status == "V_MITER_TRUE_CUT_FACE_UNCERTIFIED"
    assert second_cut.manufacturing_status == first_cut.manufacturing_status
    assert first_cut.source_new_v_cut_length_mm > 0
    assert second_cut.source_new_v_cut_length_mm == pytest.approx(
        first_cut.source_new_v_cut_length_mm
    )
    # A real positive-length 3D CUTTING sidewall must be recovered on
    # BOTH physical flanges, not a plausible empty status-only witness.
    assert first_cut.has_source_tagged_cut_faces
    assert first_cut.selected_flat_v_cut_length_mm > 0
    if mode == "ROUND_R":
        # Root-connected ROUND_R geometry preserves the first real V
        # source sidewall, but the second flange has NO selected 3D
        # V cut-face from this actual asymmetric source: this physical
        # topology is NOT a two-face mating seam and must stay blocked.
        assert second_cut.has_source_tagged_cut_faces is False
        assert second_cut.selected_flat_v_cut_length_mm == pytest.approx(0)
        assert measured.source_cut_face_coverage_status == "FIRST_ONLY_SOURCE_CUT_FACE"
    else:
        # Explicit source hole removes the root and leaves genuine
        # independently verifiable physical cut faces on both flanges.
        assert second_cut.has_source_tagged_cut_faces
        assert second_cut.selected_flat_v_cut_length_mm > 0
        assert measured.source_cut_face_coverage_status == "BOTH_SOURCE_CUT_FACES_IDENTIFIED"
    assert first_cut.selected_flat_v_cut_length_mm <= first_cut.source_new_v_cut_length_mm + 1e-6
    assert second_cut.selected_flat_v_cut_length_mm <= second_cut.source_new_v_cut_length_mm + 1e-6
    assert len(first_cut.true_cut_face_triangles) == 2 * first_cut.formed_boundary_edge_count
    assert len(second_cut.true_cut_face_triangles) == 2 * second_cut.formed_boundary_edge_count
    assert measured.source_cut_face_coverage_status == (
        "BOTH_SOURCE_CUT_FACES_IDENTIFIED"
        if first_cut.has_source_tagged_cut_faces and second_cut.has_source_tagged_cut_faces else
        "FIRST_ONLY_SOURCE_CUT_FACE"
        if first_cut.has_source_tagged_cut_faces else
        "SECOND_ONLY_SOURCE_CUT_FACE"
        if second_cut.has_source_tagged_cut_faces else
        "NO_SOURCE_CUT_FACES_IDENTIFIED"
    )
    assert all(math.isfinite(v) for tri in (
        measured.first_thick_curved_solid_triangles +
        measured.second_thick_curved_solid_triangles
    ) for point in tri for v in point)
    assert tuple(scene.primitives) == initial
    # Old ideal-mate R/BA output may not be a substitute for this new
    # physical reversed-source geometry; preserve its strict rejection.
    with pytest.raises(GeometryError, match="source material extension"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **inputs, **_calibrated(60),
        )


def test_60_round_r_missing_second_physical_cut_face_cannot_claim_seam_gap():
    from ae_engine.v_miter_cut_face_continuity_trial import (
        project_v_miter_true_cut_face_continuity_trial,
    )
    scene, first, second, extra, inputs = _60_reverse_source_for_measured_rba(
        mode="ROUND_R",
    )
    result = manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
        scene, first, second, **inputs,
        second_leg_outer_perimeter_retract_mm=6,
        **{k: v for k, v in _calibrated(60).items()
           if k != "max_permitted_edge_trim_mm"},
    )
    assert result.source_cut_face_coverage_status == "FIRST_ONLY_SOURCE_CUT_FACE"
    assert result.second_source_cut_face.true_cut_face_triangles == ()
    # The still-obsolete ideal seam MUST NOT be used as proof of
    # correction. The shared actual-face continuity Engine rejects an
    # absent sidewall, even when a caller supplies plausible seam points.
    with pytest.raises(GeometryError, match="second V-cut face|mesh|cut-face"):
        project_v_miter_true_cut_face_continuity_trial(
            result.first_source_cut_face.true_cut_face_triangles,
            result.second_source_cut_face.true_cut_face_triangles,
            formed_seam_start=(0.0, 0.0, 0.0),
            formed_seam_end=(0.0, 0.0, 20.0),
        )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_60_reverse_actual_v_cut_face_owner_receives_exact_original_stock_and_curved_t(
    monkeypatch, mode,
):
    from shapely.geometry import Polygon
    from ae_engine import v_miter_radius_ba_interface_trial as owner
    from ae_engine.v_miter_material_trial import _single_source_material
    from ae_engine.v_miter_source_cut_face_trial import trace_v_miter_source_true_t_cut_faces

    scene, first, second, extra, params = _60_reverse_source_for_measured_rba(
        mode=mode,
    )
    actual_original = _single_source_material(scene)
    before = tuple(scene.primitives)
    seen = []

    def provenance(original, altered, flat, skin, solid, *, thickness_mm, physical_vertex_offsets):
        assert original.equals_exact(actual_original, 1e-9)
        assert altered.area < original.area
        assert altered.difference(original).area == pytest.approx(0)
        assert flat and len(flat) == len(skin) and solid
        assert thickness_mm == pytest.approx(2)
        assert physical_vertex_offsets
        checked = trace_v_miter_source_true_t_cut_faces(
            original, altered, flat, skin, solid,
            thickness_mm=thickness_mm,
            physical_vertex_offsets=physical_vertex_offsets,
        )
        seen.append((altered, checked))
        return checked

    monkeypatch.setattr(owner, "trace_v_miter_source_true_t_cut_faces", provenance)
    out = manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
        scene, first, second, **params,
        second_leg_outer_perimeter_retract_mm=6,
        **{k: v for k, v in _calibrated(60).items()
           if k != "max_permitted_edge_trim_mm"},
    )
    assert len(seen) == 2
    expected_remaining = Polygon((p.x, p.y) for p in out.source_cut_remaining_outline)
    for altered, checked in seen:
        assert altered.equals(expected_remaining)
        assert checked.source_new_v_cut_length_mm > 0
    assert out.first_source_cut_face == seen[0][1]
    assert out.second_source_cut_face == seen[1][1]
    assert tuple(scene.primitives) == before


def test_60_reverse_measured_rba_cut_face_fails_when_real_t_sidewall_is_missing(monkeypatch):
    from ae_engine import v_miter_radius_ba_interface_trial as owner
    from ae_engine.v_miter_source_cut_face_trial import trace_v_miter_source_true_t_cut_faces

    scene, first, second, extra, args = _60_reverse_source_for_measured_rba()
    original = tuple(scene.primitives)
    hit = []

    def tamper_cut_wall(stock, altered, flats, formed, thick, *, thickness_mm, physical_vertex_offsets):
        real = trace_v_miter_source_true_t_cut_faces(
            stock, altered, flats, formed, thick,
            thickness_mm=thickness_mm,
            physical_vertex_offsets=physical_vertex_offsets,
        )
        if not hit:
            # The genuine 3D cut-wall is present in the physical mesh.
            # Deleting one actual wall triangle must never generate a
            # fabricated cut-face witness or a fake positive clearance.
            assert real.true_cut_face_triangles
            wall = real.true_cut_face_triangles[0]
            damaged = tuple(
                tri for tri in thick if set(tri) != set(wall)
            )
            assert len(damaged) == len(thick) - 1
            hit.append(True)
            return trace_v_miter_source_true_t_cut_faces(
                stock, altered, flats, formed, damaged,
                thickness_mm=thickness_mm,
                physical_vertex_offsets=physical_vertex_offsets,
            )
        return real

    monkeypatch.setattr(owner, "trace_v_miter_source_true_t_cut_faces", tamper_cut_wall)
    with pytest.raises(GeometryError, match="not a physical T-solid sidewall"):
        manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
            scene, first, second, **args,
            second_leg_outer_perimeter_retract_mm=6,
            **{k: v for k, v in _calibrated(60).items()
               if k != "max_permitted_edge_trim_mm"},
        )
    assert hit == [True]
    assert tuple(scene.primitives) == original


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_60_measured_reverse_curved_mesh_is_sensitive_to_actual_r_and_ba(mode):
    scene, first, second, extra, inputs = _60_reverse_source_for_measured_rba(
        mode=mode,
    )
    def solve(radius):
        measurements = {
            key: value for key, value in _calibrated(60, radius=radius).items()
            if key != "max_permitted_edge_trim_mm"
        }
        return manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
            scene, first, second, **inputs, **measurements,
            second_leg_outer_perimeter_retract_mm=6,
        )
    small, large = solve(.5), solve(1.0)
    assert small.first_neutral_axis_k == pytest.approx(.4)
    assert large.first_neutral_axis_k == pytest.approx(.4)
    assert small.first_flat_source_area_mm2 == pytest.approx(large.first_flat_source_area_mm2)
    assert small.second_flat_source_area_mm2 == pytest.approx(large.second_flat_source_area_mm2)
    assert small.source_cut_remaining_outline == large.source_cut_remaining_outline
    assert small.first_formed_curved_skin_triangles != large.first_formed_curved_skin_triangles
    assert small.second_formed_curved_skin_triangles != large.second_formed_curved_skin_triangles
    assert small.first_thick_curved_solid_triangles != large.first_thick_curved_solid_triangles


@pytest.mark.parametrize("kind", ("none", "short", "gap", "offset", "cross"))
def test_60_reverse_measured_curve_refuses_nonphysical_bend_source(kind):
    scene, first, second, extra, inputs = _60_reverse_source_for_measured_rba()
    scene.primitives.remove(extra)
    if kind == "short":
        scene.primitives.append(LinePrimitive(Vec2(0, 0), Vec2(5, 0), "BEND"))
    elif kind == "gap":
        scene.primitives.extend([
            LinePrimitive(Vec2(0, 0), Vec2(5, 0), "BEND"),
            LinePrimitive(Vec2(6, 0), Vec2(20, 0), "BEND"),
        ])
    elif kind == "offset":
        scene.primitives.append(LinePrimitive(Vec2(0, .01), Vec2(20, .01), "BEND"))
    elif kind == "cross":
        scene.primitives.append(LinePrimitive(Vec2(6, -10), Vec2(6, 10), "BEND"))
    with pytest.raises(GeometryError, match="real continuous BEND"):
        manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
            scene, first, second, **inputs, **{
                key: val for key, val in _calibrated(60).items()
                if key != "max_permitted_edge_trim_mm"
            }, second_leg_outer_perimeter_retract_mm=6,
        )


@pytest.mark.parametrize("bad", ("negative_radius", "zero_ba", "inconsistent_ba"))
def test_60_reverse_measured_curve_requires_independent_valid_r_ba(bad):
    scene, first, second, extra, inputs = _60_reverse_source_for_measured_rba()
    measured = {
        key: val for key, val in _calibrated(60).items()
        if key != "max_permitted_edge_trim_mm"
    }
    if bad == "negative_radius":
        measured["first_inner_radius_mm"] = -1
    elif bad == "zero_ba":
        measured["second_bend_allowance_mm"] = 0
    else:
        measured["first_bend_allowance_mm"] = .001
    with pytest.raises(GeometryError):
        manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
            scene, first, second, **inputs, **measured,
            second_leg_outer_perimeter_retract_mm=6,
        )


def test_90_and_unsourced_60_cannot_enter_reverse_measured_rba():
    scene, first, second, inputs = _source(angle=90)
    measurements = {
        key: val for key, val in _calibrated(90).items()
        if key != "max_permitted_edge_trim_mm"
    }
    with pytest.raises(GeometryError, match="negative first BEND"):
        manufacturing_api.diagnose_v_miter_reverse_crease_measured_r_ba_trial(
            scene, first, second, **inputs, **measurements,
            second_leg_outer_perimeter_retract_mm=6,
        )

def _120_original_full_and_split_bends(*, mode):
    full, first, second, inputs = _source(angle=120, mode=mode)
    old = tuple(full.primitives)
    short = LinePrimitive(Vec2(-5, 0), Vec2(0, 0), "BEND")
    continuation = LinePrimitive(Vec2(-100, 0), Vec2(-5, 0), "BEND")
    split = DrawingScene([old[0], short, second, continuation])
    return (full, first, second), (split, short, second), inputs


@pytest.mark.parametrize("mode", ("RELIEF_HOLE", "ROUND_R"))
def test_120_measured_rba_real_continuation_matches_single_full_source_2d_3d(mode):
    # Same physical original CUTTING, same real 100mm crease, but recorded
    # as a 5mm selected BEND followed by a 95mm actual source BEND.
    # This must be identical in real curved R/BA/T geometry to a canonical
    # single 100mm BEND, NOT a virtual or infinite mathematical extension.
    full, split, inputs = _120_original_full_and_split_bends(mode=mode)
    full_before = tuple(full[0].primitives)
    split_before = tuple(split[0].primitives)
    calibration = _calibrated(120)
    expected = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        *full, **inputs, **calibration,
    )
    actual = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        *split, **inputs, **calibration,
    )
    assert expected.manufacturing_status == "V_MITER_RADIUS_BA_INTERFACE_UNCERTIFIED"
    assert actual.manufacturing_status == expected.manufacturing_status
    assert actual.first_mesh_source_bend_span_mm == pytest.approx(100)
    assert actual.second_mesh_source_bend_span_mm == pytest.approx(100)
    assert actual.first_mesh_source_bend_span_mm == pytest.approx(
        expected.first_mesh_source_bend_span_mm
    )
    assert actual.first_flat_source_area_mm2 == pytest.approx(
        expected.first_flat_source_area_mm2
    )
    assert actual.second_flat_source_area_mm2 == pytest.approx(
        expected.second_flat_source_area_mm2
    )
    assert actual.first_flat_source_outline == expected.first_flat_source_outline
    assert actual.first_trimmed_check_outline == expected.first_trimmed_check_outline
    assert actual.full_corrected_check_outline == expected.full_corrected_check_outline
    assert actual.first_edge_trim_mm == pytest.approx(expected.first_edge_trim_mm)
    assert actual.first_formed_skin_triangles == expected.first_formed_skin_triangles
    assert actual.second_formed_skin_triangles == expected.second_formed_skin_triangles
    assert actual.first_thick_solid_triangles == expected.first_thick_solid_triangles
    assert actual.second_thick_solid_triangles == expected.second_thick_solid_triangles
    assert actual.first_source_cut_face == expected.first_source_cut_face
    assert actual.second_source_cut_face == expected.second_source_cut_face
    assert actual.seam_section_gap_trial == expected.seam_section_gap_trial
    assert actual.source_cut_face_continuity_trial == expected.source_cut_face_continuity_trial
    assert actual.true_t_volume_check_status == expected.true_t_volume_check_status
    assert tuple(full[0].primitives) == full_before
    assert tuple(split[0].primitives) == split_before


@pytest.mark.parametrize("kind", ("missing", "gap", "short", "offset", "cross"))
def test_120_measured_rba_never_uses_unsourced_bend_extension(kind):
    _, (scene, first, second), inputs = _120_original_full_and_split_bends(
        mode="RELIEF_HOLE",
    )
    scene.primitives.pop()  # remove genuine continuation to create a bad source
    if kind == "gap":
        scene.primitives.extend([
            LinePrimitive(Vec2(-5, 0), Vec2(-7, 0), "BEND"),
            LinePrimitive(Vec2(-8, 0), Vec2(-100, 0), "BEND"),
        ])
    elif kind == "short":
        scene.primitives.append(LinePrimitive(Vec2(-5, 0), Vec2(-7, 0), "BEND"))
    elif kind == "offset":
        scene.primitives.append(LinePrimitive(Vec2(-5, 0.01), Vec2(-100, 0.01), "BEND"))
    elif kind == "cross":
        scene.primitives.append(LinePrimitive(Vec2(-9, -10), Vec2(-9, 10), "BEND"))
    with pytest.raises(GeometryError, match="source material extension evidence"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **inputs, **_calibrated(120),
        )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_60_real_negative_axis_source_still_cannot_enter_measured_rba(mode):
    scene, first, second, args = _source(60, mode=mode)
    scene.primitives.append(LinePrimitive(Vec2(0, 0), Vec2(30, 0), "BEND"))
    assert manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **args,
    ).first_original_bend_continuation_covers is True
    with pytest.raises(GeometryError, match="source material extension evidence"):
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



def test_unknown_true_T_volume_never_returns_any_source_CHECK_candidate(monkeypatch):
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
    # Real formed physical triangles are built, but UNKNOWN parity is now a
    # HARD rejection, rather than a CHECK contour chosen from unverifiable
    # physical volume. No source edit and no DXF producer may get a result.
    with pytest.raises(owner.VMiterRadiusBAContactError, match="UNKNOWN true-T volume closure") as caught:
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(),
        )
    failure = caught.value
    assert failure.attempted_noncoplanar_pairs == 0
    assert failure.attempted_containment_points == ()
    assert failure.manufacturing_status.endswith("UNCERTIFIED")
    with pytest.raises(owner.VMiterRadiusBAContactError, match="UNKNOWN true-T volume closure"):
        manufacturing_api.build_v_miter_radius_ba_full_sheet_check_scene(
            scene, first, second, **args, **_calibrated(),
        )
    assert tuple(scene.primitives) == original_primitives
