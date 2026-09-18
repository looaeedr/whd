import ast
from pathlib import Path

GUI = Path(__file__).parents[1] / 'gui.py'
DOOR_VIEW = Path(__file__).parents[1] / 'gui_modules' / 'rendering' / 'door_view.py'


def _source_of_method(name):
    source = GUI.read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Phase6ApplicationHost')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method)


def _source_of_render_function(name):
    source = DOOR_VIEW.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return ast.get_source_segment(source, function)


def test_each_column_keeps_its_own_height_partition():
    source = _source_of_method('commit_door_layout_height')
    assert 'column = self.door_layout_columns[column_index]' in source
    assert '_recompute_door_layout_remainders' in source


def test_canvas_explains_asymmetric_per_column_split_workflow():
    source = _source_of_render_function('draw_door_layout_overview_preview')
    assert '各欄獨立分層' in source
    assert '2 / 3 / 2' in source
