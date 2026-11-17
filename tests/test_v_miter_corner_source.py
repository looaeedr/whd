"""#3317: same-source V-miter input contract; NO false CUTTING approval."""
import math

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry_core import CornerTypeId, GeometryError, Vec2
from ae_engine.v_miter_corner_source import VMiterReliefMode


def _source(second_end=(0.0, 100.0)):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(*second_end), "BEND")
    return DrawingScene([first, second]), first, second


def _qualified(scene=None, first=None, second=None, **overrides):
    if scene is None:
        scene, first, second = _source()
    args = dict(
        thickness_mm=2,
        first_flange_height_mm=20,
        second_flange_height_mm=30,
        second_fold_angle_deg=90,
        relief_mode="ROUND_R",
    )
    args.update(overrides)
    return manufacturing_api.qualify_v_miter_corner_source(
        scene, first, second, **args,
    )


@pytest.mark.parametrize("angle", [60, 90, 120])
@pytest.mark.parametrize("mode", ["ROUND_R", "RELIEF_HOLE"])
def test_actual_fold_inputs_and_both_relief_modes_are_source_qualified_but_not_certified(angle, mode):
    source, first, second = _source()
    plan = _qualified(
        source, first, second,
        first_flange_height_mm=20,
        second_flange_height_mm=30,
        second_fold_angle_deg=angle,
        relief_mode=mode,
    )
    assert plan.first_fold_angle_deg == 90
    assert plan.second_fold_angle_deg == angle
    assert plan.first_flange_height_mm != plan.second_flange_height_mm
    assert plan.relief_mode is VMiterReliefMode(mode)
    assert plan.relief_t_factor is None  # Multiples of T NOT yet validated.
    assert plan.bend_intersection == Vec2(0, 0)
    assert plan.flat_bend_line_angle_deg == pytest.approx(90)
    assert plan.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"


def test_non_orthogonal_bend_source_geometry_is_not_mistaken_for_a_fixed_right_angle():
    scene, first, second = _source((100, 100))
    plan = _qualified(scene, first, second, second_fold_angle_deg=120)
    assert plan.flat_bend_line_angle_deg == pytest.approx(45)
    assert plan.second_fold_angle_deg == 120
    assert plan.first_fold_angle_deg == 90


def test_manual_trial_t_factor_may_be_recorded_without_granting_manufacturing_certification():
    plan = _qualified(relief_mode="RELIEF_HOLE", relief_t_factor=1.75)
    assert plan.relief_t_factor == pytest.approx(1.75)
    assert plan.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"


@pytest.mark.parametrize("field,value", [
    ("thickness_mm", 0), ("thickness_mm", True),
    ("first_flange_height_mm", -1),
    ("second_flange_height_mm", float("nan")),
    ("second_fold_angle_deg", 0),
    ("second_fold_angle_deg", 180),
    ("second_fold_angle_deg", float("inf")),
    ("second_fold_angle_deg", False),
    ("relief_mode", "NO_RELIEF"),
    ("relief_t_factor", 0),
    ("relief_t_factor", True),
])
def test_invalid_fold_or_unverified_relief_inputs_fail_closed(field, value):
    with pytest.raises(GeometryError):
        _qualified(**{field: value})


def test_quoted_bend_or_fake_bend_cannot_pass_source_identity_check():
    scene, first, second = _source()
    twin = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        _qualified(scene, twin, second)
    with pytest.raises(GeometryError, match="original scene"):
        _qualified(scene, first, LinePrimitive(Vec2(1, 0), Vec2(2, 1), "BEND"))
    with pytest.raises(GeometryError, match="two distinct"):
        _qualified(scene, first, first)


def test_parallel_and_degenerate_fold_lines_are_not_given_fake_miter_solution():
    scene, first, second = _source((100, 0))
    with pytest.raises(GeometryError, match="parallel"):
        _qualified(scene, first, second)
    scene, first, second = _source((0, 0))
    with pytest.raises(GeometryError, match="positive length"):
        _qualified(scene, first, second)


def test_no_fifth_selection_or_cutting_policy_until_real_formed_certification():
    # A qualified source is intentionally NOT an editable manufacture-able type.
    # 3D contact/CUTTING/Save->Reload and T ratios still require evidence.
    from ae_engine.sheetmetal_geometry_core import EDITABLE_CORNER_TYPE_IDS
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4
    with pytest.raises(ValueError):
        CornerTypeId("V_MITER")
    assert hasattr(manufacturing_api, "qualify_v_miter_corner_source")
