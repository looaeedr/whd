from pathlib import Path


def test_gui_uses_shared_hole_catalog_and_resource_directory():
    source=Path('gui.py').read_text(encoding='utf-8')
    assert 'load_hole_catalog' in source and 'load_pipe_catalog' in source and 'feature_from_definition' in source
    assert 'ae.baseline_hole_catalog_root_path()' in source
    assert 'ae.get_resource_path("基準檔/開孔")' not in source
    assert "ae.get_resource_path('基準檔/開孔')" not in source
    assert r'Z:\whd\基準檔\管孔尺寸清單.csv' not in source


def test_gui_exposes_quadrant_rotation_and_blind_hole_color():
    source=Path('gui.py').read_text(encoding='utf-8')
    for angle in ('90°','180°','270°','360°'): assert angle in source
    assert 'BLIND_HOLE' in source and 'ResolvedProfile' in source


def test_catalog_double_click_enters_insert_mode_except_custom_rows():
    source=Path('gui.py').read_text(encoding='utf-8')
    start=source.index('    def _open_unified_hole_editor(')
    end=source.index('    def open_hole_editor(', start)
    s=source[start:end]
    assert 'catalog_list.bind("<Double-Button-1>"' in s
    assert 'def on_catalog_double_click' in s
    assert 'label.startswith("＋ 自訂")' in s
    assert 'set_insert_mode(True)' in s
