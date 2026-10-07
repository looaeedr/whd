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


def test_issue1355_render_projection_methods_are_extracted_without_editor_lifecycle():
    from gui_modules.application import door_render_host_adapter
    host = gui.Phase6ApplicationHost
    assert host.draw_door is door_render_host_adapter.draw_door
    assert host.draw_door_layout_overview is door_render_host_adapter.draw_door_layout_overview
    assert host.draw_indicator_box is door_render_host_adapter.draw_indicator_box
    assert host.draw_indicator_door is door_render_host_adapter.draw_indicator_door
    assert host.draw_base_plate is door_render_host_adapter.draw_base_plate
    assert len(inspect.getsource(gui).splitlines()) < 2050
    owner = inspect.getsource(door_render_host_adapter)
    assert "open_door_layout_cell_editor" not in owner
    assert "_set_receiving_inner_door_enabled" not in owner
    assert "from gui import" not in owner
    assert "import gui" not in owner
