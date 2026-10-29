# -*- coding: utf-8 -*-
"""Receiving BasePlate has no manual shrink controls; geometry stays intact."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from phase6_settings_panel_owned_render import Phase6SettingsPanelOwnedRenderMixin
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER


class _Panel(Phase6SettingsPanelOwnedRenderMixin):
    def __init__(self):
        self.commits = []
        self._receiving_base_plate_commit = self.commits.append


def _all_descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _all_descendants(child)


@pytest.mark.parametrize("source_derived", [False, True])
def test_receiving_base_displays_no_manual_shrink_widget_or_label(source_derived):
    root = tk.Tk()
    root.withdraw()
    try:
        panel = _Panel()
        physical = {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 280.0, "shrink_top": 20.0,
            "shrink_bottom": 20.0, "shrink_left": 85.0,
            "shrink_right": 85.0, "bend": 20.0,
        }
        state = {}
        panel._render_owned_receiving_base_plate(
            root, 0, {
                "values": physical, "configured": True,
                "source_derived": source_derived,
            }, state,
        )
        root.update_idletasks()
        visible = tuple(_all_descendants(root))
        labels = tuple(
            str(widget.cget("text"))
            for widget in visible
            if isinstance(widget, ttk.Label)
        )
        assert not any("縮" in label for label in labels)
        # Only physical height and bend are displayed as numeric inputs;
        # the shrink values still exist solely for the legacy physical source.
        entries = tuple(
            widget for widget in visible if isinstance(widget, ttk.Entry)
        )
        assert len(entries) == 2
        vars_by_key = state["receiving_base_plate_vars"]
        assert set(vars_by_key) == set(physical)
        assert [float(vars_by_key[key].get()) for key in (
            "shrink_top", "shrink_bottom", "shrink_left", "shrink_right",
        )] == [20, 20, 85, 85]
        apply = state["receiving_base_plate_apply_button"]
        if source_derived:
            assert "disabled" in apply.state()
            assert panel.commits == []
        else:
            apply.invoke()
            assert panel.commits == [physical]
    finally:
        root.destroy()
