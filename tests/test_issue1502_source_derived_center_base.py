# -*- coding: utf-8 -*-
"""#1502: real current Set/Bay + NFB numeric CSV -> measured CENTER source.

This exercises the existing source-geometry owner, not a custom DXF writer
or a whole-cabinet manufacturing release.
"""
from copy import deepcopy
from dataclasses import replace

import ezdxf
import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import build_part_render_data, generate_part
from ae_engine.receiving_base_plate_config import (
    receiving_base_plate_values, receiving_base_plate_blank_dimensions,
)
from ae_engine.receiving_weld_ear_policy import receiving_source_fixing_pitch_x_mm


def _source_snapshot(*, width=800., side_t=2., shallow="3P125SN"):
    holes = [
        {"physical_hole_id": "nfb:0", "slot_index": 0,
         "model_filename": "nfbv5:士林:2P400", "source_brand": "士林"},
        {"physical_hole_id": "nfb:1", "slot_index": 1,
         "model_filename": "nfbv5:士林:" + shallow, "source_brand": "士林"},
    ]
    cfg = {"layer_count": 1, "holes": holes}
    return {
        "model": "受電箱", "w": width, "h": 1600., "d": 350., "t": side_t,
        "receiving_layout": {"sets": [{
            "stable_id": "S", "bays": [{
                "stable_id": "B", "nfb_config_submitted": True,
                "nfb_config": deepcopy(cfg),
            }],
        }]},
        "_receiving_runtime_selection": {
            "set_index": 0, "bay_index": 0, "set_id": "S", "bay_id": "B",
        },
        "nfb_config_submitted": True, "nfb_config": cfg,
    }


def _spec(snap):
    val = receiving_base_plate_values(snap)
    return BasePlatePartSpec(
        width=snap["w"], height=val["h"], thickness=snap["t"],
        shrink_top=val["base_plate_shrink_top"],
        shrink_bottom=val["base_plate_shrink_bottom"],
        shrink_left=val["base_plate_shrink_left"],
        shrink_right=val["base_plate_shrink_right"],
        bend=val["base_plate_bend"], model_name="受電箱",
        receiving_bend_pattern=val["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=val["receiving_nfb_depth_pair_mm"],
    )


def test_submitted_source_dual_depth_derives_original_772x240_without_manual_config(tmp_path):
    snap = _source_snapshot()
    assert "receiving_base_plate" not in snap
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert values["receiving_nfb_depth_pair_mm"] == (107., 72.)
    assert values["h"] == 280.
    assert tuple(values[k] for k in (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
        "base_plate_bend",
    )) == (20., 20., 85., 85., 20.)
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    render = build_part_render_data(_spec(snap))
    assert render.unfolded_topology.width == 772.
    # The actual source reference gives 40/73/699/732, not a false 31.
    stations = sorted({
        round(float(g.position), 5) for g in render.fold_guides
        if g.axis == "x"
    })
    assert stations == [40., 73., 699., 732.]
    assert render.metadata["receiving_nfb_base_mfg2_release_approved"] is False
    output = tmp_path / "center_geometry_unit_only.dxf"
    generate_part(_spec(snap), output)
    doc = ezdxf.readfile(output)
    assert doc.modelspace().query("LWPOLYLINE")


@pytest.mark.parametrize("width,expected_blank,expected_pitch", [
    (800., 772., 670.), (750., 722., 620.), (900., 872., 770.),
])
def test_width_changes_rederive_mount_pitch_and_blank_without_w800_magic(
    width, expected_blank, expected_pitch,
):
    snap = _source_snapshot(width=width)
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=width, box_side_thickness_mm=2.,
    ) == expected_pitch
    assert receiving_base_plate_blank_dimensions(snap) == (expected_blank, 240.)


def test_csv_depth_difference_updates_actual_bends_not_historical_33():
    snap = _source_snapshot(shallow="2P125SN")  # 士林 depth68, 107-68-T2=37
    values = receiving_base_plate_values(snap)
    assert values["receiving_nfb_depth_pair_mm"] == (107., 68.)
    assert receiving_base_plate_blank_dimensions(snap) == (780., 240.)
    render = build_part_render_data(_spec(snap))
    station = sorted(float(g.position) for g in render.fold_guides if g.axis == "x")
    assert station == pytest.approx([40., 77., 703., 740.])


def test_no_submitted_nfb_and_ambiguous_flat_do_not_invent_a_plate():
    snap = _source_snapshot()
    snap["nfb_config_submitted"] = False
    assert receiving_base_plate_values(snap) is None
    snap = _source_snapshot(shallow="2P400")  # old slot1 owner is invalid for flat
    assert receiving_base_plate_values(snap) is None


def test_current_bay_identity_mismatch_is_not_cross_bay_mfg_source():
    snap = _source_snapshot()
    snap["_receiving_runtime_selection"]["bay_id"] = "OTHER"
    with pytest.raises(ValueError, match="identity drift"):
        receiving_base_plate_values(snap)


def test_center_source_is_t2_only_and_does_not_guess_ear_thickness():
    snap = _source_snapshot(side_t=3.)
    with pytest.raises(ValueError, match="RECEIVING_CENTER_SOURCE_REQUIRES_T2"):
        receiving_base_plate_values(snap)


def _submitted_one_shihlin_400(*, width=800.):
    snap = _source_snapshot(width=width)
    hole = snap["nfb_config"]["holes"][0]
    snap["nfb_config"]["holes"] = [hole]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    return snap


