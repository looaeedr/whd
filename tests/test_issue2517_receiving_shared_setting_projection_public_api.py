# -*- coding: utf-8 -*-
"""#2517: shared-setting equality and switch-brand inventory are Engine-owned."""
from copy import deepcopy
from inspect import getsource

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import setting_value
from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
from gui_modules.application import receiving_set_bay_controls as controls
from gui_modules.application import receiving_multi_settings_window as multi


def _physical_row():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )
    layout = api.edit_receiving_shared_setting_for_bays(
        layout, set_index=0, bay_indices=(0, 2),
        kind="inner_door_layers", value=2,
    )
    return layout["sets"][0]


def test_public_brand_choices_are_exact_canonical_engine_inventory():
    catalog = api.receiving_operator_switch_brand_choices()
    assert type(catalog) is tuple
    assert catalog == RECEIVING_SWITCH_BRANDS
    assert ae_engine.receiving_operator_switch_brand_choices is api.receiving_operator_switch_brand_choices
    for brand in catalog:
        assert api.require_receiving_operator_brand(brand) == brand
    with pytest.raises(ValueError, match="不支援"):
        api.require_receiving_operator_brand("invalid-brand")


def test_actual_bay_value_and_equal_values_match_original_engine_owner():
    row = _physical_row()
    before = deepcopy(row)
    assert api.project_receiving_shared_setting_group(
        row, 0, "inner_door_layers",
    ) == (2, (0, 2))
    assert api.project_receiving_shared_setting_group(
        row, 1, "inner_door_layers",
    ) == (1, (1,))
    assert api.project_receiving_shared_setting_group(
        row, 1, "inner_door_layers", preview_value=2,
    ) == (2, (0, 2))
    assert api.project_receiving_shared_setting_group(
        row, 2, "inner_door_layers", preview_value=1,
    ) == (1, (1,))
    assert [setting_value(row, i, "inner_door_layers") for i in range(3)] == [2, 1, 2]
    assert row == before
    assert ae_engine.project_receiving_shared_setting_group is api.project_receiving_shared_setting_group


def test_uncommitted_back_panel_preview_does_not_write_bay_or_shared_ref():
    row = _physical_row()
    before = deepcopy(row)
    active, same = api.project_receiving_shared_setting_group(
        row, 1, "back_panel_mode",
    )
    assert (active, same) == ("FULL", (0, 1, 2))
    assert api.project_receiving_shared_setting_group(
        row, 1, "back_panel_mode", preview_value="half",
    ) == ("HALF", ())
    assert row == before


def test_detached_feature_values_and_invalid_operator_source_are_fail_closed():
    row = _physical_row()
    before = deepcopy(row)
    value, matches = api.project_receiving_shared_setting_group(
        row, 0, "head_features",
    )
    assert value == [] and matches == (0, 1, 2)
    value.append("not-a-feature")
    assert row == before
    for bad_index in (True, -1, 3, 1.0, None):
        with pytest.raises(IndexError):
            api.project_receiving_shared_setting_group(
                row, bad_index, "inner_door_layers",
            )
    for bad in (True, 2.0, 3, "2", [], None):
        with pytest.raises(ValueError):
            api.project_receiving_shared_setting_group(
                row, 1, "inner_door_layers", preview_value=bad,
            )
    with pytest.raises(ValueError):
        api.project_receiving_shared_setting_group(row, 0, "missing_kind")
    with pytest.raises(ValueError):
        api.project_receiving_shared_setting_group({"bays": None}, 0, "inner_door_layers")
    assert row == before


def test_gui_no_longer_owns_real_bay_match_or_private_brand_source():
    source = getsource(controls)
    dialog = getsource(multi)
    assert "from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS" not in source + dialog
    assert "from ae_engine.receiving_shared_settings import setting_value" not in source
    assert "manufacturing_api.receiving_operator_switch_brand_choices()" in source
    assert "manufacturing_api.receiving_operator_switch_brand_choices()" in dialog
    assert "manufacturing_api.project_receiving_shared_setting_group(" in source
    assert "if setting_value(current, i, kind) == value" not in source


def test_real_native_tk_settings_panel_uses_engine_projection_to_highlight(monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    row = _physical_row()
    before = deepcopy(row)
    seen = []
    original = api.project_receiving_shared_setting_group

    def tracked(*args, **kwargs):
        result = original(*args, **kwargs)
        seen.append((args[1], args[2], result[1]))
        return result

    monkeypatch.setattr(api, "project_receiving_shared_setting_group", tracked)
    root = tk.Tk()
    root.withdraw()
    try:
        ports = {
            "row": lambda: row,
            "select": lambda _index: None,
        }
        panel = controls._build_receiving_settings_editor(
            root, tk=tk, ttk=ttk, ports=ports,
        )
        panel._receiving_kind_var.set("內門層數")
        panel._receiving_refresh()
        assert panel._receiving_matches == (0, 2)
        panel._receiving_select_bay(1)
        # Switching Bays retains the staged value until a fresh load is asked.
        assert panel._receiving_matches == (0, 2)
        assert seen[-1] == (1, "inner_door_layers", (0, 2))
        panel._receiving_refresh()
        assert panel._receiving_matches == (1,)
        assert row == before  # selecting and highlighting never Applies
    finally:
        root.destroy()
