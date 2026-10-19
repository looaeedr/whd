# -*- coding: utf-8 -*-
"""#1503 quantity common box must retain operator CSV NFB rows on reprojection.

These checks validate one prerequisite for the real GUI 2D/3D acceptance test
in test_issue1503_single_gui_real_tier_2d3d.py. They are not manufacturing
approval and do not bypass any physical Base Plate/EAR proof gates.
"""
from copy import deepcopy

from ae_engine.receiving_quantity_box import (
    project_common_box, update_common_box, normalize_common_box,
)
from ae_engine.receiving_shared_settings import setting_value


def test_two_tier_csv_models_and_heights_survive_reproject_and_detached_copy():
    initial = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    rows = ["nfbv5:士林:2P400", "nfbv5:士林:2P400"]
    changed = update_common_box(initial, {
        "inner_door_layers": 2,
        "inner_door_models": rows,
        "inner_door_layer_heights_mm": [300., 800.],
    })
    assert initial["receiving_quantity_box"].get("inner_door_models") is None
    assert initial["receiving_inner_door_layers"] == 1
    assert changed["receiving_quantity_box"]["inner_door_layers"] == 2
    assert changed["receiving_quantity_box"]["inner_door_models"] == rows
    assert changed["receiving_quantity_box"]["inner_door_layer_heights_mm"] == [300., 800.]
    for snap in (changed, project_common_box(deepcopy(changed))):
        assert snap["receiving_inner_door_layers"] == 2
        assert snap["receiving_inner_door_models"] == rows
        assert snap["receiving_inner_door_layer_heights_mm"] == [300., 800.]
        panel = snap["receiving_layout"]["sets"][0]
        assert setting_value(panel, 0, "inner_door_layers") == 2
        assert setting_value(panel, 0, "inner_door_models") == rows
        assert setting_value(panel, 0, "inner_door_layer_heights_mm") == [300., 800.]


def test_original_quantity_box_without_csv_config_keeps_previous_family_defaults():
    old = normalize_common_box({"w": 800, "h": 1600, "d": 350})
    assert old["inner_door_layers"] == 1
    assert "inner_door_models" not in old
    assert "inner_door_layer_heights_mm" not in old


def test_malformed_source_model_or_reversed_nfb_y_fails_before_commit():
    original = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    for wrong in (
        {"inner_door_models": ["not-from-CSV", ""]},
        {"inner_door_layer_heights_mm": [800., 300.]},
    ):
        from pytest import raises
        with raises(ValueError):
            update_common_box(original, wrong)


def test_quantity_selected_version_nfb_is_projected_to_one_actual_bay_only():
    from phase6_quantity_model import QuantityModel
    from ae_engine.receiving_nfb_persistence import normalize_nfb_config
    from ae_engine.receiving_nfb_model_identity import numeric_model_ref
    baseline = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    q = QuantityModel.from_payload(baseline["quantity"]) if "quantity" in baseline else QuantityModel()
    ref = numeric_model_ref("士林", "2P400")
    typed = normalize_nfb_config({
        "layer_count": 2,
        "holes": [
            {"physical_hole_id": "upper:nfb:0", "model_filename": ref,
             "source_brand": "士林", "layer_count": 2, "layer_index": 0,
             "slot_index": 0, "manual_x_state": "UNVERIFIED_BASIS"},
            {"physical_hole_id": "upper:nfb:1", "model_filename": ref,
             "source_brand": "士林", "layer_count": 2, "layer_index": 1,
             "slot_index": 0, "manual_x_state": "UNVERIFIED_BASIS"},
        ],
    })
    q.set_version_nfb_config(q.selected_version_id, submitted=True, config=typed)
    baseline["quantity"] = q.snapshot()
    projected = project_common_box(baseline)
    bay = projected["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    assert bay["nfb_config"] == typed
    assert projected["nfb_config"] == typed
    # Reprojection from saved authority must be idempotent and preserve
    # the exact physical-hole identity in every NFB layer.
    again = project_common_box(projected)
    assert again["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] == typed
    # Selecting a newly unconfigured version must not borrow old NFB holes.
    q.add_version()
    q.set_version_nfb_config(q.selected_version_id, submitted=False)
    projected["quantity"] = q.snapshot()
    next_view = project_common_box(projected)
    assert next_view.get("nfb_config_submitted") is None
    assert next_view["receiving_layout"]["sets"][0]["bays"][0].get("nfb_config_submitted") is not True


def test_real_base_plate_selection_is_owned_by_quantity_box_not_volatile_alias():
    from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot
    cfg = _snapshot()["receiving_base_plate"]
    old = project_common_box({
        "model": "受電箱", "active_mode": "quantity", "t": 2.,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    })
    chosen = update_common_box(old, {"receiving_base_plate": cfg})
    assert chosen["receiving_quantity_box"]["receiving_base_plate"] == cfg
    assert chosen["receiving_base_plate"] == cfg
    assert project_common_box(deepcopy(chosen))["receiving_base_plate"] == cfg
    restored = update_common_box(chosen, {"receiving_base_plate": None})
    assert "receiving_base_plate" not in restored
    assert "receiving_base_plate" not in restored["receiving_quantity_box"]
