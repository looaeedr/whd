"""#3317: Engine supplies explicit unverified R/BA + R/hole starting values."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.contracts import DoorPartSpec, EndCapPartSpec, FoldProfileSegment
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


@pytest.mark.parametrize("angle", [60, 90, 120])
@pytest.mark.parametrize("mode,factor", [("ROUND_R", 1.0), ("RELIEF_HOLE", 2.0)])
@pytest.mark.parametrize("thickness", [1.0, 2.0, 3.0])
def test_engine_unverified_presets_consume_real_t_and_second_fold(angle, mode, factor, thickness):
    preset = api.project_v_miter_trial_parameter_defaults(
        thickness_mm=thickness, second_fold_angle_deg=angle, relief_mode=mode,
    )
    assert preset.first_inner_radius_mm == thickness
    assert preset.second_inner_radius_mm == thickness
    assert preset.neutral_axis_k == 0.33
    assert preset.relief_mode.value == mode
    assert preset.relief_t_factor == factor
    assert preset.relief_dimension_mm == factor * thickness
    assert preset.first_bend_allowance_mm == pytest.approx(
        (math.pi / 2) * (thickness + 0.33 * thickness)
    )
    assert preset.second_bend_allowance_mm == pytest.approx(
        math.radians(angle) * (thickness + 0.33 * thickness)
    )
    assert preset.manufacturing_status.endswith("UNCERTIFIED")
    assert preset.assumption_source == "ENGINE_GENERIC_TRIAL_DEFAULT_NOT_SHOP_MEASUREMENT"
    assert preset.as_trial_inputs() == {
        "relief_t_factor": factor,
        "first_inner_radius_mm": thickness,
        "second_inner_radius_mm": thickness,
        "first_bend_allowance_mm": preset.first_bend_allowance_mm,
        "second_bend_allowance_mm": preset.second_bend_allowance_mm,
    }


@pytest.mark.parametrize("bad_t,bad_angle,bad_mode", [
    (True, 90, "ROUND_R"), (0, 90, "ROUND_R"), (-1, 90, "ROUND_R"),
    (float("nan"), 90, "ROUND_R"), (float("inf"), 90, "ROUND_R"),
    (2, True, "ROUND_R"), (2, 0, "ROUND_R"), (2, 180, "ROUND_R"),
    (2, float("nan"), "ROUND_R"), (2, 90, "FACTORY_CERTIFIED"),
])
def test_invalid_trial_inputs_fail_closed(bad_t, bad_angle, bad_mode):
    with pytest.raises(GeometryError):
        api.project_v_miter_trial_parameter_defaults(
            thickness_mm=bad_t, second_fold_angle_deg=bad_angle,
            relief_mode=bad_mode,
        )


def test_actual_gui_v_check_receives_engine_default_without_modifying_factory_source():
    points = tuple(Vec2(*v) for v in [(0, 0), (200, 0), (200, 200), (0, 200)])
    outline = PolylinePrimitive(points, 'CUTTING', closed=True)
    bends = [
        LinePrimitive(Vec2(20, 20), Vec2(20, 180), 'BEND'),
        LinePrimitive(Vec2(180, 20), Vec2(180, 180), 'BEND'),
        LinePrimitive(Vec2(20, 20), Vec2(180, 20), 'BEND'),
        LinePrimitive(Vec2(20, 180), Vec2(180, 180), 'BEND'),
    ]
    scene = DrawingScene([outline, *bends])
    original = tuple(scene.primitives)
    render = PartRenderData(scene=scene, material=Polygon([(p.x, p.y) for p in points]))
    spec = EndCapPartSpec(
        width=200, depth=200, thickness=2, frame_width=20,
        fold_profile_x=(
            FoldProfileSegment(20, angle=-90), FoldProfileSegment(160, angle=-90),
            FoldProfileSegment(20),
        ),
        fold_profile_y=(
            FoldProfileSegment(20, angle=-120), FoldProfileSegment(160, angle=-90),
            FoldProfileSegment(20),
        ),
    )
    result = api.project_operator_v_miter_live_corner_check(spec, render, 'bottom_left')
    assert result.second_fold_angle_deg == 120
    assert result.trial_defaults.thickness_mm == 2
    assert result.trial_defaults.first_inner_radius_mm == 2
    assert result.trial_defaults.second_bend_allowance_mm == pytest.approx(
        math.radians(120) * 2.66
    )
    assert result.trial_defaults.manufacturing_status.endswith("UNCERTIFIED")
    assert tuple(scene.primitives) == original
    with pytest.raises(GeometryError, match='CHECK_ONLY_UNCERTIFIED'):
        api.require_no_operator_v_miter_gui_check_for_export(
            {'v_miter_gui_check_corners': {'head': {'bottom_left': 'V_MITER_CHECK'}}}
        )


def test_gui_only_formats_engine_preset_not_recalculates_bend_allowance():
    source = (Path(__file__).parents[1] / 'gui_modules/parts/panels/assembly_corner.py').read_text(encoding='utf-8')
    assert 'preset = live.trial_defaults' in source
    assert 'preset.first_bend_allowance_mm' in source
    assert 'preset.second_bend_allowance_mm' in source
    assert 'preset.relief_dimension_mm' in source
    assert 'math.radians(' not in source

