# -*- coding: utf-8 -*-
"""Fresh default NFB is real CSV, not a silent submitted/manufactured part."""
from copy import deepcopy

from ae_engine.receiving_fresh_nfb_defaults import (
    initial_fresh_receiving_nfb_models,
)
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import model_spec


def test_first_single_draft_defaults_exactly_one_csv_shihlin_2p400():
    blank = ["", ""]
    source = initial_fresh_receiving_nfb_models(
        blank, layer_count=1, selected_brand="士林",
    )
    assert blank == ["", ""], "do not mutate saved project state"
    assert source == [numeric_model_ref("士林", "2P400"), ""]
    spec = model_spec("士林", "2P400")
    assert spec.dimensionally_complete
    assert spec.depth_mm == 107
    assert spec.opening_mm == (57, 96)
    assert spec.screw_pitch_mm == (44, 194)


def test_existing_nfb_and_other_global_brand_are_never_overwritten():
    keep = ["nfbv5:士林:2P125SN", "nfbv5:士林:2P400"]
    assert initial_fresh_receiving_nfb_models(
        keep, layer_count=2, selected_brand="士林",
    ) == keep
    assert initial_fresh_receiving_nfb_models(
        ["", ""], layer_count=1, selected_brand="東元",
    ) == ["", ""]
    assert initial_fresh_receiving_nfb_models(
        ["", ""], layer_count=2, selected_brand="士林",
    ) == ["", ""]
    assert initial_fresh_receiving_nfb_models(
        ["nfbv5:士林:2P400", ""], layer_count=1, selected_brand="士林",
    ) == ["nfbv5:士林:2P400", ""]


def test_unsubmitted_draft_does_not_manufacture_or_edit_original():
    from ae_engine.receiving_quantity_box import project_common_box
    source = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    before = deepcopy(source)
    fresh = initial_fresh_receiving_nfb_models(
        source["receiving_quantity_box"].get("inner_door_models", ["", ""]),
        layer_count=1, selected_brand="士林",
    )
    assert fresh[0] == "nfbv5:士林:2P400"
    assert source == before
    assert source.get("nfb_config_submitted") is not True
    assert source.get("receiving_base_plate") is None


def test_submitted_single_400_resolves_source_left_without_manual_base():
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.receiving_nfb_persistence import normalize_nfb_config
    from ae_engine.receiving_quantity_box import project_common_box
    from phase6_quantity_model import QuantityModel
    snap = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    model = QuantityModel()
    config = normalize_nfb_config({
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "inner_door:upper:panel:nfb:layer:0:slot:0",
            "model_filename": numeric_model_ref("士林", "2P400"),
            "source_brand": "士林", "layer_count": 1,
            "layer_index": 0, "slot_index": 0,
            "manual_x_state": "UNVERIFIED_BASIS",
        }],
    })
    model.set_version_nfb_config(model.selected_version_id, submitted=True, config=config)
    snap["quantity"] = model.snapshot()
    snap = project_common_box(snap)
    resolved = receiving_base_plate_values(snap)
    assert snap["nfb_config_submitted"] is True
    assert "receiving_base_plate" not in snap
    assert resolved is not None
    assert resolved["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert resolved["h"] == 340
