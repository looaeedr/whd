"""#3317 actual V CUT FACE topology: short seam gaps cannot hide between 7 probes."""
from __future__ import annotations

import math
import pytest

from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_cut_face_continuity_trial import (
    project_v_miter_true_cut_face_continuity_trial,
)
from ae_engine.v_miter_seam_gap_trial import (
    project_v_miter_true_t_seam_section_gap_trial,
)


def _wall(x, z0, z1):
    """Two physical sidewall triangles on a true T-thick flat cut edge."""
    a = (x, 0.0, z0)
    b = (x, 1.0, z0)
    c = (x, 1.0, z1)
    d = (x, 0.0, z1)
    return ((a, b, c), (a, c, d))


def _sloped_wall(x0, x1, z0, z1):
    """Real planar T-sidewall moving linearly in XYZ with seam height."""
    a, b = (x0, 0.0, z0), (x0, 1.0, z0)
    c, d = (x1, 1.0, z1), (x1, 0.0, z1)
    return ((a, b, c), (a, c, d))


def _args():
    return dict(formed_seam_start=(0, 0, 0), formed_seam_end=(0, 0, 10))


def _analyze(first, second):
    return project_v_miter_true_cut_face_continuity_trial(
        first, second, **_args(),
    )


def test_mesh_vertex_roundoff_is_not_untracked_material_but_real_event_is_rejected():
    from ae_engine.v_miter_cut_face_continuity_trial import (
        _section_transverse_speed_bound,
    )
    wall = _wall(0, 5, 10)
    # Projection stored as a source fraction and multiplied back to mm
    # may differ from 5mm by floating arithmetic alone. No material is
    # added, and the same genuine triangle still spans this interval.
    lo = (5 / 7) * 7
    assert _section_transverse_speed_bound(
        wall, (0, 0, 0), (0, 0, 1), lo, 10,
    ) is not None
    # A genuine vertex at 5mm cannot be ignored by an asserted 4..10
    # geometry interval (with the midpoint inside the triangle).
    with pytest.raises(GeometryError, match="untracked mesh vertex"):
        _section_transverse_speed_bound(
            wall, (0, 0, 0), (0, 0, 1), 4, 10,
        )


def test_short_real_cut_face_material_break_between_seven_legacy_stations():
    first = _wall(0, 0, 10)
    second = _wall(2, 0, 5.2) + _wall(2, 5.4, 10)
    seven = project_v_miter_true_t_seam_section_gap_trial(
        first, second, **_args(),
    )
    # 5.2..5.4 is BETWEEN 5.0 and 6.25. All fixed stations see both.
    assert seven.measured_section_count == 7
    assert seven.missing_section_count == 0
    assert seven.max_measured_gap_mm == pytest.approx(2)

    result = _analyze(first, second)
    assert result.manufacturing_status.endswith("UNCERTIFIED")
    assert result.coverage_status == "FACE_COVERAGE_INCOMPLETE"
    assert result.both_face_interval_count == 2
    assert result.missing_face_interval_count == 1
    assert len(result.intervals) == 3
    assert result.both_face_span_mm == pytest.approx(9.8)
    assert result.first_missing_span_mm == pytest.approx(0)
    assert result.second_missing_span_mm == pytest.approx(0.2)
    assert result.both_missing_span_mm == pytest.approx(0)
    missing = [i for i in result.intervals if not i.has_both_cut_faces]
    assert len(missing) == 1
    assert missing[0].start_mm == pytest.approx(5.2)
    assert missing[0].end_mm == pytest.approx(5.4)
    assert missing[0].midpoint_section.station_mm == pytest.approx(5.3)
    assert missing[0].midpoint_section.status == "SECOND_MISSING"
    assert missing[0].midpoint_section.measured_gap_mm is None
    assert result.min_sampled_cut_face_gap_mm == pytest.approx(2)
    assert result.max_sampled_cut_face_gap_mm == pytest.approx(2)


