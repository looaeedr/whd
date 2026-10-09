# -*- coding: utf-8 -*-
"""OPEN-04/05 Receiving switch tier UI-only regressions."""
from __future__ import annotations

from copy import deepcopy
import inspect
import os
from pathlib import Path

import pytest

from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application import receiving_set_bay_controls as controls
from gui_modules.application import fold_designer_composition_receiving as composition
from gui_modules.application.receiving_switch_tier_ui import (
    ReceivingSwitchTierUiModel,
    SWITCH_TIER_OUTPUT_NOTICE,
    switch_tier_nominal_text,
)

ROOT = Path(__file__).resolve().parents[1]


def test_switch_tier_is_unset_and_nominal_heights_have_one_ui_source():
    model = ReceivingSwitchTierUiModel()
    assert model.snapshot() == {"switch_tier": None, "positions": []}
    assert "尚未選擇" in switch_tier_nominal_text(model.switch_tier)
    model.set_switch_tier("一層")
    assert switch_tier_nominal_text(model.switch_tier) == "標稱高度：550 mm（不是計算結果）"
    assert model.snapshot()["positions"] == [
        {"position": "本層", "brand_override": None},
    ]
    model.set_switch_tier("兩層")
    assert switch_tier_nominal_text(model.switch_tier) == "標稱高度：290／790 mm（不是計算結果）"
    assert model.snapshot()["positions"] == [
        {"position": "上層", "brand_override": None},
        {"position": "下層", "brand_override": None},
    ]
    model.set_brand_override("上層", "三菱")
    assert model.snapshot()["positions"][0]["brand_override"] == "三菱"
    assert model.snapshot()["positions"][1]["brand_override"] is None
    model.set_switch_tier("一層")
    model.set_switch_tier("兩層")
    assert all(p["brand_override"] is None for p in model.snapshot()["positions"])
    with pytest.raises(ValueError):
        model.set_switch_tier("三層")


def test_tier_change_never_mutates_inner_door_layers_or_set_bay_counts():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    before = deepcopy(layout)
    model = ReceivingSwitchTierUiModel()
    model.set_switch_tier("兩層")
    model.set_brand_override("下層", "東元")
    model.set_switch_tier("一層")
    assert layout == before
    tier_impl = inspect.getsource(composition.set_receiving_switch_tier_ui)
    assert "refresh_receiving_set_bay_control" in tier_impl
    assert "submit_update_intent" not in tier_impl
    assert "manufacturing" not in tier_impl
    assert "inner_door_layers" not in tier_impl
    assert '["layers"]' not in tier_impl
    assert "receiving_switch_tier_ui_by_set" in inspect.getsource(
        composition.receiving_switch_tier_ui_model
    )
    assert '["switch_tier_state"]' in inspect.getsource(controls._build_receiving_settings_editor)
    assert "SWITCH_TIER_OUTPUT_NOTICE" in inspect.getsource(controls.build_receiving_set_bay_controls)
    assert SWITCH_TIER_OUTPUT_NOTICE


def test_header_and_settings_brands_and_tiers_share_source_contract():
    ports = inspect.getsource(composition.receiving_settings_ports)
    refresh = inspect.getsource(composition.refresh_receiving_set_bay_control)
    bridge = (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")
    assert 'adapter.set_brand(value)' in ports
    assert 'self.refresh_receiving_set_bay_control(namespace)' in ports
    assert '"switch_tier_state": tier_ui.snapshot' in ports
    assert '"switch_tier": switch_tier' in ports
    assert '"switch_tier_override": switch_tier_override' in ports
    assert 'controls.switch_brand_var.set(switch.brand)' in refresh
    assert 'controls.switch_tier_var.set(selected_tier or SWITCH_TIER_PLACEHOLDER)' in refresh
    assert 'on_switch_tier_selected=lambda tier:' in bridge
    assert 'set_receiving_switch_tier_ui(globals(), tier)' in bridge


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="real Tk widgets require Windows or DISPLAY/Xvfb",
)
def test_real_tk_tier_selection_syncs_header_settings_and_overrides_start_collapsed():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.geometry("900x650+0+0")
    model = ReceivingSwitchTierUiModel()
    set_row = {
        "switch_brand": "士林",
        "bays": [{"width": 800, "height": 1600, "depth": 350, "door_state": {}}],
        "joints": [],
    }
    sync_header = lambda: None
    def update_brand(value):
        set_row["switch_brand"] = value
        sync_header()
    def update_tier(value):
        model.set_switch_tier(value)
        sync_header()
    def update_override(position, value):
        model.set_brand_override(position, value)

    ports = {
        "row": lambda: set_row,
        "switch_tier_state": model.snapshot,
        "switch_tier": update_tier,
        "switch_tier_override": update_override,
        "brand": update_brand,
        "select": lambda index: None,
        "dimensions": lambda *args, **kwargs: None,
        "change": lambda *args, **kwargs: None,
        "share": lambda *args, **kwargs: None,
        "unlink": lambda *args, **kwargs: None,
        "alignment": lambda *args, **kwargs: None,
        "holes": lambda *args, **kwargs: None,
    }
    try:
        header = controls.build_receiving_set_bay_controls(
            root, tk=tk, ttk=ttk,
            on_switch_brand_selected=update_brand,
            on_switch_tier_selected=update_tier,
            on_add_layer=lambda: None,
            on_remove_layer=lambda: None,
        )
        def sync():
            header.switch_brand_var.set(set_row["switch_brand"])
            header.switch_tier_var.set(model.switch_tier or "請選擇")
            header.switch_tier_nominal_var.set(switch_tier_nominal_text(model.switch_tier))
        sync_header = sync
        settings = controls._build_receiving_settings_editor(root, tk=tk, ttk=ttk, ports=ports)
        root.update()
        assert header.switch_tier_var.get() == "請選擇"
        assert settings._receiving_switch_tier_var.get() == "請選擇"
        header.switch_tier_var.set("兩層")
        header.switch_tier_selector.event_generate("<<ComboboxSelected>>")
        root.update()
        settings._receiving_refresh()
        assert settings._receiving_switch_tier_var.get() == "兩層"
        assert "290／790" in header.switch_tier_nominal_var.get()
        settings._receiving_switch_tier_var.set("一層")
        settings._receiving_switch_tier_selector.event_generate("<<ComboboxSelected>>")
        root.update()
        assert header.switch_tier_var.get() == "一層"
        header.switch_brand_var.set("東元")
        header.switch_brand_selector.event_generate("<<ComboboxSelected>>")
        root.update()
        assert set_row["switch_brand"] == "東元"
        settings._receiving_switch_tier_var.set("兩層")
        settings._receiving_switch_tier_selector.event_generate("<<ComboboxSelected>>")
        root.update()
        assert settings._receiving_switch_tier_override_vars["上層"].get() == "沿用本套"
        assert model.snapshot()["positions"][0]["brand_override"] is None
    finally:
        root.destroy()
