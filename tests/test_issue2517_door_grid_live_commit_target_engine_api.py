"""#2517: Door grid W/H commits must resolve real target indices in Engine.

A stale Tk callback must not touch a different physical Door column/row via
Python's bool or negative-index aliases; committed fallback mm are Engine data.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.door_layout_numeric_transitions import (
    validate_operator_door_grid_edit_index as engine_index,
)
from gui_modules.application import door_layout_host_adapter as gui


class Field:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def get(self):
        return self.raw

    def set(self, value):
        self.calls.append(value)
        self.raw = value


def _host():
    events = []
    row = {
        "width_var": Field("420.625"), "width_committed": "410.125",
        "width_auto": False,
        "height_vars": [Field("301.25"), Field("298.75")],
        "height_committed": ["300.125", "299.875"],
        "height_auto": [False, False],
    }
    host = SimpleNamespace(
        door_layout_columns=[row],
        w_var=Field("700.5"),
        h_var=Field("700.5"),
        _parse_layout_value=lambda var, label:
            api.normalize_operator_door_grid_dimension(
                var.get(),
                field=("column_width" if "寬度" in label else
                       "row_height" if "高度" in label else
                       "w" if label == "W" else "h"),
            ),
        _door_layout_controller_columns=lambda: (
            api.DoorLayoutColumnState(
                width=row["width_committed"],
                width_auto=row["width_auto"],
                heights=tuple(row["height_committed"]),
                height_auto=tuple(row["height_auto"]),
            ),
        ),
        _reject_door_layout_dimension=lambda var, previous, msg:
            events.append(("reject", previous, msg)),
        _recompute_door_layout_remainders=lambda **kw:
            events.append(("recompute", kw)),
        _on_door_layout_value_changed=lambda **kw:
            events.append(("update", kw)),
    )
    return host, row, events


def _source(row):
    return (
        row["width_committed"], row["width_var"].get(), row["width_auto"],
        tuple(v.get() for v in row["height_vars"]),
        tuple(row["height_committed"]), tuple(row["height_auto"]),
    )


def test_public_index_is_exact_original_engine_owner_not_gui_cast():
    assert api.validate_operator_door_grid_edit_index is engine_index
    assert ae_engine.validate_operator_door_grid_edit_index is engine_index
    assert engine_index(0, count=1, axis="column") == 0
    assert engine_index(1, count=2, axis="row") == 1


@pytest.mark.parametrize("bad", [
    True, False, -1, 1, 99, 0.0, 0.5, "0", "1", None,
])
@pytest.mark.parametrize("axis,count", [("column", 1), ("row", 1)])
def test_engine_rejects_invalid_raw_physical_edit_index(bad, axis, count):
    with pytest.raises(ValueError):
        engine_index(bad, count=count, axis=axis)


@pytest.mark.parametrize("bad", [True, False, None, 0.0, -1, 1, "1", float("nan")])
def test_engine_rejects_bad_edit_count_before_physical_edit(bad):
    with pytest.raises(ValueError):
        engine_index(0, count=bad, axis="column")


def test_unknown_edit_axis_is_rejected():
    with pytest.raises(ValueError):
        engine_index(0, count=1, axis="anything")


@pytest.mark.parametrize("bad", [True, False, -1, 1, 0.0, 0.5, "0", None])
def test_stale_width_callback_does_not_read_or_restore_wrong_column(bad):
    host, row, events = _host()
    before = _source(row)
    with pytest.raises(ValueError):
        gui.commit_door_layout_width(host, bad)
    assert _source(row) == before
    assert row["width_var"].calls == []
    assert events == []


@pytest.mark.parametrize(("column", "row_index"), [
    (True, 0), (False, 0), (-1, 0), (1, 0),
    (0.0, 0), (0, True), (0, False), (0, -1),
    (0, 2), (0, 0.0), (0, 1.5), (0, "1"),
])
def test_stale_height_callback_does_not_mutate_any_physical_row(column, row_index):
    host, source, events = _host()
    before = _source(source)
    with pytest.raises(ValueError):
        gui.commit_door_layout_height(host, column, row_index)
    assert _source(source) == before
    assert all(var.calls == [] for var in source["height_vars"])
    assert events == []


@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "NaN", float("nan"), float("inf"),
])
def test_invalid_committed_width_cannot_become_rollback_mm(bad):
    host, row, events = _host()
    row["width_committed"] = bad
    prior = _source(row)
    with pytest.raises(ValueError):
        gui.commit_door_layout_width(host, 0)
    assert _source(row) == prior
    assert events == []


@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "NaN", float("nan"), float("inf"),
])
def test_invalid_committed_height_cannot_become_rollback_mm(bad):
    host, row, events = _host()
    row["height_committed"][1] = bad
    before = _source(row)
    with pytest.raises(ValueError):
        gui.commit_door_layout_height(host, 0, 1)
    assert _source(row) == before
    assert events == []


def test_legal_fractional_width_and_height_are_committed_unchanged():
    host, row, events = _host()
    assert gui.commit_door_layout_width(host, 0) is True
    assert row["width_committed"] == 420.625
    assert events == [
        ("recompute", {"rebuild": True}),
        ("update", {"recompute": False}),
    ]
    events.clear()
    assert gui.commit_door_layout_height(host, 0, 0) is True
    assert row["height_committed"] == [301.25, "299.875"]
    assert events == [
        ("recompute", {"rebuild": True}),
        ("update", {"recompute": False}),
    ]
    dimensions = {
        "width": row["width_committed"],
        "heights": row["height_committed"],
    }
    assert json.loads(json.dumps(dimensions)) == dimensions


def test_real_gui_edit_ports_validate_indices_before_any_index_lookup():
    width = inspect.getsource(gui.commit_door_layout_width)
    height = inspect.getsource(gui.commit_door_layout_height)
    assert width.index("manufacturing_api.validate_operator_door_grid_edit_index(") < width.index("self.door_layout_columns[column_index]")
    assert height.index("manufacturing_api.validate_operator_door_grid_edit_index(") < height.index("self.door_layout_columns[column_index]")
    assert "previous = float(" not in width
    assert "previous = float(" not in height