def test_each_actual_interval_detects_first_second_and_both_material_absence():
    first = _wall(0, 0, 4) + _wall(0, 6, 10)
    second = _wall(2, 0, 3) + _wall(2, 7, 10)
    result = _analyze(first, second)
    assert result.coverage_status == "FACE_COVERAGE_INCOMPLETE"
    assert result.both_face_span_mm == pytest.approx(6)
    assert result.first_missing_span_mm == pytest.approx(0)
    assert result.second_missing_span_mm == pytest.approx(2)
    assert result.both_missing_span_mm == pytest.approx(2)
    missing = [i for i in result.intervals if not i.has_both_cut_faces]
    assert len(missing) == 3
    assert [i.midpoint_section.status for i in missing] == [
        "SECOND_MISSING", "BOTH_MISSING", "SECOND_MISSING",
    ]
    for interval, (expected_start, expected_end) in zip(
        missing, ((3, 4), (4, 6), (6, 7)),
    ):
        assert interval.start_mm == pytest.approx(expected_start)
        assert interval.end_mm == pytest.approx(expected_end)


def test_material_present_but_short_local_gap_peak_is_not_missed():
    first = _wall(0, 0, 10)
    second = _wall(2, 0, 5.2) + _wall(3, 5.2, 5.4) + _wall(2, 5.4, 10)
    seven = project_v_miter_true_t_seam_section_gap_trial(
        first, second, **_args(),
    )
    assert seven.measured_section_count == 7
    assert seven.max_measured_gap_mm == pytest.approx(2)

    result = _analyze(first, second)
    assert result.missing_face_interval_count == 0
    assert result.coverage_status == "FACE_COVERAGE_SAMPLED_ONLY"
    assert result.min_sampled_cut_face_gap_mm == pytest.approx(2)
    assert result.max_sampled_cut_face_gap_mm == pytest.approx(3)
    assert any(
        i.midpoint_section.station_mm == pytest.approx(5.3)
        and i.midpoint_section.measured_gap_mm == pytest.approx(3)
        for i in result.intervals
    )
    # These samples are NOT a certified continuous maximum fit tolerance.
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_all_measured_face_intervals_is_not_mating_certification():
    a, b = _wall(0, 0, 10), _wall(2, 0, 10)
    result = _analyze(a, b)
    assert result.both_face_interval_count > 0
    assert result.missing_face_interval_count == 0
    assert result.both_face_span_mm == pytest.approx(10)
    assert result.min_sampled_cut_face_gap_mm == pytest.approx(2)
    assert result.coverage_status == "FACE_COVERAGE_SAMPLED_ONLY"
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_no_bilateral_cut_face_overlap_is_explicit_missing_not_zero():
    first = _wall(0, 0, 3)
    second = _wall(2, 7, 10)
    result = _analyze(first, second)
    assert result.both_face_interval_count == 0
    assert result.both_face_span_mm == pytest.approx(0)
    assert result.missing_face_interval_count >= 3
    assert result.min_sampled_cut_face_gap_mm is None
    assert result.max_sampled_cut_face_gap_mm is None
    assert result.first_missing_span_mm == pytest.approx(3)
    assert result.second_missing_span_mm == pytest.approx(3)
    assert result.both_missing_span_mm == pytest.approx(4)


@pytest.mark.parametrize("invalid", (
    (), (0.0,), (1.0,), (0.5, 0.5), (0.6, 0.2),
    (float("nan"),), (float("inf"),), (True,), ("0.5",),
))
def test_explicit_section_station_override_fail_closed(invalid):
    mesh = _wall(0, 0, 10)
    with pytest.raises(GeometryError, match="stations"):
        project_v_miter_true_t_seam_section_gap_trial(
            mesh, mesh, **_args(), station_fractions=invalid,
        )


@pytest.mark.parametrize("degenerate", (
    (((0, 0, 5), (1, 0, 5), (2, 0, 5)),),
    (((2, 0, 0), (2, 0, 5), (2, 0, 10)),),
    (((0, 0, 0), (0, 0, 0), (1, 0, 5)),),
))
def test_cut_face_interval_rejects_zero_area_source_mesh_before_coverage(degenerate):
    """Source-tagged V cut face needs a genuine positive-area 3D surface."""
    with pytest.raises(GeometryError, match="zero or invalid area"):
        _analyze(_wall(0, 0, 10), degenerate)


