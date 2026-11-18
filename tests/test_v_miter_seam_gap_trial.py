"""#3317 physical T-solid seam sections: real positive gap and missing contact evidence."""
from __future__ import annotations

import math
import pytest

from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_seam_gap_trial import (
    project_v_miter_true_t_seam_section_gap_trial,
)


def _box(lo, hi):
    """12 real 3D solid-surface triangles, not a zero-thickness seam."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    vertices = (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2),
        (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5),
    )
    return tuple(tuple(vertices[j] for j in face) for face in faces)


def _probe(a, b):
    return project_v_miter_true_t_seam_section_gap_trial(
        a, b, formed_seam_start=(0, 0, 0), formed_seam_end=(0, 0, 10),
    )


def test_real_closed_solids_have_two_mm_gap_at_all_seam_sections():
    first = _box((0, 0, 0), (1, 1, 10))
    second = _box((3, 0, 0), (4, 1, 10))
    result = _probe(first, second)
    assert result.manufacturing_status == "V_MITER_SEAM_GAP_UNCERTIFIED"
    assert result.measured_section_count == 7
    assert result.missing_section_count == 0
    assert result.min_measured_gap_mm == pytest.approx(2)
    assert result.max_measured_gap_mm == pytest.approx(2)
    assert result.seam_length_mm == pytest.approx(10)
    for row in result.sections:
        assert row.status == "MEASURED"
        assert row.first_section_segment_count > 0
        assert row.second_section_segment_count > 0
        assert row.measured_gap_mm == pytest.approx(2)
        assert row.nearest_first_xyz[0] == pytest.approx(1)
        assert row.nearest_second_xyz[0] == pytest.approx(3)
        assert row.nearest_first_xyz[2] == pytest.approx(row.station_mm)
        assert row.nearest_second_xyz[2] == pytest.approx(row.station_mm)
        assert math.dist(row.nearest_first_xyz, row.nearest_second_xyz) == pytest.approx(2)


def test_touching_true_solid_sections_measure_zero_but_do_not_certify_contact():
    a = _box((0, 0, 0), (1, 1, 10))
    b = _box((1, 0, 0), (3, 1, 10))
    result = _probe(a, b)
    assert result.measured_section_count == 7
    assert result.min_measured_gap_mm == pytest.approx(0)
    assert result.max_measured_gap_mm == pytest.approx(0)
    assert "UNCERTIFIED" in result.manufacturing_status
    assert "CHECK" in result.geometry_model


def test_partial_seam_has_missing_physical_material_not_zero_gap():
    first = _box((0, 0, 0), (1, 1, 10))
    second = _box((3, 0, 0), (4, 1, 3))
    result = _probe(first, second)
    assert result.measured_section_count == 2
    assert result.missing_section_count == 5
    assert [s.status for s in result.sections[:2]] == ["MEASURED", "MEASURED"]
    assert all(s.status == "SECOND_MISSING" for s in result.sections[2:])
    assert all(s.measured_gap_mm is None for s in result.sections[2:])
    assert all(s.nearest_second_xyz is None for s in result.sections[2:])
    assert result.max_measured_gap_mm == pytest.approx(2)


def test_absent_section_is_unknown_not_zero_or_infinite_gap():
    first = _box((0, 0, 0), (1, 1, 10))
    second = _box((3, 0, 11), (4, 1, 15))
    result = _probe(first, second)
    assert result.measured_section_count == 0
    assert result.missing_section_count == 7
    assert result.min_measured_gap_mm is None
    assert result.max_measured_gap_mm is None
    assert all(s.status == "SECOND_MISSING" for s in result.sections)
    assert all(s.measured_gap_mm is None for s in result.sections)


@pytest.mark.parametrize("bad", (
    (),
    (((0, 0, float("nan")), (1, 0, 0), (0, 1, 0)),),
    (((0, 0, 0), (True, 0, 0), (0, 1, 0)),),
    (((0, 0, 0), (1, 0, 0)),),
))
def test_invalid_true_solid_mesh_is_rejected_not_passed_as_missing(bad):
    first = _box((0, 0, 0), (1, 1, 10))
    with pytest.raises(GeometryError, match="seam-section"):
        _probe(first, bad)


def test_zero_length_or_nonfinite_source_seam_is_rejected():
    first = _box((0, 0, 0), (1, 1, 10))
    with pytest.raises(GeometryError, match="seam-section"):
        project_v_miter_true_t_seam_section_gap_trial(
            first, first, formed_seam_start=(0, 0, 0), formed_seam_end=(0, 0, 0),
        )
    with pytest.raises(GeometryError, match="seam-section"):
        project_v_miter_true_t_seam_section_gap_trial(
            first, first, formed_seam_start=(0, 0, 0),
            formed_seam_end=(float("inf"), 0, 1),
        )
