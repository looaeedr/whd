"""#3317 inverse formed R/BA contact into original flat material, CHECK only.

Independent unit test: this explicitly does not certify the actual Tail V.
"""
import math
import pytest

from ae_engine.sheetmetal_geometry_core import Vec2
from ae_engine.v_miter_tail_dual_source_check import (
    _inverse_straight_90_fold_contact,
    _apex_ray_side_exit_least_squares,
)


def test_straight_90_fold_inverse_reuses_real_rba_and_source_apex():
    apex = Vec2(15.0, 48.0)
    inner_r, thickness, ba = 2.0, 2.0, 4.178318229274424
    mid_r = inner_r + thickness / 2.0
    target = (12.0, 45.0)
    fractions = (0.25, 0.50, 0.75, 0.95)
    reach = 15.0 - ba + mid_r
    zs = [mid_r + f * (reach - mid_r) for f in fractions]
    side = tuple(_inverse_straight_90_fold_contact(
        target, z, apex=apex,
        axis=(0, 1, 0), outside=(-1, 0, 0),
        bend_allowance_mm=ba, mid_radius_mm=mid_r,
    ) for z in zs)
    bottom = tuple(_inverse_straight_90_fold_contact(
        target, z, apex=apex,
        axis=(1, 0, 0), outside=(0, -1, 0),
        bend_allowance_mm=ba, mid_radius_mm=mid_r,
    ) for z in zs)
    for z, s, b in zip(zs, side, bottom):
        flat_u = ba + z - mid_r
        assert (s.x, s.y) == pytest.approx((15-flat_u, 45.0))
        assert (b.x, b.y) == pytest.approx((12.0, 48-flat_u))
        # Side stock's ORIGINAL BEND only starts at y=49. This inverse
        # witness is outside that span; never fill the missing stock.
        assert s.y < 49.0
    side_exit, side_residual = _apex_ray_side_exit_least_squares(
        apex, side, side_x=0.0,
    )
    bottom_exit, bottom_residual = _apex_ray_side_exit_least_squares(
        apex, bottom, side_x=0.0,
    )
    assert math.isfinite(side_exit) and math.isfinite(bottom_exit)
    assert side_exit < apex.y  # NOT the required upper V outer opening
    assert side_residual > 0  # straight ray cannot cover curved-root offset
    assert bottom_residual > 0


def test_inverse_rejects_missing_straight_section_or_ray():
    from ae_engine.sheetmetal_geometry_core import GeometryError
    with pytest.raises(GeometryError, match="NOT_ON_STRAIGHT"):
        _inverse_straight_90_fold_contact(
            (12, 45), 2.0, apex=Vec2(15, 48),
            axis=(0, 1, 0), outside=(-1, 0, 0),
            bend_allowance_mm=4.178318229274424, mid_radius_mm=3.0,
        )
    with pytest.raises(GeometryError, match="NOT_DETERMINED"):
        _apex_ray_side_exit_least_squares(
            Vec2(15, 48), (Vec2(15, 47), Vec2(15, 46)), 0.0,
        )
