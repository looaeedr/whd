# -*- coding: utf-8 -*-
"""R7 live-source regressions: custom-only changes and finite manufacturing inputs."""
from copy import deepcopy
import pytest

from phase6_custom_parts import custom_part_only_change
from ae_engine.inner_door_frames import derive_inner_door_frames, inner_door_frame_formed_occupation
from ae_engine.sheetmetal_geometry import (
    CornerTypeSelection, CornerTypeId, CrossCornerMode, EndCapGeometry,
    FourSideFlangeGeometry, RectCornerReliefPolicy,
    calculate_endcap_relief_dimensions, build_endcap_topology,
    build_four_side_outline,
)
from ae_engine.sheetmetal_strip_geometry import FoldSegment, StripFoldChain, build_strip_outline
from ae_engine.sheetmetal_part_adapters import (
    build_box_body_result, build_base_plate_result, build_door_result,
    build_receiving_base_plate_result, RECEIVING_BASE_PATTERN_LEFT,
)


def _custom_snapshot():
    return {
        "w": 800, "h": 1600, "d": 350,
        "workspace": {
            "custom_parts": {"next_id": 2, "items": {
                "custom:1": {"physical_id": "custom:1", "display_name": "板A",
                             "fold_axis": "X", "transverse_length": 120.0,
                             "per_box_count": 1, "fold_preset": "OUTSIDE_17_100"}
            }},
            "part_profiles": {"box_body": {"X": [{"len": 800.0}]}},
        },
    }


def test_r7_custom_only_accepts_missing_none_and_blank_optional_stores():
    before = _custom_snapshot()
    after = deepcopy(before)
    after["workspace"]["custom_parts"]["items"]["custom:1"]["display_name"] = "板B"
    before["workspace"]["part_features"] = None
    after["workspace"]["part_features"] = {}
    before["part_face_features"] = None
    after["part_face_features"] = {}
    assert custom_part_only_change(before, after)
    assert before["workspace"]["part_features"] is None  # compare is pure


def test_r7_only_empty_store_changes_are_not_real_custom_edits():
    before = _custom_snapshot()
    after = deepcopy(before)
    before["workspace"]["part_features"] = None
    after["workspace"]["part_features"] = {}
    assert not custom_part_only_change(before, after)


def test_r7_custom_only_rejects_box_change_other_part_or_identity_change():
    before = _custom_snapshot()
    after = deepcopy(before)
    after["workspace"]["custom_parts"]["items"]["custom:1"]["display_name"] = "板B"
    after["w"] = 810
    assert not custom_part_only_change(before, after)
    after["w"] = 800
    after["workspace"]["part_profiles"]["box_body"]["X"][0]["len"] = 810
    assert not custom_part_only_change(before, after)
    del after["workspace"]["part_profiles"]["box_body"]
    assert not custom_part_only_change(before, after)
    added = deepcopy(before)
    added["workspace"]["custom_parts"]["items"]["custom:2"] = deepcopy(
        added["workspace"]["custom_parts"]["items"]["custom:1"])
    assert not custom_part_only_change(before, added)


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), -float("inf")])
def test_r7_inner_door_frame_refuses_bad_thickness_and_span(bad):
    valid = {"top": 696., "left": 1098., "right": 1098.}
    with pytest.raises(ValueError):
        inner_door_frame_formed_occupation(bad)
    with pytest.raises(ValueError):
        derive_inner_door_frames("door-A", spans=valid, thickness=bad,
                                 included_sides=("top", "left", "right"))
    altered = {**valid, "left": bad}
    with pytest.raises(ValueError):
        derive_inner_door_frames("door-A", spans=altered, thickness=2.,
                                 included_sides=("top", "left", "right"))


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf")])
def test_r7_geometry_rejects_bad_strip_four_side_endcap_and_corner(bad):
    with pytest.raises(ValueError):
        build_strip_outline(StripFoldChain((FoldSegment("a", 20.), FoldSegment("b", 40.)), bad))
    with pytest.raises(ValueError):
        build_strip_outline(StripFoldChain((FoldSegment("a", bad), FoldSegment("b", 40.)), 500.))
    with pytest.raises(ValueError):
        build_strip_outline(StripFoldChain((FoldSegment("a", 20., bad), FoldSegment("b", 40.)), 500.))

    face = FourSideFlangeGeometry(800., 600., 2., 20., 20., 20., 20.)
    relief = RectCornerReliefPolicy(5., 5., 5., 5., 5., 5.)
    with pytest.raises(ValueError):
        build_four_side_outline(
            FourSideFlangeGeometry(bad, face.total_height, face.thickness,
                                   face.left_fold, face.right_fold, face.top_fold, face.bottom_fold),
            relief,
        )
    with pytest.raises(ValueError):
        build_four_side_outline(face, RectCornerReliefPolicy(bad, 5., 5., 5., 5., 5.))
    with pytest.raises(ValueError):
        calculate_endcap_relief_dimensions(
            EndCapGeometry(bad, 350., 2., 46., 22., 22., 20., 20.)
        )
    with pytest.raises(ValueError):
        CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN, amount_t=bad)
    with pytest.raises(ValueError):
        CornerTypeSelection(CornerTypeId.CROSS, slot_width=bad,
                            slot_straight_depth=3., slot_radius=1.)


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf")])
def test_r7_part_adapters_reject_invalid_manufacturing_dimensions(bad):
    with pytest.raises(ValueError):
        build_box_body_result(
            w=bad, h=1600., d=350., t=2., fw=46., zl1=22., zl2=20.,
            zr1=22., zr2=20., z_comp=0.,
        )
    with pytest.raises(ValueError):
        build_door_result(
            w=800., h=1100., t=bad, fw=46., gap_w=3.5, gap_h=3.5,
            fold_left=19., fold_right=19., fold_top=19., fold_bottom=19.,
        )
    with pytest.raises(ValueError):
        build_base_plate_result(
            w=800., h=600., t=2., shrink_top=20., shrink_bottom=20.,
            shrink_left=bad, shrink_right=20., bend=20.,
        )
    with pytest.raises(ValueError):
        build_receiving_base_plate_result(
            w=800., h=600., t=2., shrink_top=20., shrink_bottom=20.,
            shrink_left=85., shrink_right=85., bend=bad,
            pattern=RECEIVING_BASE_PATTERN_LEFT,
        )


def test_r7_positive_inputs_preserve_existing_dimension_calculation():
    frames = derive_inner_door_frames(
        "door-A", spans={"top": 696., "left": 1098., "right": 1098.},
        thickness=2., included_sides=("top", "left", "right"),
    )
    assert [frame.blank_width for frame in frames] == [90., 90., 110.]
    assert inner_door_frame_formed_occupation(2.) == 50.
    strip = build_strip_outline(StripFoldChain((FoldSegment("a", 20.), FoldSegment("b", 40.)), 500.))
    assert strip[2].x == 60. and strip[2].y == 500.
    cap = EndCapGeometry(800., 350., 2., 46., 22., 22., 20., 20.)
    assert build_endcap_topology(cap).left_bend.p1.x == 22.
