import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOOR_LAYOUT_METHODS = {
    '_door_layout_number_text', '_new_door_layout_column', 'set_door_layout_columns',
    '_ensure_door_layout_default', '_parse_layout_value', '_recompute_column_height_remainder',
    '_recompute_door_layout_remainders', 'get_door_layout_columns', 'get_door_layout_cells',
    '_door_layout_cell_key', 'get_selected_door_layout_cell', 'select_door_layout_cell',
    '_sync_door_canvas_double_click_binding', 'toggle_multi_door_layout',
    '_reject_door_layout_dimension', 'commit_door_layout_width', 'commit_door_layout_height',
    'add_door_layout_column', '_remap_door_layout_owned_data', 'remove_door_layout_column',
    'add_door_layout_height', 'remove_door_layout_height', '_on_door_layout_value_changed',
    '_on_total_door_dimension_changed', 'refresh_door_layout_status', 'rebuild_door_layout_ui',
    'setup_tab_door_ui',
}


def _box_methods():
    tree = ast.parse((ROOT / 'gui.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BoxCalculatorGUI')
    return {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}


def test_all_door_layout_methods_needed_by_gui_are_present():
    methods = _box_methods()
    assert DOOR_LAYOUT_METHODS <= methods, sorted(DOOR_LAYOUT_METHODS - methods)
