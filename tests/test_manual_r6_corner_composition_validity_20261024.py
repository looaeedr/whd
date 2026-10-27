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


@pytest.mark.parametrize("field", [
    "fold_u", "fold_v", "primary_u", "primary_v",
    "secondary_u", "secondary_depth",
    "slot_width", "slot_straight_depth", "slot_radius",
])
def test_r6_composer_rejects_unrepresentable_physical_corner_dimensions(field):
    """Huge saved values must raise the existing geometry error, not OverflowError."""
    kwargs = {"fold_u": 15., "fold_v": 15.}
    intrinsic = {"primary": (10., 10.)}
    if field.startswith("fold_"):
        kwargs[field] = 10 ** 400
    elif field.startswith("primary_"):
        intrinsic["primary"] = (10 ** 400, 10.) if field == "primary_u" else (10., 10 ** 400)
    elif field.startswith("secondary_"):
        intrinsic.update(secondary_u=4., secondary_depth=5.)
        intrinsic[field] = 10 ** 400
    else:
        intrinsic.update(slot_width=12., slot_straight_depth=10., slot_radius=3.)
        intrinsic[field] = 10 ** 400
    with pytest.raises(GeometryError):
        compose_corner_residual(CornerTypeResidual(**intrinsic), **kwargs)


def test_r6_composer_rejects_finite_inputs_whose_cutting_sum_overflows():
    with pytest.raises(GeometryError, match="第一級截角尺寸"):
        compose_corner_residual(
            CornerTypeResidual(primary=(1e308, 0.)),
            fold_u=1e308, fold_v=15.,
        )


def test_r6_corner_policy_rejects_unrepresentable_thickness_and_fw():
    from ae_engine.sheetmetal_corner_policy import (
        corner_selection_residual, FourCornerTypePolicy,
    )
    from ae_engine.sheetmetal_geometry_core import CornerTypeSelection, CornerTypeId
    selection = CornerTypeSelection(CornerTypeId.CROSS)
    for dimensions in ({"thickness": 10 ** 400, "fw": 20.},
                       {"thickness": 2., "fw": 10 ** 400}):
        with pytest.raises(GeometryError):
            corner_selection_residual(selection, **dimensions)
    cfg = FourCornerTypePolicy(selection, selection, selection, selection,
                               fw=10 ** 400)
    with pytest.raises(GeometryError, match="FW"):
        cfg.fw_for("top_left")


@pytest.mark.parametrize("invalid", ["false", "0", 1, None])
def test_r6_saved_bottom_wrap_flag_must_be_explicit_boolean(invalid):
    """A saved string must not unexpectedly enable physical EndCap WRAP."""
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import (
        BoxBodyStructureType, default_box_body_structure_state,
    )
    saved = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    cfg = saved["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg["bottom_external_wrap"] = invalid
    with pytest.raises(ValueError, match="bottom_external_wrap"):
        receiving.bottom_external_wrap_enabled(saved)
    with pytest.raises(ValueError, match="bottom_external_wrap"):
        receiving.set_bottom_external_wrap(saved, invalid)
    assert cfg["bottom_external_wrap"] == invalid


@pytest.mark.parametrize("field", ["reserve_u", "reserve_v"])
@pytest.mark.parametrize("invalid", [True, False, float("nan"), float("inf"), float("-inf"), 10 ** 400])
def test_r6_bottom_wrap_reserves_reject_nonphysical_stored_or_operator_values(field, invalid):
    """A nonfinite relief reserve may not become a silent 0-mm cutout."""
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import (
        BoxBodyStructureType, default_box_body_structure_state,
    )
    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    key = "bottom_relief_reserve_u" if field == "reserve_u" else "bottom_relief_reserve_v"
    cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    with pytest.raises(ValueError, match=key):
        receiving.set_bottom_relief_reserves(state, **{field: invalid})
    cfg[key] = invalid
    with pytest.raises(ValueError, match=key):
        receiving.bottom_relief_reserves(state)
    assert cfg[key] is invalid


def test_r6_bottom_wrap_valid_boolean_and_adjustable_reserves_remain_unchanged():
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import default_box_body_structure_state
    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    assert receiving.bottom_relief_reserves(state) == pytest.approx((2., 1.))
    disabled = receiving.set_bottom_external_wrap(state, False)
    assert receiving.bottom_external_wrap_enabled(disabled) is False
    adjustable = receiving.set_bottom_relief_reserves(state, reserve_u=3.5, reserve_v=2.25)
    assert receiving.bottom_relief_reserves(adjustable) == pytest.approx((3.5, 2.25))