def test_zero_length_or_absent_source_cut_face_rejects_continuity_trial():
    mesh = _wall(0, 0, 10)
    with pytest.raises(GeometryError, match="seam"):
        project_v_miter_true_cut_face_continuity_trial(
            mesh, mesh, formed_seam_start=(0, 0, 0),
            formed_seam_end=(0, 0, 0),
        )
    with pytest.raises(GeometryError, match="empty"):
        _analyze((), mesh)


def test_static_true_cut_faces_have_tight_constant_whole_interval_gap_bounds():
    trial = _analyze(_wall(0, 0, 10), _wall(2, 0, 10))
    assert trial.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
    assert trial.coverage_status == "FACE_COVERAGE_SAMPLED_ONLY"
    assert trial.max_gap_lower_bound_mm <= 2 <= trial.max_gap_upper_bound_mm
    assert trial.min_gap_lower_bound_mm <= 2 <= trial.min_gap_upper_bound_mm
    # Mesh diagonal endpoint speeds are conservative, NOT an exact
    # Hausdorff speed of the union. The independent physical vertex
    # bounding cap still proves this entire static interval < sqrt(5).
    assert 2 <= trial.max_gap_upper_bound_mm <= math.sqrt(5) + 1e-3
    assert trial.min_gap_lower_bound_mm <= 2
    assert len(trial.intervals) == 1
    row = trial.intervals[0]
    assert row.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
    assert row.combined_transverse_speed > 0  # internal mesh diagonals
    assert row.transverse_bounding_box_cap_mm == pytest.approx(math.sqrt(5))
    assert row.max_gap_lower_bound_mm <= 2 <= row.max_gap_upper_bound_mm
    assert row.min_gap_lower_bound_mm <= 2 <= row.min_gap_upper_bound_mm


