"""#3317 genuine 3D nested-volume witness: source-safe trial must not call it clearance."""
from __future__ import annotations

import pytest

from ae_engine.assembly_geometry import (
    detect_world_mesh_enclosed_volume_witness,
    detect_world_mesh_surface_interference,
)
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_radius_ba_interface_trial import _search_source_safe_edge_trim


def _closed_box(lo, hi):
    """Twelve real triangular faces of one closed physical volume."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2),
        (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5),
    )
    return tuple(tuple(v[i] for i in face) for face in faces)


def test_enclosed_physical_volume_is_detected_when_crossing_detector_reports_zero():
    outer = _closed_box((0, 0, 0), (20, 20, 20))
    inner = _closed_box((5, 5, 5), (7, 8, 9))
    assert detect_world_mesh_surface_interference(inner, outer).pair_count == 0
    a = detect_world_mesh_enclosed_volume_witness(inner, outer)
    b = detect_world_mesh_enclosed_volume_witness(outer, inner)
    assert a.meshes_closed and b.meshes_closed
    assert a.has_enclosed_overlap and b.has_enclosed_overlap
    assert a.sample_count > 0
    assert a.strictly_inside_points == b.strictly_inside_points
    assert all(0 < x < 20 for p in a.strictly_inside_points for x in p)
    assert a.geometry_model.endswith("UNCERTIFIED")


@pytest.mark.parametrize("other", (
    _closed_box((30, 0, 0), (32, 3, 3)),  # genuinely disjoint
    _closed_box((20, 2, 2), (23, 5, 5)),  # legal touching face, not volume
))
def test_disjoint_or_touching_closed_solids_are_not_fake_positive_volume(other):
    outer = _closed_box((0, 0, 0), (20, 20, 20))
    result = detect_world_mesh_enclosed_volume_witness(outer, other)
    assert result.meshes_closed
    assert not result.has_enclosed_overlap


def test_open_mesh_is_not_treated_as_verified_zero_volume_interference():
    outer = _closed_box((0, 0, 0), (20, 20, 20))
    inner = _closed_box((5, 5, 5), (7, 8, 9))
    result = detect_world_mesh_enclosed_volume_witness(inner[:-1], outer)
    assert not result.meshes_closed
    assert not result.has_enclosed_overlap
    assert result.sample_count == 0


def test_source_safe_trim_search_rejects_volume_even_when_surface_crossing_count_zero():
    sampled = []

    def evaluate(trim):
        sampled.append(trim)
        # Genuine source/geometry checks are represented by existing trial
        # tuple members. Independent 3D containment is index 5.
        inside = ((2.0, 3.0, 4.0),) if trim < 5 else ()
        return ("closed_sheet", "curved_skin", "true_T_solid", 0, (), inside, True)

    original, best, selected = _search_source_safe_edge_trim(
        evaluate, 10, failure_message="no real 3D relief",
    )
    assert original[3] == 0 and original[5]  # surface-only would falsely pass at trim 0
    assert best[3] == 0 and not best[5]
    assert 5 <= selected <= 10
    assert 0 in sampled and 10 in sampled

    with pytest.raises(GeometryError, match="volume not eliminated"):
        _search_source_safe_edge_trim(
            lambda trim: ("source", "skin", "solid", 0, (), ((1, 2, 3),), True),
            10, failure_message="V-miter enclosed volume not eliminated",
        )
