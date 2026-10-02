from pathlib import Path


def _editor_source():
    return Path('gui_modules/editors/hole_editor.py').read_text(encoding='utf-8')


def test_endcap_routes_into_unified_editor_with_full_surface_validation():
    source = _editor_source()
    assert 'feature_surface_from_rect' in source
    assert 'host._open_unified_hole_editor' in source
    assert 'feature_is_within_surface' in source
    assert 'move_feature_within_surface' in source


def test_unified_drag_does_not_directly_bypass_surface_validation():
    source = _editor_source()
    start = source.index('class HoleEditorCanvasPointerActions:')
    end = source.index('class HoleEditorReferenceActions:', start)
    block = source[start:end]
    assert 'move_feature_within_surface' in block
    assert 'move_feature_to_finished_point' not in block
