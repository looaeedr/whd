# -*- coding: utf-8 -*-
"""#2517: Receiving Joint dimension editability is one public Engine policy."""
from copy import deepcopy
from inspect import getsource

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.application import receiving_set_bay_controls as controls


def _layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )


def test_actual_saved_set_row_equals_original_layout_policy_and_is_pure():
    layout = _layout()
    old = deepcopy(layout)
    row = layout["sets"][0]
    for i in range(2):
        expected = api.receiving_joint_alignment_editability(
            layout, set_index=0, joint_index=i,
        )
        assert expected == {"depth_alignment": False, "height_alignment": False}
        assert api.project_receiving_joint_alignment_editability(row, i) == expected
    assert layout == old
    assert ae_engine.project_receiving_joint_alignment_editability is (
        api.project_receiving_joint_alignment_editability
    )

    uneven = api.update_receiving_bay(
        layout, set_index=0, bay_index=1, depth=500, height=1800,
    )
    for i in range(2):
        expected = api.receiving_joint_alignment_editability(
            uneven, set_index=0, joint_index=i,
        )
        assert api.project_receiving_joint_alignment_editability(
            uneven["sets"][0], i,
        ) == expected == {"depth_alignment": True, "height_alignment": True}
    assert layout == old


def test_invalid_or_stale_physical_joint_source_never_yields_editability():
    source = _layout()["sets"][0]
    before = deepcopy(source)
    for invalid_index in (True, -1, 2, 0.5, "0", None):
        with pytest.raises(IndexError):
            api.project_receiving_joint_alignment_editability(source, invalid_index)
    for invalid in (
        None, [], {}, {"bays": [], "joints": []},
        {"bays": source["bays"], "joints": []},
    ):
        with pytest.raises(ValueError):
            api.project_receiving_joint_alignment_editability(invalid, 0)
    corrupt = deepcopy(source)
    corrupt["bays"][1]["depth"] = True
    with pytest.raises(ValueError):
        api.project_receiving_joint_alignment_editability(corrupt, 0)
    assert source == before


def test_gui_has_no_second_dimension_comparison_owner():
    source = getsource(controls._build_receiving_settings_editor)
    assert source.count("manufacturing_api.project_receiving_joint_alignment_editability(") == 2
    assert 'left["depth"] != right["depth"]' not in source
    assert 'left["height"] != right["height"]' not in source


def test_native_tk_editability_refresh_tracks_engine_not_gui_dimension_math(monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    layout = _layout()
    current = {"row": layout["sets"][0]}
    seen = []
    original = api.project_receiving_joint_alignment_editability

    def project(row, index):
        seen.append((index, row["bays"][1]["depth"]))
        return original(row, index)

    monkeypatch.setattr(api, "project_receiving_joint_alignment_editability", project)

    root = tk.Tk()
    root.withdraw()
    try:
        panel = controls._build_receiving_settings_editor(
            root, tk=tk, ttk=ttk,
            ports={"row": lambda: current["row"], "select": lambda index: None},
        )

        def widgets(node):
            for child in node.winfo_children():
                yield child
                yield from widgets(child)

        def joint_states(labels):
            return tuple(
                str(widget.cget("state"))
                for widget in widgets(panel)
                if isinstance(widget, ttk.Combobox)
                and tuple(widget.cget("values")) == labels
            )

        assert joint_states(("前齊", "後齊")) == ("disabled", "disabled")
        assert joint_states(("上齊", "下齊")) == ("disabled", "disabled")

        next_layout = api.update_receiving_bay(
            layout, set_index=0, bay_index=1, depth=500,
        )
        current["row"] = next_layout["sets"][0]
        panel._receiving_refresh()
        assert joint_states(("前齊", "後齊")) == ("readonly", "readonly")
        assert joint_states(("上齊", "下齊")) == ("disabled", "disabled")
        assert seen and set(x[0] for x in seen) == {0, 1}
        assert layout == _layout()  # read-only Tk projection
    finally:
        root.destroy()