def test_source_left_400_csv_pitch_derives_710x300_without_manual_config(tmp_path):
    snap = _submitted_one_shihlin_400()
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert values["receiving_nfb_reference_depth_mm"] == 107.
    assert values["h"] == 340.
    assert tuple(values[k] for k in (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right", "base_plate_bend",
    )) == (20., 20., 45., 45., 20.)
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)
    render = build_part_render_data(_spec(snap))
    assert render.unfolded_topology.width == 710.
    assert sorted(float(g.position) for g in render.fold_guides if g.axis == "y") == [20., 280.]
    output = tmp_path / "left_geometry_unit_only.dxf"
    generate_part(_spec(snap), output)
    assert ezdxf.readfile(output).modelspace().query("LWPOLYLINE")


@pytest.mark.parametrize("width,blank,pitch", [
    (800., 710., 670.), (750., 660., 620.), (900., 810., 770.),
])
def test_left_source_selected_by_400_screw_pitch_scales_with_real_side_63(
    width, blank, pitch,
):
    snap = _submitted_one_shihlin_400(width=width)
    assert receiving_base_plate_blank_dimensions(snap) == (blank, 300.)
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=width, box_side_thickness_mm=2.
    ) == pitch


def test_no_arbitrary_flat_right_selection_for_other_source_model():
    snap = _submitted_one_shihlin_400()
    snap["nfb_config"]["holes"][0]["model_filename"] = "nfbv5:士林:3P125SN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert receiving_base_plate_values(snap) is None


def test_two_tier_committed_holes_do_not_reuse_one_root_flat_plate():
    snap = _submitted_one_shihlin_400()
    snap["nfb_config"]["layer_count"] = 2
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    assert receiving_base_plate_values(snap) is None


def test_submitted_csv_source_overrides_stale_saved_pattern_and_dimensions():
    # Real old projects may have a manually chosen RIGHT pattern. That is
    # neither a manufacturing authority nor a reason to bypass submitted CSV.
    snap = _source_snapshot()
    snap["receiving_base_plate"] = {
        "pattern": "RIGHT_FLAT_SIDE", "height": 360.,
        "shrink_top": 20., "shrink_bottom": 20.,
        "shrink_left": 45., "shrink_right": 45., "bend": 20.,
    }
    selected = receiving_base_plate_values(snap)
    assert selected["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert selected["receiving_nfb_depth_pair_mm"] == (107., 72.)
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    # Source resolution must not overwrite operator project data on a read.
    assert snap["receiving_base_plate"]["pattern"] == "RIGHT_FLAT_SIDE"


def test_submitted_single_400_source_replaces_obsolete_manual_width():
    snap = _submitted_one_shihlin_400(width=750.)
    snap["receiving_base_plate"] = {
        "pattern": "LEFT_FLAT_SIDE", "height": 340.,
        "shrink_top": 20., "shrink_bottom": 20.,
        # Stale W800-derived margins cannot be used at a new physical width.
        "shrink_left": 85., "shrink_right": 85., "bend": 20.,
    }
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert values["base_plate_shrink_left"] == 45.
    assert receiving_base_plate_blank_dimensions(snap) == (660., 300.)
    # Even when width varies, installed slot pitch is always from current W/T.
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=750., box_side_thickness_mm=2.,
    ) == 620.


def test_unknown_submitted_csv_plate_cannot_borrow_manual_pattern():
    snap = _submitted_one_shihlin_400()
    snap["nfb_config"]["holes"][0]["model_filename"] = "nfbv5:士林:3P125SN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    snap["receiving_base_plate"] = {
        "pattern": "RIGHT_FLAT_SIDE", "height": 360.,
        "shrink_top": 20., "shrink_bottom": 20.,
        "shrink_left": 45., "shrink_right": 45., "bend": 20.,
    }
    assert receiving_base_plate_values(snap) is None
    assert receiving_base_plate_blank_dimensions(snap) is None


def test_unsubmitted_legacy_edit_remains_previewable_but_not_csv_certified():
    snap = _source_snapshot()
    snap["nfb_config_submitted"] = False
    old = {
        "pattern": "LEFT_FLAT_SIDE", "height": 340.,
        "shrink_top": 20., "shrink_bottom": 20.,
        "shrink_left": 45., "shrink_right": 45., "bend": 20.,
    }
    snap["receiving_base_plate"] = old
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert values["receiving_nfb_reference_depth_mm"] is None


def _one_layer_pair(second_model="2P400", second_brand="士林"):
    snap = _submitted_one_shihlin_400()
    second = deepcopy(snap["nfb_config"]["holes"][0])
    second.update(
        physical_hole_id="nfb:second", slot_index=1,
        model_filename=f"nfbv5:{second_brand}:{second_model}",
        source_brand=second_brand,
    )
    snap["nfb_config"]["holes"].append(second)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    return snap


@pytest.mark.parametrize("second_model", ["2P400", "3P400SN"])
def test_real_left_two_original_quartets_allow_second_nfb_slot_and_alias(second_model):
    # Two on ONE actual mounting tier; no new manual plate, no moving
    # ear mounting X, and the source-derived 710x300 blank remains identical.
    snap = _one_layer_pair(second_model)
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)
    assert receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=800., box_side_thickness_mm=2.,
    ) == 670.


def test_one_tier_cross_brand_similar_pitch_not_identical_plate_source():
    # 伍菱 3P400SN has pitch/depth equal but its opening differs.
    snap = _one_layer_pair("3P400SN", "伍菱")
    with pytest.raises(ValueError, match="DIFFERENT_MODELS"):
        receiving_base_plate_values(snap)


def test_flat_second_slot_cannot_be_misread_as_third_switch_row():
    snap = _one_layer_pair()
    snap["nfb_config"]["holes"][1]["slot_index"] = 2
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    # The source adapter intentionally converts this unsupported same-tier
    # slot into an unresolved physical blank, not a GUI-fatal exception.
    assert receiving_base_plate_values(snap) is None
