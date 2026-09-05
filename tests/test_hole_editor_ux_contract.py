from pathlib import Path


def _editor_body():
    src=Path('gui.py').read_text(encoding='utf-8')
    return src[src.index('    def _open_unified_hole_editor'):src.index('    def open_hole_editor')]


def test_hole_editor_keeps_left_catalog_explicit_insert_and_custom_blind_checkbox():
    body=_editor_body()
    assert 'text="一般開孔"' in body
    assert 'text="管孔清單"' in body
    assert 'selected_catalog_text' in body
    assert 'text="插入"' in body
    assert '＋ 自訂圓孔' in body and '＋ 自訂方孔' in body
    assert 'text="盲孔"' in body


def test_hole_editor_has_no_visible_legacy_as_vs_builtin_choices():
    body=_editor_body()
    assert 'type_options' not in body
    assert '"AS"' not in body and '"VS"' not in body
