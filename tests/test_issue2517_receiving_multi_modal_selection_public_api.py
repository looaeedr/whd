# -*- coding: utf-8 -*-
"""#2517: real Receiving modal Set/Bay GUI callbacks use public Engine identity."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    project_receiving_operator_set_bay_selection as owner_project,
)
from gui_modules.application import fold_designer_composition_receiving as gui
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application import receiving_multi_settings_window as window


def _layout():
    return api.append_receiving_set(
        api.operator_new_receiving_layout(width=800, height=1600, depth=400)
    )


def _dialog(monkeypatch):
    layout = _layout()
    adapter = ReceivingSetBayAdapter(layout)
    events = []

    class DoorHost:
        def _door_layout_baseline_scene(self, *args):
            events.append(("door_baseline", args))
            return None, None

    door_host = DoorHost()
    app = SimpleNamespace(
        root=None,
        _scene_query_callback=door_host._door_layout_baseline_scene,
        _phase6_input_snapshot={"receiving_layout": layout},
    )

    def settings_ports(_namespace, index):
        events.append(("settings_port", index))
        return {
            "select": lambda bay: events.append(("select_setting", bay)),
            "row": lambda: adapter.layout["sets"][index],
        }

    owner = SimpleNamespace(
        app=app,
        receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda _namespace: adapter,
        receiving_settings_ports=settings_ports,
        mark_receiving_switch_layout_dirty=lambda _namespace, _adapter: events.append(("dirty",)),
    )
    monkeypatch.setattr(window, "open_multi_settings", lambda _root, **kwargs: kwargs)
    ports = gui.open_receiving_multi_settings(owner, None)
    assert isinstance(ports, dict)
    return ports, adapter, events


def test_single_owner_public_api_and_root_identity():
    assert api.project_receiving_operator_set_bay_selection is owner_project
    assert ae_engine.project_receiving_operator_set_bay_selection is owner_project
    assert "project_receiving_operator_set_bay_selection" in ae_engine.__all__


@pytest.mark.parametrize(("set_index", "bay_index", "expected"), [
    (0, 0, (0, 0)), (1, 0, (1, 0)), ("1", "0", (1, 0)),
    ("01", "+0", (1, 0)),
])
def test_engine_qualifies_real_existing_set_bay_without_mutating_layout(
    set_index, bay_index, expected,
):
    layout = _layout()
    before = deepcopy(layout)
    target = api.project_receiving_operator_set_bay_selection(
        layout, set_index=set_index, bay_index=bay_index,
    )
    assert (target["set_index"], target["bay_index"]) == expected
    assert target["set_id"] == layout["sets"][expected[0]]["stable_id"]
    assert json.loads(json.dumps(target)) == target
    assert layout == before


@pytest.mark.parametrize(("set_index", "bay_index"), [
    (True, 0), (0, False), (1.5, 0), (0, 0.1),
    (None, 0), (0, None), (2, 0), (0, 1),
    (-1, 0), (0, -1), ("1_0", 0), (0, "1_0"),
    (" 1", 0), (0, " 0"), ([], 0),
])
def test_invalid_physical_set_bay_rejected_before_mutation(set_index, bay_index):
    layout = _layout()
    original = deepcopy(layout)
    with pytest.raises(ValueError, match="Receiving"):
        api.project_receiving_operator_set_bay_selection(
            layout, set_index=set_index, bay_index=bay_index,
        )
    assert layout == original


@pytest.mark.parametrize(("port_name", "args"), [
    ("select_bay", (True, 0)), ("select_bay", (1, False)),
    ("select_bay", (1, 1.8)), ("select_bay", (1, 1)),
    ("rename_bay", (1.9, 0, "P8")),
    ("rename_bay", (1, True, "P8")),
    ("on_setting_selected", (1, 1.5, "back_panel_mode")),
    ("get_original_door_marks", (False, 0)),
    ("get_original_door_marks", (1, 1)),
])
def test_actual_multi_modal_callbacks_reject_invalid_without_partial_selection(
    monkeypatch, port_name, args,
):
    ports, adapter, events = _dialog(monkeypatch)
    layout_before = deepcopy(adapter.layout)
    selection_before = adapter.selection
    with pytest.raises(ValueError, match="Receiving"):
        ports[port_name](*args)
    assert adapter.layout == layout_before
    assert adapter.selection == selection_before
    assert events == []


def test_modal_valid_set_and_bay_navigation_and_persisted_panel_rename(monkeypatch):
    ports, adapter, events = _dialog(monkeypatch)
    original = deepcopy(adapter.layout)
    ports["select_bay"]("1", "0")
    assert (adapter.selection.set_index, adapter.selection.bay_index) == (1, 0)
    assert adapter.layout == original
    assert ports["rename_bay"]("1", "0", "P8") is True
    assert adapter.layout["sets"][1]["bays"][0]["panel_name"] == "P8"
    assert events == [("dirty",)]
    restored = json.loads(json.dumps(adapter.layout, ensure_ascii=False))
    assert api.normalize_receiving_layout(restored) == adapter.layout


def test_modal_existing_setting_rejects_invalid_before_ports_or_mutation(monkeypatch):
    ports, adapter, events = _dialog(monkeypatch)
    before = deepcopy(adapter.layout)
    with pytest.raises(ValueError, match="Receiving"):
        ports["on_setting_selected"]("1_0", 0, "back_panel_mode")
    assert events == [] and adapter.layout == before


def test_gui_modal_has_no_premature_integer_cast_in_four_physical_callbacks():
    source = inspect.getsource(gui.open_receiving_multi_settings)
    selection = source[source.index("    def select_bay("):source.index("    def single_brand():")]
    marks = source[source.index("    def existing_door_marks("):source.index("    def cached_initial_door_marks():")]
    assert selection.count("manufacturing_api.project_receiving_operator_set_bay_selection(") == 3
    assert marks.count("manufacturing_api.project_receiving_operator_set_bay_selection(") == 1
    assert "int(set_index)" not in selection + marks
    assert "int(bay_index)" not in selection + marks
