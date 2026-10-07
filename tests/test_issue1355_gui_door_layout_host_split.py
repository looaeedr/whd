from __future__ import annotations

import inspect

import gui
from gui_modules.application import door_layout_host_adapter


def test_issue1355_door_layout_host_methods_are_extracted():
    host = gui.Phase6ApplicationHost
    assert host.set_door_layout_columns is door_layout_host_adapter.set_door_layout_columns
    assert host.get_door_layout_cells is door_layout_host_adapter.get_door_layout_cells
    assert host.commit_door_layout_width is door_layout_host_adapter.commit_door_layout_width
    assert host.commit_door_layout_height is door_layout_host_adapter.commit_door_layout_height
    assert host.remove_door_layout_column is door_layout_host_adapter.remove_door_layout_column
    assert host.remove_door_layout_height is door_layout_host_adapter.remove_door_layout_height


def test_issue1355_adapter_excludes_receiving_inner_door_and_gui_shrinks():
    facade = inspect.getsource(gui)
    owner = inspect.getsource(door_layout_host_adapter)
    assert len(facade.splitlines()) < 2200
    assert "_receiving_inner_door_stable_id_for_cell" not in owner
    assert "_set_receiving_inner_door_enabled" not in owner
    assert "def set_door_layout_columns" not in facade
    assert "def set_door_layout_columns" in owner
