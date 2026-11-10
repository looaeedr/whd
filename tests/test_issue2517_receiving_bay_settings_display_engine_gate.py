"""#2517: Receiving per-Bay editor displays only validated Engine W/H/D."""
from __future__ import annotations

from copy import deepcopy
import inspect
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application import receiving_set_bay_controls as controls


def _row():
    return new_receiving_layout(
        width=820.25, height=1600.5, depth=350.75,
    )["sets"][0]


def _entries(root):
    pending = [root]
    result = []
    while pending:
        widget = pending.pop(0)
        if isinstance(widget, ttk.Entry):
            result.append(widget)
        pending.extend(widget.winfo_children())
    return result


def test_readback_preserves_engine_decimal_source_without_gui_manufacturing_fallback():
    row = _row()
    original = deepcopy(row)
    values = controls._receiving_bay_dimension_labels(row, 0)
    physical = manufacturing_api.normalize_operator_live_box_dimensions({
        "w": row["bays"][0]["width"],
        "h": row["bays"][0]["height"],
        "d": row["bays"][0]["depth"],
    })
    assert physical == {"w": 820.25, "h": 1600.5, "d": 350.75}
    assert values == {
        "width": "820.25", "height": "1600.5", "depth": "350.75",
    }
    assert row == original
    source = inspect.getsource(controls._receiving_bay_dimension_labels)
    assert "manufacturing_api.normalize_operator_live_box_dimensions(" in source
    assert 'float(bay[' not in source


@pytest.mark.parametrize("field,invalid", [
    ("width", True), ("width", None), ("width", "nan"),
    ("height", False), ("height", float("inf")),
    ("depth", 0), ("depth", -5), ("depth", "not a number"),
])
def test_invalid_saved_bay_source_is_not_displayed_as_physical_mm(field, invalid):
    row = _row()
    row["bays"][0][field] = invalid
    before = deepcopy(row)
    with pytest.raises(ValueError, match="包外尺寸"):
        controls._receiving_bay_dimension_labels(row, 0)
    assert row == before


@pytest.mark.parametrize("field,invalid", [
    ("width", True), ("height", float("nan")), ("depth", -1),
])
def test_actual_tk_refresh_is_atomic_for_invalid_bay_source(field, invalid):
    root = tk.Tk()
    root.withdraw()
    try:
        row = _row()
        panel = controls._build_receiving_settings_editor(
            root, tk=tk, ttk=ttk, ports={"row": lambda: row},
        )
        entries = _entries(panel)
        assert len(entries) == 3
        assert tuple(entry.get() for entry in entries) == (
            "820.25", "1600.5", "350.75",
        )
        before = tuple(entry.get() for entry in entries)
        row["bays"][0][field] = invalid
        source_before = deepcopy(row)
        with pytest.raises(ValueError, match="包外尺寸"):
            panel._receiving_refresh()
        assert tuple(entry.get() for entry in entries) == before
        assert row == source_before
        # No stale failed-source value may be republished by a later valid read.
        row["bays"][0][field] = {
            "width": 820.25, "height": 1600.5, "depth": 350.75,
        }[field]
        panel._receiving_refresh()
        assert tuple(entry.get() for entry in entries) == before
    finally:
        root.destroy()
