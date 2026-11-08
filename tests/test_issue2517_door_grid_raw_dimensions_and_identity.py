# -*- coding: utf-8 -*-
"""#2517: actual Door grid selection and raw dimensions belong to public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges, DoorLayoutCell, door_layout_part_key,
)
from ae_engine.door_layout_numeric_transitions import (
    normalize_operator_door_grid_dimension, resolve_operator_door_layout_cell,
)
from gui_modules.application import door_layout_host_adapter as gui
from gui_modules.parts.panels import door as panel


class Field:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def get(self):
        return self.value

    def set(self, value):
        self.calls.append(value)
        self.value = value


def _cells():
    return (
        DoorLayoutCell(0, 0, 400.0, 450.0, DoorFrameEdges()),
        DoorLayoutCell(0, 1, 400.0, 550.0, DoorFrameEdges()),
        DoorLayoutCell(1, 0, 600.0, 1000.0, DoorFrameEdges()),
    )


def _host(mode="corner_data"):
    selected = Field("0:0")
    designer = SimpleNamespace(_phase6_3d_display_mode=mode)
    return SimpleNamespace(
        door_layout_selected_var=selected,
        get_door_layout_cells=lambda: _cells(),
        _door_layout_cell_key=lambda c: f"{c.column_index}:{c.row_index}",
        canvas_door=None,
        fold_designer_app=designer,
    ), selected, designer


def test_both_public_engine_door_ports_are_original_authorities():
    assert api.normalize_operator_door_grid_dimension is normalize_operator_door_grid_dimension
    assert api.resolve_operator_door_layout_cell is resolve_operator_door_layout_cell
    assert ae_engine.normalize_operator_door_grid_dimension is normalize_operator_door_grid_dimension
    assert ae_engine.resolve_operator_door_layout_cell is resolve_operator_door_layout_cell
    assert api.door_layout_part_key is door_layout_part_key


@pytest.mark.parametrize(("field", "raw"), [
    ("w", "800.125"), ("h", "1000.5"),
    ("column_width", "300.625"), ("row_height", "450.25"),
])
def test_engine_and_gui_share_fractional_positive_door_dimensions(field, raw):
    label = {"w": "W", "h": "H", "column_width": "欄 1 寬度",
             "row_height": "欄 1 第 1 層高度"}[field]
    value = Field(raw)
    result = panel._parse_layout_value(value, label)
    assert result == api.normalize_operator_door_grid_dimension(raw, field=field)
    assert json.loads(json.dumps({"value": result}))["value"] == result
    assert value.get() == raw


@pytest.mark.parametrize("bad", [True, False, None, -1, 0, float("nan"),
                                  float("inf"), "bad", "nan", "inf"])
def test_gui_and_engine_reject_bad_physical_door_dimensions(bad):
    value = Field(bad)
    with pytest.raises(ValueError):
        panel._parse_layout_value(value, "欄 2 寬度")
    with pytest.raises(ValueError):
        api.normalize_operator_door_grid_dimension(bad, field="column_width")
    assert value.get() is bad


def test_door_editor_uses_engine_numeric_rules_not_local_finite_formulas():
    source = inspect.getsource(panel._parse_layout_value)
    assert "manufacturing_api.normalize_operator_door_grid_dimension(" in source
    assert "float(" not in source and "isfinite(" not in source
    assert "int(" not in source


@pytest.mark.parametrize(("c", "r", "key"), [
    (0, 0, "door_c1_r1"), (0, 1, "door_c1_r2"), (1, 0, "door_c2_r1"),
])
def test_actual_existing_physical_door_cell_is_same_for_export_and_preview(c, r, key):
    actual = api.resolve_operator_door_layout_cell(_cells(), c, r)
    assert api.door_layout_part_key(actual) == key
    assert door_layout_part_key(actual) + ".dxf" == key + ".dxf"
    assert actual in _cells()


@pytest.mark.parametrize(("c", "r"), [
    (True, 0), (False, 0), (0.0, 0), (0.5, 0),
    (-1, 0), (0, -1), (2, 0), (0, 3), ("0", 0), (0, "1"),
])
def test_engine_and_gui_reject_stale_or_noninteger_cell_before_selection(c, r):
    host, selected, _designer = _host()
    prior = selected.get()
    with pytest.raises(ValueError, match="DOOR_LAYOUT_CELL"):
        api.resolve_operator_door_layout_cell(_cells(), c, r)
    with pytest.raises(ValueError, match="DOOR_LAYOUT_CELL"):
        gui.select_door_layout_cell(host, c, r)
    assert selected.get() == prior
    assert selected.calls == []


@pytest.mark.parametrize(("c", "r"), [(-1, 0), (0, -1), (True, 0), (0, False), (0.5, 0)])
def test_direct_engine_door_part_key_fails_closed_on_invalid_physical_identity(c, r):
    cell = DoorLayoutCell(c, r, 100, 200, DoorFrameEdges())
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PHYSICAL"):
        api.door_layout_part_key(cell)


def test_gui_corner_data_selection_delegates_actual_engine_door_id(monkeypatch):
    import fold_designer_bridge as bridge
    host, selected, designer = _host()
    calls = []
    original = api.door_layout_part_key
    monkeypatch.setattr(api, "door_layout_part_key",
                        lambda cell: (calls.append(("engine", cell)), original(cell))[1])
    monkeypatch.setattr(bridge, "_phase6_select_corner_data_part",
                        lambda receiver, key, **kw: calls.append((receiver, key, kw)))
    gui.select_door_layout_cell(host, 1, 0)
    assert selected.get() == "1:0"
    assert calls[0] == ("engine", _cells()[2])
    assert calls[1] == (designer, "door_c2_r1", {"refresh_view": False})
    assert selected.calls == ["1:0"]
    assert "door_c{int(" not in inspect.getsource(gui.select_door_layout_cell)
