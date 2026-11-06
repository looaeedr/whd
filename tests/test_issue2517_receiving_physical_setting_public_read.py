# -*- coding: utf-8 -*-
"""#2517: Fold Designer receives per-Bay physical values only via public Engine."""
from copy import deepcopy
from inspect import getsource

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import setting_value as original_engine_owner
from gui_modules.application import fold_designer_composition_receiving as gui


def _layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )


def test_public_per_bay_setting_read_matches_existing_engine_owner_without_mutating_source():
    layout = _layout()
    original = deepcopy(layout)
    row = layout["sets"][0]
    kinds = (
        "inner_door_layers", "inner_door_models", "inner_door_features",
        "inner_door_layer_heights_mm", "head_version_id",
        "tail_version_id", "inner_door_version_id",
    )
    for index in (0, 1):
        for kind in kinds:
            assert gui._receiving_setting_value(row, index, kind) == (
                original_engine_owner(row, index, kind)
            )
            value, matching = manufacturing_api.project_receiving_shared_setting_group(
                row, index, kind,
            )
            assert value == gui._receiving_setting_value(row, index, kind)
            assert index in matching
    assert layout == original


def test_public_per_bay_value_reads_linked_and_independently_edited_actual_bays():
    layout = _layout()
    edited = manufacturing_api.edit_receiving_shared_setting(
        layout, set_index=0, bay_index=1,
        kind="inner_door_layers", value=2,
    )
    row = edited["sets"][0]
    assert gui._receiving_setting_value(row, 0, "inner_door_layers") == 1
    assert gui._receiving_setting_value(row, 1, "inner_door_layers") == 2
    assert gui._receiving_setting_value(row, 1, "inner_door_models") == ["", ""]
    assert layout == _layout()
    with pytest.raises((ValueError, IndexError, KeyError, TypeError)):
        gui._receiving_setting_value(row, 3, "inner_door_layers")
    with pytest.raises(ValueError):
        gui._receiving_setting_value(row, 0, "unknown-manufacturing-setting")


def test_fold_designer_gui_no_longer_imports_engine_private_setting_value():
    source = getsource(gui)
    assert "from ae_engine.receiving_shared_settings import setting_value" not in source
    assert source.count("_receiving_setting_value(") >= 10
    assert "project_receiving_shared_setting_group(" in getsource(
        gui._receiving_setting_value
    )
