from pathlib import Path


def test_endcap_routes_into_unified_editor_with_full_surface_validation():
    source=Path('gui.py').read_text(encoding='utf-8')
    wrapper=source[source.index('    def open_hole_editor'):]
    unified=source[source.index('    def _open_unified_hole_editor'):source.index('    def open_hole_editor')]
    assert 'feature_surface_from_rect' in wrapper
    assert 'self._open_unified_hole_editor' in wrapper
    assert 'feature_is_within_surface' in unified
    assert 'move_feature_within_surface' in unified


def test_unified_drag_does_not_directly_bypass_surface_validation():
    source=Path('gui.py').read_text(encoding='utf-8')
    unified=source[source.index('    def _open_unified_hole_editor'):source.index('    def open_hole_editor')]
    block=unified[unified.index('        def on_canvas_drag'):unified.index('        def on_canvas_up')]
    assert 'move_feature_within_surface' in block
    assert 'move_feature_to_finished_point' not in block
