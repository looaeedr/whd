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
    snap = _source_snapshot(shallow="2P400")  # same depth => LEFT/RIGHT ambiguous
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
