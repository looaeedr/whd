import ast
from pathlib import Path

GUI = Path(__file__).parents[1] / 'gui.py'


def _source_of_method(name):
    source = GUI.read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'BoxCalculatorGUI')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method)


def test_door_editor_uses_dynamic_indicator_box_page_not_component_edit_buttons():
    source = _source_of_method('_open_unified_hole_editor')
    assert '編輯盒子' not in source
    assert '編輯小門' not in source
    assert 'indicator_component_context_provider' in source
    assert '指示燈盒' in source
    assert 'indicator_page' in source


def test_multi_door_editor_supplies_per_cell_indicator_component_context_provider():
    source = _source_of_method('open_door_layout_cell_editor')
    assert 'indicator_component_context_provider' in source
    assert '_indicator_component_editor_contexts' in source
    assert 'door_layout_indicator_box_features' in source
    assert 'door_layout_indicator_door_features' in source


def test_single_door_editor_uses_same_indicator_component_page_flow():
    source = _source_of_method('open_part_hole_editor')
    assert 'indicator_component_context_provider' in source
    assert '_indicator_component_editor_contexts' in source
    assert 'indicator_component_openers' not in source


def test_small_door_spec_delegates_to_values_adapter_that_uses_manufacturing_api_helper():
    public_source = _source_of_method('_indicator_door_part_spec')
    adapter_source = _source_of_method('_indicator_door_part_spec_from_values')
    assert '_indicator_door_part_spec_from_values' in public_source
    assert 'manufacturing_api.indicator_small_door_spec' in adapter_source


def test_active_indicator_component_reloads_formula_context_when_groups_change():
    source = _source_of_method('_open_unified_hole_editor')
    assert 'if context_key == active_context_key[0]:' not in source
    assert 'indicator_component_context_provider(state_now)' in source
