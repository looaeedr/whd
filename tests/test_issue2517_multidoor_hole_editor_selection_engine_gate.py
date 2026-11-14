"""#2517: opening a physical Door cell Hole Editor must use Engine identity."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, DoorLayoutCell
import gui


class Field:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.calls.append(value)


def _cells():
    return (
        DoorLayoutCell(0, 0, 400.0, 450.0, DoorFrameEdges()),
        DoorLayoutCell(0, 1, 400.0, 550.0, DoorFrameEdges()),
        DoorLayoutCell(1, 0, 600.0, 1000.0, DoorFrameEdges()),
    )


def _host():
    selection = Field("0:1")
    calls = []
    host = SimpleNamespace(
        last_unified_hole_editor=None,
        door_layout_selected_var=selection,
        get_door_layout_cells=lambda: _cells(),
        get_selected_door_layout_cell=lambda: pytest.fail(
            "must not use GUI first-cell fallback for physical Hole Editor"
        ),
        _door_layout_cell_key=lambda cell: f"{cell.column_index}:{cell.row_index}",
        get_float_values=lambda: (
            calls.append("values"),
            dict(w=1000, h=1000, t=2, fw=25,
                 door_gap_w=2, door_gap_h=2),
        )[1],
        _door_layout_cell_result=lambda cell, val: (calls.append("cell"), cell)[1],
        _door_layout_part_spec=lambda cell, val: (calls.append("spec"), object())[1],
        _door_layout_baseline_scene=lambda cell, val: (None, "baseline"),
        door_layout_features={"0:0": [], "0:1": [], "1:0": []},
        door_layout_indicator_states={"0:0": {"mode": "none"}},
        door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        _door_layout_indicator_state_for_key=lambda key: {"mode": "none"},
        _open_unified_hole_editor=lambda *args, **kwargs: calls.append(
            ("open", args, kwargs)
        ),
        draw_door_layout_overview=lambda: None,
        fold_designer_app=None,
    )
    return host, selection, calls


@pytest.mark.parametrize("column,row", [
    (True, 0), (False, 0), (0, True), (0, False),
    (0.0, 0), (0.5, 0), (0, 1.9), (-1, 0), (0, -1),
    (2, 0), (0, 3), ("1", 0), (0, "1"), (None, 0),
])
def test_invalid_raw_cell_selection_rejects_without_opening_or_mutating(
    monkeypatch, column, row,
):
    host, selected, events = _host()
    errors = []
    monkeypatch.setattr(
        gui.messagebox, "showerror",
        lambda title, msg: errors.append((title, str(msg))),
    )
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, column, row)
    assert selected.get() == "0:1"
    assert selected.calls == []
    assert events == []
    assert len(errors) == 1
    assert "DOOR_LAYOUT_CELL" in errors[0][1]


@pytest.mark.parametrize("column,row,key,physical", [
    (0, 0, "0:0", "door_c1_r1"),
    (0, 1, "0:1", "door_c1_r2"),
    (1, 0, "1:0", "door_c2_r1"),
])
def test_editor_opens_same_real_engine_cell_as_saved_dxf_part(
    monkeypatch, column, row, key, physical,
):
    host, selected, events = _host()
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: errors.append(a))
    monkeypatch.setattr(
        api, "project_operator_hole_editor_door_cell",
        lambda result, spec, **kw: SimpleNamespace(
            surface=object(), width=100, height=200, reference_guide=None,
            door_indicator_context=None, door_frame_edges=DoorFrameEdges(),
            baseline_scene=None, baseline_status="baseline",
        ),
    )
    monkeypatch.setattr(
        gui._door_layout_host_adapter, "_receiving_live_door_layout_source",
        lambda _: None,
    )
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, column, row)
    assert selected.get() == key
    assert selected.calls == [key]
    assert errors == []
    opened = next(event for event in events if isinstance(event, tuple)
                  and event[0] == "open")
    assert opened[1][0] == "door"
    actual = api.resolve_operator_door_layout_cell(_cells(), column, row)
    assert api.door_layout_part_key(actual) == physical


def test_invalid_geometry_does_not_change_previous_selected_door(monkeypatch):
    host, selected, events = _host()
    host._door_layout_part_spec = lambda *a: (_ for _ in ()).throw(
        ValueError("invalid physical DoorPartSpec")
    )
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: errors.append(a))
    monkeypatch.setattr(
        gui._door_layout_host_adapter, "_receiving_live_door_layout_source",
        lambda _: None,
    )
    gui.Phase6ApplicationHost.open_door_layout_cell_editor(host, 1, 0)
    assert selected.get() == "0:1"
    assert selected.calls == []
    assert "open" not in events
    assert len(errors) == 1


def test_editor_uses_existing_engine_cell_resolver_and_no_int_cast():
    source = inspect.getsource(
        gui.Phase6ApplicationHost.open_door_layout_cell_editor
    )
    assert "manufacturing_api.resolve_operator_door_layout_cell(" in source
    assert "int(column_index)" not in source
    assert "int(row_index)" not in source
    assert "get_selected_door_layout_cell()" not in source