def test_conservative_bounds_cover_unsampled_peak_at_actual_triangle_vertex():
    # Physical true cut face first x=0. Second x(z) = 2 at seam ends,
    # 3 at the event z=5. The midpoint checks at z=2.5/7.5 measure
    # only 2.5; the actual geometric supremum is 3 at the shared event.
    first = _wall(0, 0, 10)
    second = _sloped_wall(2, 3, 0, 5) + _sloped_wall(3, 2, 5, 10)
    result = _analyze(first, second)
    assert len(result.intervals) == 2
    assert result.max_sampled_cut_face_gap_mm == pytest.approx(2.5)
    assert result.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
    assert result.max_gap_lower_bound_mm <= 3
    assert result.max_gap_upper_bound_mm >= 3
    # This remains a conservative upper bound: the actual peak is 3,
    # while triangulation diagonals and 2D bounding boxes are looser.
    assert 3 <= result.max_gap_upper_bound_mm <= math.sqrt(10) + 1e-3
    assert result.min_gap_lower_bound_mm <= 2
    assert result.min_gap_upper_bound_mm >= 2
    for row in result.intervals:
        assert row.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
        assert row.combined_transverse_speed >= 0.2
        assert row.transverse_bounding_box_cap_mm is not None
        assert row.max_gap_upper_bound_mm <= row.transverse_bounding_box_cap_mm + 1e-3
        assert row.max_gap_lower_bound_mm <= 3 <= row.max_gap_upper_bound_mm
        assert row.min_gap_lower_bound_mm <= 2 <= row.min_gap_upper_bound_mm
        assert row.max_gap_upper_bound_mm > row.midpoint_section.measured_gap_mm
        assert row.max_gap_upper_bound_mm >= row.max_gap_lower_bound_mm
        assert row.min_gap_upper_bound_mm >= row.min_gap_lower_bound_mm
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_remote_source_cut_faces_touch_but_entire_seam_remains_far_from_datum():
    """Inter-face gap=0 cannot pretend either physical cut face reaches seam."""
    result = _analyze(_wall(100, 0, 10), _wall(100, 0, 10))
    assert result.coverage_status == "FACE_COVERAGE_SAMPLED_ONLY"
    assert result.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
    assert result.min_sampled_cut_face_gap_mm == pytest.approx(0)
    assert result.max_gap_upper_bound_mm >= 0
    assert result.first_datum_reach_lower_bound_mm == pytest.approx(100)
    assert result.second_datum_reach_lower_bound_mm == pytest.approx(100)
    assert result.first_datum_reach_upper_bound_mm >= 100
    assert result.second_datum_reach_upper_bound_mm >= 100
    assert len(result.intervals) == 1
    row = result.intervals[0]
    for side in ("first", "second"):
        lo = getattr(row, f"{side}_datum_reach_lower_bound_mm")
        hi = getattr(row, f"{side}_datum_reach_upper_bound_mm")
        assert lo == pytest.approx(100)
        assert hi >= lo
        assert lo <= getattr(result, f"{side}_datum_reach_lower_bound_mm") <= hi
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_real_sloped_mesh_datum_reach_bounds_cover_unsampled_event_extrema():
    """Vertex-event intervals cover physical source-datum reach, not 7 probes."""
    first = _sloped_wall(100, 101, 0, 5) + _sloped_wall(101, 100, 5, 10)
    second = _wall(103, 0, 10)
    result = _analyze(first, second)
    assert result.coverage_status == "FACE_COVERAGE_SAMPLED_ONLY"
    assert result.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
    assert len(result.intervals) == 2
    # First cut face is x=100 at endpoints and x=101 at the mesh event.
    # Its two midpoint sections only see x=100.5.
    assert result.first_datum_reach_lower_bound_mm <= 100
    assert result.first_datum_reach_upper_bound_mm >= 101
    assert result.second_datum_reach_lower_bound_mm == pytest.approx(103)
    assert result.second_datum_reach_upper_bound_mm >= 103
    for row in result.intervals:
        assert row.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
        assert row.first_datum_reach_lower_bound_mm <= 100
        assert row.first_datum_reach_upper_bound_mm >= 101
        assert row.second_datum_reach_lower_bound_mm == pytest.approx(103)
        assert row.second_datum_reach_upper_bound_mm >= 103
        assert row.first_datum_reach_lower_bound_mm <= row.first_datum_reach_upper_bound_mm
        assert row.second_datum_reach_lower_bound_mm <= row.second_datum_reach_upper_bound_mm
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_partial_real_cut_face_coverage_disables_global_max_gap_envelope():
    result = _analyze(
        _wall(0, 0, 10),
        _wall(2, 0, 5.2) + _wall(2, 5.4, 10),
    )
    assert result.coverage_status == "FACE_COVERAGE_INCOMPLETE"
    assert result.gap_bound_status == "UNRESOLVED_OR_PARTIAL_SOURCE_COVERAGE"
    for side in ("first", "second"):
        assert getattr(result, f"{side}_datum_reach_lower_bound_mm") is None
        assert getattr(result, f"{side}_datum_reach_upper_bound_mm") is None
    assert result.max_gap_lower_bound_mm is None
    assert result.max_gap_upper_bound_mm is None
    assert result.min_gap_lower_bound_mm is None
    assert result.min_gap_upper_bound_mm is None
    missing = [row for row in result.intervals if not row.has_both_cut_faces]
    assert len(missing) == 1
    assert missing[0].gap_bound_status == "MISSING_PHYSICAL_CUT_FACE"
    assert missing[0].first_datum_reach_lower_bound_mm is None
    assert missing[0].second_datum_reach_upper_bound_mm is None
    assert missing[0].max_gap_upper_bound_mm is None
    assert all(row.max_gap_upper_bound_mm is not None
               for row in result.intervals if row.has_both_cut_faces)


def test_tiny_unresolved_vertex_clusters_never_claim_gap_upper_certificate():
    from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
    tol = PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    first = _wall(0, 0, 10)
    # A triangle vertex projected nearer than the shared GEOMETRY
    # numerical tolerance is merged into its adjacent source event.
    # That interval no longer has proven exact topology for all stations.
    second = _wall(2, 0, 5) + _wall(2, 5 + tol * 0.25, 10)
    result = _analyze(first, second)
    assert result.numerically_unresolved_vertex_event_count > 0
    assert result.coverage_status == "FACE_COVERAGE_INCOMPLETE"
    assert result.gap_bound_status == "UNRESOLVED_OR_PARTIAL_SOURCE_COVERAGE"
    for side in ("first", "second"):
        assert getattr(result, f"{side}_datum_reach_lower_bound_mm") is None
        assert getattr(result, f"{side}_datum_reach_upper_bound_mm") is None
    assert result.max_gap_upper_bound_mm is None
    assert all(row.max_gap_upper_bound_mm is None for row in result.intervals)
