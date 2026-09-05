from pathlib import Path
from ae_engine.hole_catalog import custom_circle_definition, custom_rectangle_definition


def test_custom_circle_and_rectangle_default_to_cutting_and_checkbox_makes_blind():
    assert custom_circle_definition(22).process == 'CUTTING'
    assert custom_rectangle_definition(90,50).process == 'CUTTING'
    assert custom_circle_definition(22,blind=True).process == 'BLIND_HOLE'
    assert custom_rectangle_definition(90,50,blind=True).process == 'BLIND_HOLE'


def test_gui_catalog_sources_are_only_the_two_csv_loaders():
    source=Path('gui.py').read_text(encoding='utf-8')
    block=source[source.index('def _open_unified_hole_editor'):source.index('def open_hole_editor')]
    assert 'load_hole_catalog(hole_base_dir)' in block
    assert 'load_pipe_catalog(hole_base_dir)' in block
    assert '"AS"' not in block and '"VS"' not in block
