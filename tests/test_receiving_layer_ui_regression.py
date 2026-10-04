from __future__ import annotations

import ast
import inspect
from pathlib import Path

from ae_engine.receiving_switch_layout import (
    RECEIVING_SWITCH_BRANDS,
    RECEIVING_SWITCH_LAYOUT_KEY,
    new_receiving_switch_layout,
    resize_switch_layers,
    set_layer_connection_count,
)
from gui_modules.application import receiving_set_bay_controls as controls
from gui_modules.application.receiving_switch_layout_adapter import ReceivingSwitchLayoutAdapter

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / 'fold_designer_bridge.py'
NAV = ROOT / 'phase6_navigation_view_adapter.py'
FINAL_VIEW = ROOT / 'phase6_final_scene_view.py'


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, node) or ''


def test_receiving_operator_terms_are_chinese_layers_connections_and_switch_brand_options():
    assert RECEIVING_SWITCH_BRANDS == ('士林', '東元', '三菱', '伍菱', '順山')
    source = Path(inspect.getsourcefile(controls)).read_text(encoding='utf-8')
    assert '−Bay' not in source
    assert '+Bay' not in source
    assert 'Set 1' not in source
    assert 'Bay 1' not in source
    assert '開關' in source
    assert '＋層' in source
    assert '預覽' in source


def test_switch_layout_is_separate_from_multi_cabinet_receiving_layout():
    layout = new_receiving_switch_layout(brand='東元')
    layout = resize_switch_layers(layout, 2)
    layout = set_layer_connection_count(layout, layer_index=0, connection_count=3)
    assert layout['switch_brand'] == '東元'
    assert [row['connection_count'] for row in layout['layers']] == [3, 1]
    assert RECEIVING_SWITCH_LAYOUT_KEY == 'receiving_switch_layout'
    assert 'sets' not in layout and 'bays' not in layout and 'joints' not in layout


def test_switch_layout_adapter_edits_each_layer_without_manufacturing_callback():
    adapter = ReceivingSwitchLayoutAdapter(new_receiving_switch_layout())
    adapter.resize_connections(0, 2)
    adapter.add_layer()
    adapter.resize_connections(1, 1)
    assert adapter.connection_counts() == (3, 2)
    assert adapter.set_brand('三菱') is True
    assert adapter.brand == '三菱'


def test_each_layer_row_has_own_connection_resize_and_preview_callbacks():
    source = inspect.getsource(controls.refresh_receiving_layer_rows)
    assert 'on_resize_connections(layer_index, -1)' in source
    assert 'on_resize_connections(layer_index, 1)' in source
    assert 'on_preview(layer_index)' in source
    assert '第{layer_index + 1}層' in source
    assert '{connection_count}連' in source


def test_receiving_connection_resize_is_configuration_only_and_never_flushes_3d():
    source = _function_source(BRIDGE, '_phase6_resize_receiving_bays')
    assert 'layer_index' in source
    assert '_phase6_receiving_switch_adapter' in source
    assert 'receiving_layout' not in source
    assert '_phase6_sync_receiving_current_bay' not in source
    assert '.do_update(' not in source
    assert 'submit_update_intent' not in source
    assert '_phase6_refresh_receiving_set_bay_control' in source


def test_preview_confirmation_fails_closed_without_authoritative_brand_opening_resolver():
    source = _function_source(BRIDGE, '_phase6_confirm_receiving_opening')
    assert '_phase6_receiving_switch_opening_resolver' in source
    assert '開孔規格尚未建立' in source
    assert 'layer_index' in source and 'connection_index' in source
    assert '.do_update(' not in source


def test_box_body_physical_child_notebook_is_visible_for_parent_or_child_context():
    source = _function_source(NAV, 'refresh_box_body_piece_selector')
    assert 'show_for_box_body' in source
    assert 'notebook.pack(' in source
    assert 'active == "box_body" or active in wanted' in source


def test_assembly_visibility_and_diagnostic_changes_are_display_only():
    for name in ('_phase6_on_assembly_part_visibility_changed', '_phase6_on_assembly_diagnostic_changed'):
        source = _function_source(BRIDGE, name)
        assert 'submit_update_intent' in source
        assert '"display"' in source
        assert '.do_update(' not in source


def test_assembly_render_does_not_force_duplicate_live_publish():
    source = FINAL_VIEW.read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Phase6FinalSceneViewAdapter')
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'query_assembly_render_data')
    fn_source = ast.get_source_segment(source, fn) or ''
    assert 'resolve_geometry()' in fn_source
    assert 'publish_live_state(force=True)' not in fn_source
