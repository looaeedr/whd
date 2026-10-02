from pathlib import Path


def test_all_major_panel_canvases_share_unified_hole_editor():
    src = Path('gui.py').read_text(encoding='utf-8')
    assert 'def _open_unified_hole_editor' in src
    assert 'def _open_generic_feature_surface_editor' not in src
    assert 'def _attach_part_hole_entrypoint' in src
    for key in ('box_body','door','base_plate','indicator_box','indicator_door','head','tail'):
        assert f'"{key}"' in src


def test_all_part_editors_pass_finished_reference_guide_without_replacing_surface():
    source = Path('gui_modules/editors/hole_editor.py').read_text(encoding='utf-8')
    assert 'build_finished_reference_guide' in source
    assert '"reference_guide": reference_guide' in source
    assert 'feature_surface_from_structural_result' in source
    assert 'host._open_unified_hole_editor(' in source
    assert 'reference_guide=reference_guide' in source
