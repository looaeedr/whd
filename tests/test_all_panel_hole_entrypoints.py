from pathlib import Path


def test_every_primary_panel_uses_double_click_unified_hole_entrypoint():
    source = (Path(__file__).resolve().parents[1] / 'gui.py').read_text(encoding='utf-8')
    attach = source[source.index('def _attach_part_hole_entrypoint'):source.index('def setup_tab_endcap_ui')]
    assert 'Double-Button-1' in attach
    assert 'open_part_hole_editor' in attach
    assert 'canvas.unbind("<Button-3>")' in attach
    for key in ('box_body','door','base_plate','indicator_box','indicator_door'):
        assert f'"{key}"' in source
    endcap = source[source.index('def setup_tab_endcap_ui'):source.index('def setup_tab_base_plate_ui')]
    assert 'Double-Button-1' in endcap
    assert 'Button-3' not in endcap
