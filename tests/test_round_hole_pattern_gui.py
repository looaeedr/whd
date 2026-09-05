from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / 'gui.py').read_text(encoding='utf-8')


def test_unified_editor_has_separate_general_and_pipe_catalogs():
    assert '一般開孔' in SRC
    assert '管孔清單' in SRC
    assert 'pipe_catalog_list' in SRC
    assert 'load_hole_catalog(hole_base_dir)' in SRC
    assert 'load_pipe_catalog(hole_base_dir)' in SRC


def test_round_hole_settings_exposes_all_requested_controls():
    assert '圓孔排列設定' in SRC
    for text in ('向左', '向右', '向上', '向下', '左右兩側', '上下兩側'):
        assert text in SRC
    for text in ('孔心距', '間距', '孔心齊', '管頂齊', '管底齊', '填滿', '重新填滿'):
        assert text in SRC


def test_round_spacing_driver_is_switched_by_editing_either_field():
    assert 'round_driver.set("center")' in SRC
    assert 'round_driver.set("gap")' in SRC
    assert 'circle_center_distance_from_gap' in SRC
    assert 'circle_gap_from_center_distance' in SRC


def test_reference_overlay_groups_x_y_edge_values_and_uses_smaller_font():
    assert 'x_group' in SRC
    assert 'y_group' in SRC
    assert "entry_font = ('Consolas', 12, 'bold')" in SRC
    assert 'X 到' in SRC and 'Y 到' in SRC


def test_last_confirmed_position_workflow_is_recorded():
    assert 'position_authority' in SRC
    assert 'position_authority[0] = "reference"' in SRC
    assert 'position_authority[0] = "round"' in SRC
