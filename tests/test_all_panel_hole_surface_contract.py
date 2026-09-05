from pathlib import Path


def test_all_major_panel_canvases_share_unified_hole_editor():
    src = Path('gui.py').read_text(encoding='utf-8')
    assert 'def _open_unified_hole_editor' in src
    assert 'def _open_generic_feature_surface_editor' not in src
    assert 'def _attach_part_hole_entrypoint' in src
    for key in ('box_body','door','base_plate','indicator_box','indicator_door','head','tail'):
        assert f'"{key}"' in src


def test_all_part_editors_pass_finished_reference_guide_without_replacing_surface():
    from pathlib import Path
    s = Path('gui.py').read_text(encoding='utf-8')
    start = s.index('    def open_part_hole_editor(')
    end = s.index('    def _open_unified_hole_editor(', start)
    section = s[start:end]
    assert 'build_finished_reference_guide' in section
    assert 'reference_guide=reference_guide' in section
    assert 'feature_surface_from_structural_result' in section
    cap_start = s.index('    def open_hole_editor(')
    cap = s[cap_start:]
    assert 'reference_guide=' in cap
