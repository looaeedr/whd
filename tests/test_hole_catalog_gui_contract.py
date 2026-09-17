from pathlib import Path


def _editor_source():
    root = Path(__file__).resolve().parents[1]
    return "\n".join(
        (root / path).read_text(encoding='utf-8')
        for path in (
            'gui_modules/editors/hole_editor.py',
            'gui_modules/editors/hole_editor_composition.py',
            'gui_modules/editors/hole_editor_view.py',
        )
    )


def test_gui_uses_shared_hole_catalog_and_resource_directory():
    source=_editor_source()
    assert 'load_hole_catalog' in source and 'load_pipe_catalog' in source and 'feature_from_definition' in source
    assert 'baseline_hole_catalog_root_path()' in source
    assert 'ae.get_resource_path("基準檔/開孔")' not in source
    assert "ae.get_resource_path('基準檔/開孔')" not in source
    assert r'Z:\whd\基準檔\管孔尺寸清單.csv' not in source


def test_gui_exposes_quadrant_rotation_and_blind_hole_color():
    source=_editor_source()
    assert 'for angle in (90, 180, 270, 360):' in source
    assert 'BLIND_HOLE' in source and 'ResolvedProfile' in source


def test_catalog_double_click_enters_insert_mode_except_custom_rows():
    source=_editor_source()
    assert '"<Double-Button-1>"' in source
    assert 'def on_catalog_double_click' in source
    assert 'self.selected_catalog_text.get().startswith("＋ 自訂")' in source
    assert 'self.set_insert_mode(True)' in source
