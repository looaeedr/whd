# -*- coding: utf-8 -*-
"""#2517 Door grid auto/fixed sources must not be inferred by GUI truthiness."""
from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.door_layout_numeric_transitions import DoorLayoutColumnState
from gui_modules.application import door_layout_host_adapter as gui


class Field:
    def __init__(self, value):
        self.value = value
        self.writes = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes.append(value)


def _serialized_fixed_column(*, width_auto="false", height_auto=("false", "true")):
    return DoorLayoutColumnState(400, width_auto, (450, 550), height_auto)


def test_public_engine_decodes_serialized_false_and_recomputes_same_physical_cells():
    original = _serialized_fixed_column()
    actual = api.recompute_door_layout(
        (original,), total_width=1000, total_height=1000, selected_key="0:0",
    )
    assert original == _serialized_fixed_column()
    assert [(c.width, c.width_auto, c.heights, c.height_auto) for c in actual.columns] == [
        (400.0, False, (450.0, 550.0), (False, True)),
        (600.0, True, (1000.0,), (True,)),
    ]
    layout = json.loads(json.dumps([(c.width, list(c.heights)) for c in actual.columns]))
    cells = api.door_layout_cells(layout, total_width=1000, total_height=1000)
    assert [(api.door_layout_part_key(c), c.start_width, c.start_height) for c in cells] == [
        ("door_c1_r1", 400.0, 450.0),
        ("door_c1_r2", 400.0, 550.0),
        ("door_c2_r1", 600.0, 1000.0),
    ]


def test_width_and_height_edit_guards_use_actual_fixed_flags_not_gui_truthiness():
    width_columns = (
        DoorLayoutColumnState(400, "false", (1000,), ("false",)),
        DoorLayoutColumnState(600, "false", (1000,), ("false",)),
    )
    width_check = api.validate_door_layout_width_commit(
        width_columns, 0, 1000, 401,
    )
    assert not width_check.valid and width_check.maximum == 400
    height_columns = (
        DoorLayoutColumnState(1000, "false", (450, 550), ("false", "false")),
    )
    height_check = api.validate_door_layout_height_commit(
        height_columns, 0, 0, 1000, 500,
    )
    assert not height_check.valid and height_check.maximum == 450


@pytest.mark.parametrize("bad", ["maybe", None, [], {}, 2, -1, 0.5, float("nan")])
@pytest.mark.parametrize("field", ["width", "height"])
def test_bad_auto_flag_is_atomic_for_all_three_public_engine_transitions(bad, field):
    columns = (
        _serialized_fixed_column(width_auto=bad)
        if field == "width" else
        _serialized_fixed_column(height_auto=("false", bad))
    ,)
    before = repr(columns)
    with pytest.raises(ValueError):
        api.recompute_door_layout(columns, total_width=1000, total_height=1000, selected_key="0:0")
    with pytest.raises(ValueError):
        api.validate_door_layout_width_commit(columns, 0, 1000, 400)
    with pytest.raises(ValueError):
        api.validate_door_layout_height_commit(columns, 0, 0, 1000, 450)
    assert repr(columns) == before


def test_height_auto_length_must_match_actual_physical_rows():
    rows = (DoorLayoutColumnState(400, False, (450, 550), (False,)),)
    with pytest.raises(ValueError, match="DOOR_LAYOUT_AUTO"):
        api.recompute_door_layout(rows, total_width=1000, total_height=1000, selected_key="0:0")


def _gui_host(width_auto, height_auto):
    initial = {
        "width_var": Field("400"),
        "width_auto": width_auto,
        "width_committed": 400,
        "height_vars": [Field("450"), Field("550")],
        "height_auto": list(height_auto),
        "height_committed": [450, 550],
    }
    host = SimpleNamespace(
        door_layout_columns=[initial],
        w_var=Field("1000"),
        h_var=Field("1000"),
        door_layout_selected_var=Field("0:0"),
    )
    host._parse_layout_value = lambda field, label: api.normalize_operator_door_grid_dimension(
        field.get(), field="column_width" if "寬度" in label else "row_height",
    )
    host._door_layout_controller_columns = lambda: gui._door_layout_controller_columns(host)
    host._new_door_layout_column = lambda width, heights, **flags: {
        "width": width, "heights": list(heights), **flags,
    }
    return host


def test_gui_forwards_original_flags_and_consumes_same_engine_result():
    host = _gui_host("false", ("false", "true"))
    raw = gui._door_layout_controller_columns(host)
    assert raw[0].width_auto == "false"
    assert raw[0].height_auto == ("false", "true")
    gui._recompute_door_layout_remainders(host, rebuild=False)
    assert [(c["width"], c["width_auto"]) for c in host.door_layout_columns] == [
        (400, False), (600, True),
    ]


def test_gui_rejects_invalid_flag_without_selection_or_layout_commit():
    host = _gui_host("maybe", ("false", "true"))
    before = host.door_layout_columns
    with pytest.raises(ValueError):
        gui._recompute_door_layout_remainders(host, rebuild=False)
    assert host.door_layout_columns is before
    assert host.door_layout_selected_var.writes == []


def test_gui_new_row_flag_projection_uses_existing_public_engine_boolean_api(monkeypatch):
    monkeypatch.setattr(gui.tk, "StringVar", lambda *, value: Field(value))
    host = SimpleNamespace(_door_layout_number_text=gui._door_layout_number_text)
    row = gui._new_door_layout_column(
        host, 400, [450], width_auto="false", height_auto=["false"],
    )
    assert row["width_auto"] is False and row["height_auto"] == [False]
    with pytest.raises(ValueError):
        gui._new_door_layout_column(
            host, 400, [450], width_auto="false", height_auto=["invalid"],
        )
