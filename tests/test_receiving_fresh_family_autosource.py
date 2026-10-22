# -*- coding: utf-8 -*-
"""Fresh Receiving switches directly expose one CSV-backed NFB and its actual parts."""
from copy import deepcopy

import pytest

from ae_engine.cabinet_types import policy
from ae_engine.receiving_fresh_nfb_defaults import (
    seed_fresh_receiving_nfb_source,
    seed_fresh_receiving_quantity_nfb_source,
)
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from ae_engine.receiving_shared_settings import setting_value
from ae_engine.sheetmetal_feature_core import ProfileFeature
from phase6_receiving_modes import fresh_receiving_mode, ReceivingModeSession
from phase6_project_file import _decode, _encode


MODEL = numeric_model_ref("士林", "2P400")


def _fresh_set():
    return seed_fresh_receiving_nfb_source(
        policy.apply_fresh_family_defaults({"t": 2.0}, "受電箱"),
    )


def _assert_physical_source(data):
    assert data["model"] == "受電箱"
    assert data["nfb_config_submitted"] is True
    assert data["nfb_config"]["layer_count"] == 1
    assert len(data["nfb_config"]["holes"]) == 1
    hole = data["nfb_config"]["holes"][0]
    assert hole["model_filename"] == MODEL
    assert hole["manual_x_state"] == "UNVERIFIED_BASIS"
    assert hole["manual_x_mm"] is None
    panel = next(p for p in policy.derive_inner_door_panels(data)
                 if str(p.cell_key) == "0:0")
    features = data["part_features"][panel.stable_id]
    assert len(features) == 1 and isinstance(features[0], ProfileFeature)
    assert features[0].source_type == "NFB_CSV_SOURCE"
    assert features[0].layer == "CUTTING"
    assert dict(features[0].source_params)["model"] == "2P400"
    plate = receiving_base_plate_values(data)
    assert plate is not None
    assert plate["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    ears = receiving_base_fixing_plate_previews(
        data, available_parts=("box_body", "base_plate"),
    )
    assert len(ears) == 2
    assert {ear.parent_part_id for ear in ears} == {"base_plate"}


def test_first_family_switch_materializes_real_one_tier_one_nfb_and_derived_parts():
    data = _fresh_set()
    _assert_physical_source(data)
    row = data["receiving_layout"]["sets"][0]
    assert row["bays"][0]["nfb_config"] == data["nfb_config"]
    assert setting_value(row, 0, "inner_door_models") == [MODEL, ""]
    assert setting_value(row, 0, "inner_door_layers") == 1
    assert setting_value(row, 0, "inner_door_layer_heights_mm") == [330., 830.]
    assert len(setting_value(row, 0, "inner_door_features")) == 1


def test_existing_nfb_is_never_replaced_by_reenter_or_save_reload():
    data = _fresh_set()
    before = deepcopy(data)
    again = seed_fresh_receiving_nfb_source(data)
    assert again == before
    restored = _decode(_encode(data))
    assert restored["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] == (
        data["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]
    )


def test_only_first_explicit_auto_nfb_mode_switch_seeds_current_physical_box():
    virgin = fresh_receiving_mode(
        "set_bay", {"w": 800, "h": 1600, "d": 350}, auto_nfb=True,
    )
    _assert_physical_source(virgin)
    session = ReceivingModeSession(virgin)
    assert session.switch("quantity", dimensions={"w": 800, "h": 1600, "d": 350})
    quantity = session.snapshot()
    _assert_physical_source(quantity)
    assert quantity["receiving_quantity_box"]["inner_door_models"] == [MODEL, ""]
    assert session.switch("set_bay", dimensions={"w": 800, "h": 1600, "d": 350})
    _assert_physical_source(session.snapshot())
    # Returning to an initialized mode restores its edits and does not reseed.
    assert session.switch("quantity")
    assert session.snapshot() == quantity


def test_fresh_set_mode_auto_seed_is_opt_in_not_project_file_migration():
    bare = fresh_receiving_mode("set_bay", {"w": 800, "h": 1600, "d": 350})
    assert bare.get("nfb_config_submitted") is not True
    new = fresh_receiving_mode(
        "set_bay", {"w": 800, "h": 1600, "d": 350}, auto_nfb=True,
    )
    _assert_physical_source(new)


def test_fresh_quantity_model_source_stays_single_owner_on_reprojection():
    new = fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350}, auto_nfb=True,
    )
    _assert_physical_source(new)
    from ae_engine.receiving_quantity_box import project_common_box
    projected = project_common_box(new)
    _assert_physical_source(projected)
    assert projected["nfb_config"] == new["nfb_config"]


def test_unrelated_existing_project_not_overwritten_by_first_switch_helper():
    data = _fresh_set()
    config = deepcopy(data["nfb_config"])
    config["holes"][0]["manual_x_state"] = "RECONFIRM_REQUIRED"
    config = normalize_nfb_config(config)
    data["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = config
    assert seed_fresh_receiving_nfb_source(data)["nfb_config"] == config
    assert seed_fresh_receiving_nfb_source({"model":"金庫型"}) == {"model":"金庫型"}


def test_manufacturing_transport_keeps_real_set_bay_indices_as_integers():
    from phase6_manufacturing_contracts import (
        freeze_manufacturing_value, thaw_manufacturing_value,
    )
    source = _fresh_set()
    original = source["_receiving_runtime_selection"]
    received = thaw_manufacturing_value(freeze_manufacturing_value(source))
    runtime = received["_receiving_runtime_selection"]
    assert runtime == original
    assert type(runtime["set_index"]) is int
    assert type(runtime["bay_index"]) is int
    _assert_physical_source(received)
