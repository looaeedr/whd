import ast
from pathlib import Path


def test_door_layout_number_text_remains_staticmethod():
    source = Path(__file__).resolve().parents[1].joinpath('gui.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'BoxCalculatorGUI')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_door_layout_number_text')
    decorators = {ast.unparse(d) for d in fn.decorator_list}
    assert 'staticmethod' in decorators
    assert [a.arg for a in fn.args.args] == ['value']
