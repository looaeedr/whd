"""R6 actual corner-composition guard: residuals cannot bypass UI validation."""
from math import inf, nan

import pytest

from ae_engine.sheetmetal_corner_policy import compose_corner_residual
from ae_engine.sheetmetal_geometry_core import CornerTypeResidual, GeometryError


@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf])
def test_r6_secondary_corner_dimension_rejects_bool_and_nonfinite(bad):
    source = CornerTypeResidual(
        primary=(10.0, 10.0), secondary_u=bad, secondary_depth=5.0,
    )
    with pytest.raises(GeometryError, match="第二級截角尺寸"):
        compose_corner_residual(source, fold_u=15.0, fold_v=15.0)


@pytest.mark.parametrize("field,bad", [
    ("slot_width", 0.0), ("slot_width", -1.0),
    ("slot_straight_depth", 0.0), ("slot_straight_depth", -1.0),
    ("slot_radius", 0.0), ("slot_radius", -1.0),
])
def test_r6_direct_corner_composition_rejects_nonpositive_cross_slot(field, bad):
    kwargs = dict(slot_width=10., slot_straight_depth=12., slot_radius=5.)
    kwargs[field] = bad
    with pytest.raises(GeometryError, match="十字截角槽參數必須大於 0"):
        compose_corner_residual(
            CornerTypeResidual(primary=(0., 0.), **kwargs),
            fold_u=20., fold_v=20.,
        )


def test_r6_direct_corner_composition_rejects_slot_radius_over_half_width():
    with pytest.raises(GeometryError, match="槽 R"):
        compose_corner_residual(
            CornerTypeResidual(
                primary=(0., 0.), slot_width=10.,
                slot_straight_depth=12., slot_radius=5.01,
            ),
            fold_u=20., fold_v=20.,
        )


@pytest.mark.parametrize("bad", [True, False, nan, inf, -inf, 1.5])
def test_r6_axis_swapping_rejects_noninteger_and_bool_rotation(bad):
    with pytest.raises(GeometryError, match="截角旋轉"):
        compose_corner_residual(
            CornerTypeResidual(primary=(3., 4.)),
            fold_u=20., fold_v=30.,
            rotation_quadrants=bad, allow_axis_swap=True,
        )


def test_r6_valid_secondary_corner_and_cross_slot_keep_existing_geometry():
    secondary = compose_corner_residual(
        CornerTypeResidual(
            primary=(10., 10.), secondary_u=0., secondary_depth=5.,
        ),
        fold_u=15., fold_v=15.,
    )
    assert (secondary.primary_u, secondary.primary_v) == (25., 25.)
    assert (secondary.secondary_u, secondary.secondary_depth) == (15., 5.)

    cross = compose_corner_residual(
        CornerTypeResidual(
            primary=(2., 4.),
            slot_width=10., slot_straight_depth=12., slot_radius=5.,
        ),
        fold_u=20., fold_v=30.,
        rotation_quadrants=1, allow_axis_swap=True,
    )
    assert (cross.primary_u, cross.primary_v) == (24., 32.)
    assert (cross.slot_width, cross.slot_straight_depth, cross.slot_radius) == (10., 12., 5.)

@pytest.mark.parametrize("field", [
    "relief_left_fold", "relief_right_fold",
    "bottom_relief_left_fold", "bottom_relief_right_fold",
])
@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), "-inf"])
def test_r6_manual_endcap_relief_overrides_are_real_finite_folds(field, bad):
    """A bad saved manual override must never become a cutting relief span."""
    from ae_engine.sheetmetal_geometry import (
        EndCapGeometry, VAULT_ENDCAP_CORNER_POLICY, _endcap_manual_material_polygon,
    )
    geometry = EndCapGeometry(
        total_width=800., total_depth=350., thickness=2., fw=0.5,
        left_fold=19., right_fold=19., top_first_fold=29., bottom_fold=29.,
    )
    with pytest.raises(GeometryError, match="封頭.*折邊"):
        _endcap_manual_material_polygon(
            geometry, VAULT_ENDCAP_CORNER_POLICY, **{field: bad},
        )
