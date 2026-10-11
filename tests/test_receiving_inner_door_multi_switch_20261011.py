# -*- coding: utf-8 -*-
"""One inner-door layer can contain an ordered, repeated list of NFB switches."""
import json

import pytest

from ae_engine.receiving_shared_settings import (
    switch_filenames_in_layer, pack_switch_layer, switch_model_layers,
    validate_setting, edit_setting, setting_value,
)
from ae_engine.receiving_inner_door_candidates import (
    create_inner_candidate, update_inner_candidate, duplicate_inner_candidate,
    inner_config,
)
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from ae_engine.receiving_inner_door_pairing import paired_bay_parts


def test_legacy_single_switch_data_remains_identical_after_validation():
    original = ["BH_25X95.dxf", ""]
    assert validate_setting("inner_door_models", original) == original
    assert switch_model_layers(original) == original
    assert switch_filenames_in_layer(original[0]) == ("BH_25X95.dxf",)
    assert switch_filenames_in_layer(original[1]) == ()
    assert pack_switch_layer(()) == ""
    assert pack_switch_layer(("A.dxf",)) == "A.dxf"


def test_multiple_switches_in_same_layer_preserve_quantity_and_order():
    source = [["A.dxf", "A.dxf", "B.dxf"], ["C.DXF", "B.dxf"]]
    validated = validate_setting("inner_door_models", source)
    assert validated == source
    assert pack_switch_layer(source[0]) == source[0]
    assert switch_filenames_in_layer(validated[0]).count("A.dxf") == 2
    assert len(switch_filenames_in_layer(validated[0])) == 3
    assert validated[1] == ["C.DXF", "B.dxf"]
    assert json.loads(json.dumps(validated)) == source
    validated[0].pop()
    assert source[0] == ["A.dxf", "A.dxf", "B.dxf"]


@pytest.mark.parametrize("bad", [
    [["bad.csv", "A.dxf"], ""],
    [["../bad.dxf"], ""],
    [["a/b.dxf"], ""],
    [["a\\b.dxf"], ""],
    [[None], ""],
    [[3], ""],
    [[[]], ""],
    [[""], ""],
    [[".dxf"], ""],
    ["A.dxf", {"name": "B.dxf"}],
    ["A.dxf"],
])
def test_invalid_switch_instance_values_are_rejected(bad):
    with pytest.raises(ValueError):
        validate_setting("inner_door_models", bad)


def test_multi_switch_inner_versions_crud_copy_and_layer_guard():
    one, v1 = create_inner_candidate(None, {
        "layers": 1,
        "models": [["A.dxf", "A.dxf", "B.dxf"], ""],
    })
    assert inner_config(one, v1)["models"][0] == ["A.dxf", "A.dxf", "B.dxf"]
    two, v2 = duplicate_inner_candidate(one, v1)
    changed = update_inner_candidate(two, v2, {
        "layers": 2,
        "models": [["A.dxf", "B.dxf"], ["C.dxf", "C.dxf"]],
    })
    assert inner_config(changed, v2)["models"][1] == ["C.dxf", "C.dxf"]
    assert inner_config(changed, v1)["models"][1] == ""
    with pytest.raises(ValueError, match="單層"):
        create_inner_candidate(one, {
            "layers": 1,
            "models": [["A.dxf", "B.dxf"], ["C.dxf"]],
        })


def test_real_set_bay_multi_switch_assignment_does_not_touch_endcaps():
    adapter = ReceivingSetBayAdapter(
        resize_receiving_bays(
            new_receiving_layout(width=800, height=1600, depth=350),
            set_index=0, bay_count=2,
        )
    )
    config = {"layers": 2, "models": [["A.dxf", "A.dxf"], ["B.dxf", "C.dxf"]]}
    selected = adapter.apply_inner_door_candidate_to_bays(config, 0, (0, 1))
    assert selected == (0, 1)
    for bi in (0, 1):
        row = adapter.layout["sets"][0]
        assert setting_value(row, bi, "inner_door_models") == config["models"]
        pair = paired_bay_parts(adapter.layout, set_index=0, bay_index=bi)
        assert pair["inner_door"]["models"] == config["models"]
        assert pair["head_features"] == []
        assert pair["tail_features"] == []
    adapter.apply_inner_door_candidate_to_bays(
        {"layers": 1, "models": [["D.dxf", "D.dxf", "D.dxf"], ""]},
        0, (1,),
    )
    assert setting_value(adapter.layout["sets"][0], 0, "inner_door_models") == config["models"]
    assert setting_value(adapter.layout["sets"][0], 1, "inner_door_models")[0] == [
        "D.dxf", "D.dxf", "D.dxf",
    ]
