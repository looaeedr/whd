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
    assert setting_value(row, 0, "inner_door_layer_heights_mm") == [550., 830.]
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
    assert new["receiving_inner_door_layer_heights_mm"] == [550., 830.]
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
    assert received["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] == source["nfb_config"]


def _two_tier_candidate_with_real_csv(source):
    from ae_engine.receiving_nfb_csv_editor_features import (
        editor_nfb_features_from_csv,
    )
    panel = next(p for p in policy.derive_inner_door_panels(source)
                 if str(p.cell_key) == "0:0")
    payload = {
        "layers": 2,
        "models": [MODEL, MODEL],
        "layer_heights_mm": [300.0, 830.0],
    }
    features = editor_nfb_features_from_csv(source, payload)
    assert len(features) == 2
    return {**payload, "features": {panel.stable_id: list(features)}}, panel.stable_id


def test_explicit_candidate_apply_replaces_initial_one_nfb_without_double_cutting():
    from gui_modules.application.receiving_set_bay_adapter import (
        ReceivingSetBayAdapter,
    )
    from ae_engine.receiving_layout import resize_receiving_bays
    initial = _fresh_set()
    old_bay = deepcopy(initial["receiving_layout"]["sets"][0]["bays"][0])
    candidate, part_id = _two_tier_candidate_with_real_csv(initial)
    expanded = resize_receiving_bays(
        initial["receiving_layout"], set_index=0, bay_count=2,
    )
    other_before = deepcopy(expanded["sets"][0]["bays"][1])
    adapter = ReceivingSetBayAdapter(expanded)
    old = adapter.layout
    assert old["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert adapter.apply_inner_door_candidate_to_bays(
        candidate, 0, (0,), version_id="inner-door-v1",
    ) == (0,)
    after = adapter.layout
    changed = after["sets"][0]["bays"][0]
    assert changed["stable_id"] == old_bay["stable_id"]
    assert changed["nfb_config_submitted"] is True
    assert changed["nfb_config"]["layer_count"] == 2
    assert len(changed["nfb_config"]["holes"]) == 2
    assert [hole["layer_index"] for hole in changed["nfb_config"]["holes"]] == [0, 1]
    assert len(setting_value(after["sets"][0], 0, "inner_door_features")[part_id]) == 2
    assert all(hole["physical_hole_id"].startswith(changed["stable_id"] + ":")
               for hole in changed["nfb_config"]["holes"])
    assert after["sets"][0]["bays"][1] == other_before
    # Re-applying the same version must replace, never append duplicate holes.
    adapter.apply_inner_door_candidate_to_bays(
        candidate, 0, (0,), version_id="inner-door-v1",
    )
    assert adapter.layout == after


def test_submitted_nfb_rejects_mixed_manual_cutting_with_no_partial_change():
    from gui_modules.application.receiving_set_bay_adapter import (
        ReceivingSetBayAdapter,
    )
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
    original = _fresh_set()
    candidate, part_id = _two_tier_candidate_with_real_csv(original)
    candidate["features"][part_id].append(
        CircleFeature(
            diameter=5.0, anchor=FeatureAnchor.TOP_RIGHT,
            offset=Vec2(-20.0, -20.0),
        )
    )
    adapter = ReceivingSetBayAdapter(original["receiving_layout"])
    before = adapter.layout
    with pytest.raises(ValueError, match="非 NFB CUTTING"):
        adapter.apply_inner_door_candidate_to_bays(
            candidate, 0, (0,), version_id="inner-door-v1",
        )
    assert adapter.layout == before


def test_explicit_quantity_allocation_replaces_submitted_one_nfb_same_source():
    from gui_modules.application.receiving_set_bay_adapter import (
        ReceivingSetBayAdapter,
    )
    from ae_engine.receiving_inner_door_candidates import create_inner_candidate
    initial = _fresh_set()
    config, part_id = _two_tier_candidate_with_real_csv(initial)
    library, version = create_inner_candidate(None, config)
    adapter = ReceivingSetBayAdapter(initial["receiving_layout"])
    assert adapter.apply_inner_door_quantity_configuration(
        library, {version: 1}, {(0, 0): version}, expected_counts=(1,),
    ) == 1
    bay = adapter.layout["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    assert bay["nfb_config"]["layer_count"] == 2
    assert len(bay["nfb_config"]["holes"]) == 2
    assert len(setting_value(adapter.layout["sets"][0], 0, "inner_door_features")[part_id]) == 2
