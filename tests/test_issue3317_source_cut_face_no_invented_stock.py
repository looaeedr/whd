"""#3317: a V cut-face cannot use material outside the actual CUTTING source.

The source mesh tracer is shared by the real Factory T and explicit R/BA
CHECK paths. A large sheet cannot turn an out-of-stock tab into permitted
material merely because its added area is small relative to total area.
No factory kerf, seam tolerance, inner R, or BA is inferred here.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from ae_engine.contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_source_cut_face_trial import (
    trace_v_miter_source_true_t_cut_faces,
)


def _source_and_v_candidate(side_mm: float, tab_mm: float, reverse: bool):
    original_points = (
        (0.0, 0.0), (side_mm, 0.0),
        (side_mm, side_mm), (0.0, side_mm),
    )
    corrected_points = [
        (0.0, 0.0), (side_mm, 0.0),
        (side_mm, side_mm - 10.0),
        (side_mm - 10.0, side_mm - 10.0),
        (side_mm - 10.0, side_mm), (0.0, side_mm),
    ]
    if tab_mm:
        corrected_points.extend((
            (0.0, 100.5), (-tab_mm, 100.5),
            (-tab_mm, 100.0), (0.0, 100.0),
        ))
    original = Polygon(
        tuple(reversed(original_points)) if reverse else original_points
    )
    corrected = Polygon(
        tuple(reversed(corrected_points)) if reverse else corrected_points
    )
    assert original.is_valid and corrected.is_valid
    assert corrected.area > 0
    return original, corrected


@pytest.mark.parametrize("side_mm, tab_mm", (
    (1000.0, 0.02),
    (5000.0, 0.2),
))
@pytest.mark.parametrize("reverse", (False, True))
def test_small_out_of_stock_tab_on_large_sheet_is_never_a_real_v_cut_face(
    side_mm, tab_mm, reverse,
):
    original, corrected = _source_and_v_candidate(side_mm, tab_mm, reverse)
    length_tol = (
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    # Deliberately smaller than the old sheet-area-scaled allowance, yet
    # many orders of magnitude beyond actual Engine coordinate tolerance.
    assert corrected.difference(original).area > 0
    assert corrected.difference(original).area < length_tol * original.area
    assert tab_mm > 1000 * length_tol

    with pytest.raises(GeometryError, match="cannot invent corrected stock"):
        trace_v_miter_source_true_t_cut_faces(
            original, corrected, (), (), (), thickness_mm=2.0,
        )


@pytest.mark.parametrize("reverse", (False, True))
def test_genuine_inside_source_v_removal_reaches_existing_mesh_guard(reverse):
    original, corrected = _source_and_v_candidate(1000.0, 0.0, reverse)
    assert corrected.difference(original).is_empty
    # Without a real 2D/3D/true-T mesh there must still be no fabricated
    # cut-face evidence; but a valid source V subtraction itself is allowed.
    with pytest.raises(GeometryError, match="lacks paired 2D/3D/true-T mesh"):
        trace_v_miter_source_true_t_cut_faces(
            original, corrected, (), (), (), thickness_mm=2.0,
        )
