# -*- coding: utf-8 -*-
"""Regression: saved Set/Bay two-NFB source -> candidate -> explicit real Apply."""
from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine.receiving_legacy_nfb_editor_bootstrap import (
    recover_submitted_nfb_models_for_editor,
)
from ae_engine.receiving_inner_door_candidates import (
    ROLE, create_inner_candidate, inner_versions,
)
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def _legacy_source():
    return {
        "nfb_config_submitted": True,
        "nfb_config": {
            "layer_count": 1,
            "holes": [
                {"slot_index": 0, "model_filename": "nfbv5:士林:2P400",
                 "source_brand": "士林"},
                {"slot_index": 1, "model_filename": "nfbv5:士林:3P125SN",
                 "source_brand": "士林"},
            ],
        },
    }


def test_saved_two_nfb_rows_restore_missing_legacy_editor_alias_without_mutation():
    physical = _legacy_source()
    original = deepcopy(physical)
    alias = {"layers": 1, "models": ["nfbv5:士林:2P400", ""],
             "layer_heights_mm": [550, 830]}
    restored = recover_submitted_nfb_models_for_editor(alias, physical)
    assert restored["models"] == [
        ["nfbv5:士林:2P400", "nfbv5:士林:3P125SN"], ""
    ]
    assert restored["_restored_saved_nfb_models"] is True
    assert physical == original and alias["models"][0] == "nfbv5:士林:2P400"

    complete = {**alias, "models": deepcopy(restored["models"])}
    assert recover_submitted_nfb_models_for_editor(complete, physical) == complete
    stale = deepcopy(physical)
    stale["nfb_config"]["holes"][1]["slot_index"] = 0
    assert recover_submitted_nfb_models_for_editor(alias, stale) == alias
    unsubmitted = {**physical, "nfb_config_submitted": False}
    assert recover_submitted_nfb_models_for_editor(alias, unsubmitted) == alias


def test_just_saved_inner_candidate_is_selected_for_real_apply_not_live_label():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No Tk display: {exc}")
    root.geometry("420x300+20+20")
    events = []
    library = {"value": None}
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    selected = {"bay": 0}
    saved = {"id": None}

    def editor(version_id, callback):
        assert version_id is None
        lib, vid = create_inner_candidate(
            library["value"],
            {"layers": 1,
             "models": [["nfbv5:士林:2P400", "nfbv5:士林:3P125SN"], ""],
             "layer_heights_mm": [550, 830],
             "features": {}},
        )
        library["value"], saved["id"] = lib, vid
        callback(vid)

    def ports():
        return {
            "versions": lambda role: inner_versions(library["value"]) if role == ROLE else (),
            "apply": lambda role, vid, si, bays:
                events.append(("physical_apply", role, vid, si, tuple(bays))),
            "apply_live": lambda role, si, bays:
                events.append(("label_only", role, si, tuple(bays))),
        }

    def setting_ports(si):
        return {
            "row": lambda: layout["sets"][si],
            "select": lambda bi: selected.__setitem__("bay", bi),
        }

    def find_button(host, text):
        found = [
            widget for row in host.winfo_children()
            for widget in row.winfo_children()
            if isinstance(widget, ttk.Button) and widget.cget("text") == text
        ]
        assert len(found) == 1, (text, len(found))
        return found[0]

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda mode: True,
            resize_connections=lambda *args: False,
            get_candidate_ports=lambda: {"versions": lambda role: ()},
            get_inner_candidate_ports=ports,
            get_settings_ports=setting_ports,
            edit_multi_inner_door=editor,
            select_bay=lambda si, bi: selected.__setitem__("bay", bi),
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        find_button(win._receiving_multi_settings_host, "編輯").invoke()
        root.update()
        assert saved["id"] is not None
        assert win._receiving_multi_candidate_selected[ROLE] == saved["id"]
        assert win._receiving_multi_candidate_combos[ROLE].get() != "即時"
        assert win._receiving_multi_applied["selected_bays"] == (0,)
        assert not events, "Saving candidate must not apply physical NFB yet"
        find_button(win._receiving_multi_settings_host, "套用").invoke()
        root.update()
        assert events == [
            ("physical_apply", ROLE, saved["id"], 0, (0,))
        ], "Apply must transfer two-hole candidate; label-only is not assembly"
    finally:
        root.destroy()
