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
