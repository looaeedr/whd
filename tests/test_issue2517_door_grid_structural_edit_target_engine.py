"""#2517: structural Door-grid actions qualify physical targets before GUI indexing.

Delete/insert callbacks can outlive their original controls. A bool, negative
index or stale index must never target another physical Door cell.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import door_layout_host_adapter as gui


class _Selection:
    def __init__(self):
        self.value = "0:0"
        self.changes = []

    def set(self, value):
        self.value = value
        self.changes.append(value)


def _host():
    events = []
    selection = _Selection()
    columns = [
        {"width_auto": False, "height_auto": [False, True],
         "height_vars": ["top", "auto"]},
        {"width_auto": True, "height_auto": [True],
         "height_vars": ["right"]},
    ]
    host = SimpleNamespace(
        door_layout_columns=columns,
        door_layout_selected_var=selection,
        _remap_door_layout_owned_data=lambda **kwargs:
            events.append(("remap", kwargs)),
        _recompute_door_layout_remainders=lambda **kwargs:
            events.append(("recompute", kwargs)),
        _on_door_layout_value_changed=lambda **kwargs:
            events.append(("update", kwargs)),
        commit_door_layout_height=lambda c, r: events.append(("commit", c, r)),
    )
    return host, events, selection


@pytest.mark.parametrize("invalid", [
    True, False, -1, 2, 0.0, 0.5, "0", None, float("nan"),
])
@pytest.mark.parametrize("action", [
    "remove_door_layout_column", "add_door_layout_height",
    "remove_door_layout_height",
])
def test_invalid_column_target_cannot_change_gui_or_physical_sources(
    invalid, action,
):
    host, events, selection = _host()
    original = deepcopy(host.door_layout_columns)
    with pytest.raises(ValueError):
        if action == "remove_door_layout_height":
            gui.remove_door_layout_height(host, invalid, 0)
        else:
            getattr(gui, action)(host, invalid)
    assert host.door_layout_columns == original
    assert selection.changes == []
    assert events == []


@pytest.mark.parametrize("invalid", [
    True, False, -1, 2, 0.0, 0.5, "0", None, float("nan"),
])
def test_invalid_row_target_cannot_remap_or_remove_another_door(invalid):
    host, events, selection = _host()
    original = deepcopy(host.door_layout_columns)
    with pytest.raises(ValueError):
        gui.remove_door_layout_height(host, 0, invalid)
    assert host.door_layout_columns == original
    assert selection.changes == []
    assert events == []


def test_legal_physical_column_delete_uses_original_engine_remap():
    host, events, selection = _host()
    assert manufacturing_api.validate_operator_door_grid_edit_index(
        0, count=2, axis="column",
    ) == 0
    gui.remove_door_layout_column(host, 0)
    assert len(host.door_layout_columns) == 1
    assert host.door_layout_columns[0]["height_vars"] == ["right"]
    assert events == [
        ("remap", {"operation": "delete_column", "column_index": 0}),
        ("recompute", {"rebuild": True}),
        ("update", {"recompute": False}),
    ]
    assert selection.changes == ["0:0"]


def test_legal_physical_row_delete_uses_original_engine_remap():
    host, events, selection = _host()
    gui.remove_door_layout_height(host, 0, 0)
    assert host.door_layout_columns[0]["height_vars"] == ["auto"]
    assert host.door_layout_columns[0]["height_auto"] == [True]
    assert events == [
        ("remap", {"operation": "delete_row", "column_index": 0, "row_index": 0}),
        ("recompute", {"rebuild": True}),
        ("update", {"recompute": False}),
    ]
    assert selection.changes == ["0:0"]


def test_legal_height_add_promotes_only_selected_columns_auto_row():
    host, events, selection = _host()
    gui.add_door_layout_height(host, 0)
    assert events == [("commit", 0, 1)]
    assert selection.changes == []
    assert host.door_layout_columns[1]["height_vars"] == ["right"]


def test_auto_row_or_column_cannot_be_deleted():
    host, events, selection = _host()
    original = deepcopy(host.door_layout_columns)
    gui.remove_door_layout_column(host, 1)
    gui.remove_door_layout_height(host, 0, 1)
    assert host.door_layout_columns == original
    assert events == []
    assert selection.changes == []
