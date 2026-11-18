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


def _args():
    return dict(formed_seam_start=(0, 0, 0), formed_seam_end=(0, 0, 10))


def _analyze(first, second):
    return project_v_miter_true_cut_face_continuity_trial(
        first, second, **_args(),
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
    assert [(i.start_mm, i.end_mm) for i in missing] == pytest.approx([
        (3, 4), (4, 6), (6, 7),
    ])


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
    assert result.first_missing_span_mm == pytest.approx(7)
    assert result.second_missing_span_mm == pytest.approx(7)
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


def test_zero_length_or_absent_source_cut_face_rejects_continuity_trial():
    mesh = _wall(0, 0, 10)
    with pytest.raises(GeometryError, match="seam"):
        project_v_miter_true_cut_face_continuity_trial(
            mesh, mesh, formed_seam_start=(0, 0, 0),
            formed_seam_end=(0, 0, 0),
        )
    with pytest.raises(GeometryError, match="empty"):
        _analyze((), mesh)
