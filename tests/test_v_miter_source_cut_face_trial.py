"""#3317 source-first V-cut sidewalls must come from REAL physical T-solid faces."""
from __future__ import annotations

import math
import pytest
from shapely.geometry import Polygon, box

from ae_engine.assembly_geometry_primitives import thicken_triangle_surface
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_source_cut_face_trial import trace_v_miter_source_true_t_cut_faces
from ae_engine.v_miter_true_t_collision import _source_triangulation


def _notch():
    original = box(0, 0, 10, 10)
    # The two sloped V-cut faces are newly introduced source CUTTING edges.
    # The exterior x=10 edges are old perimeter, never V contact faces.
    corrected = Polygon((
        (0, 0), (10, 0), (10, 4), (8, 5),
        (10, 6), (10, 10), (0, 10),
    ))
    flat = _source_triangulation(corrected)
    formed = tuple(
        tuple((x, y, 0.0) for x, y in triangle) for triangle in flat
    )
    solid = thicken_triangle_surface(formed, 2.0)
    return original, corrected, flat, formed, solid


def test_actual_source_notch_identifies_only_true_T_cutting_sidewalls():
    original, corrected, flat, formed, solid = _notch()
    result = trace_v_miter_source_true_t_cut_faces(
        original, corrected, flat, formed, solid, thickness_mm=2,
    )
    expected = 2 * math.sqrt(5)
    assert result.manufacturing_status.endswith("UNCERTIFIED")
    assert result.source_new_v_cut_length_mm == pytest.approx(expected)
    assert result.selected_flat_v_cut_length_mm == pytest.approx(expected)
    assert result.formed_boundary_edge_count >= 2
    assert len(result.true_cut_face_triangles) == 2 * result.formed_boundary_edge_count
    assert len(result.true_cut_face_triangles) < len(solid)
    # No x=0 (old outside) or 10mm exterior wall is accepted as a V-cut face.
    for tri in result.true_cut_face_triangles:
        assert all(8 - 1e-7 <= point[0] <= 10 + 1e-7 for point in tri)
        assert all(4 - 1e-7 <= point[1] <= 6 + 1e-7 for point in tri)
        assert all(abs(abs(point[2]) - 1.0) <= 1e-7 for point in tri)


def test_missing_actual_solid_sidewall_rejects_fabricated_evidence():
    original, corrected, flat, formed, solid = _notch()
    proven = trace_v_miter_source_true_t_cut_faces(
        original, corrected, flat, formed, solid, thickness_mm=2,
    )
    # Remove one of the required wall triangles while retaining other
    # true-T shell triangles. The provenance cannot silently invent it.
    wall = proven.true_cut_face_triangles[0]
    remainder = tuple(
        tri for tri in solid if set(tri) != set(wall)
    )
    assert len(remainder) == len(solid) - 1
    with pytest.raises(GeometryError, match="not a physical T-solid sidewall"):
        trace_v_miter_source_true_t_cut_faces(
            original, corrected, flat, formed, remainder, thickness_mm=2,
        )


def test_unpaired_3d_mesh_and_missing_new_cut_fail_closed():
    original, corrected, flat, formed, solid = _notch()
    with pytest.raises(GeometryError, match="paired 2D/3D"):
        trace_v_miter_source_true_t_cut_faces(
            original, corrected, flat[:-1], formed, solid, thickness_mm=2,
        )
    with pytest.raises(GeometryError, match="no real new V-cut"):
        trace_v_miter_source_true_t_cut_faces(
            original, original, flat, formed, solid, thickness_mm=2,
        )
    with pytest.raises(GeometryError, match="cannot invent"):
        trace_v_miter_source_true_t_cut_faces(
            corrected, original, flat, formed, solid, thickness_mm=2,
        )


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), 0, True, -2))
def test_thickness_is_explicit_positive_real_material(bad):
    original, corrected, flat, formed, solid = _notch()
    with pytest.raises(GeometryError, match="actual finite positive thickness"):
        trace_v_miter_source_true_t_cut_faces(
            original, corrected, flat, formed, solid, thickness_mm=bad,
        )
