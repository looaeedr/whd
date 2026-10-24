"""Source-reviewed Round 5 numeric, hole and annotation safeguards."""
import pytest
from ae_engine.contracts import FoldProfileSegment, CustomFoldPartSpec
from ae_engine.custom_fold_manufacturing import custom_fold_structural_result
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from ae_engine.drawing_annotation_layout import _quantity_text_box
from ae_engine.sheetmetal_drawing import TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.hole_catalog import (
    custom_circle_definition, custom_rectangle_definition, feature_from_definition,
)
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, _round_pattern_pitch


def test_r5_72_terminal_no_bend_and_invalid_source_values():
    def spec(first, last_angle=0.):
        return CustomFoldPartSpec(
            physical_id="custom:test", fold_axis="X", thickness=2.,
            transverse_length=100.,
            fold_profile=(FoldProfileSegment(length=first, angle=90., formed_length=42.),
                          FoldProfileSegment(length=60., angle=last_angle, formed_length=62.)),
        )
    result = custom_fold_structural_result(spec(40.))
    assert result.width == pytest.approx(100.)
    assert len(result.bends) == 1
    for bad in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            custom_fold_structural_result(spec(bad))


def test_r5_74_display_sources_fallback_independently():
    assert resolve_operator_finished_dimensions(
        "box_body", snapshot={"w": 600., "h": 800., "d": 250.},
        settings={"w": None, "h": True, "d": float("nan")},
    ) == (600., 800., 250.)
    assert resolve_operator_finished_dimensions(
        "head", snapshot={"w": None, "d": float("inf")},
        settings={"w": 500., "d": 200.},
    ) == (500., 200.)


def test_r5_75_out_of_range_mtext_attachment_keeps_insert():
    primitive = TextPrimitive(
        text="QTY: 2", insert=Vec2(10., 20.), char_height=5.,
        layer="MARKING", attachment_point=12,
    )
    box = _quantity_text_box(primitive)
    assert box.bounds[0] == pytest.approx(10.)
    assert box.bounds[1] == pytest.approx(20.)


def test_r5_78_custom_hole_values_and_rotation_guard():
    for bad in (True, False, 0, -5., float("nan"), float("inf")):
        with pytest.raises(ValueError):
            custom_circle_definition(bad)
        with pytest.raises(ValueError):
            custom_rectangle_definition(bad, 10.)
        with pytest.raises(ValueError):
            custom_rectangle_definition(10., bad)
    good = custom_circle_definition(22.)
    for bad in (True, float("nan"), 89.6):
        with pytest.raises(ValueError):
            feature_from_definition(good, Vec2(50., 50.), 100., 100., rotation_deg=bad)
    feature = feature_from_definition(good, Vec2(50., 50.), 100., 100., rotation_deg=90)
    assert feature.diameter == pytest.approx(22.)


def test_r5_79_round_pattern_rejects_invalid_pitch():
    hole = CircleFeature(diameter=10., anchor=FeatureAnchor.BOTTOM_LEFT, offset=Vec2(20., 20.))
    for bad in (True, float("nan"), float("inf")):
        for driver in ("center", "gap"):
            with pytest.raises(ValueError):
                _round_pattern_pitch(hole, driver, bad)
    assert _round_pattern_pitch(hole, "gap", 5.) == pytest.approx(15.)
