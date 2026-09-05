import ast
from pathlib import Path
from types import MethodType, SimpleNamespace


def _load_method(name):
    source = Path('gui.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BoxCalculatorGUI')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    fn = ast.FunctionDef(
        name=method.name, args=method.args, body=method.body,
        decorator_list=[], returns=method.returns, type_comment=method.type_comment,
    )
    ast.fix_missing_locations(fn)
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'gui.py', 'exec'), ns)
    return ns[name]


class FakeVar:
    def __init__(self, owner, value):
        self.owner = owner
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.owner.on_baseline_changed()


def test_legacy_corner_transaction_delegates_to_live_snapshot_and_confirms_when_applied():
    apply_tx = _load_method('_apply_fold_designer_corner_transaction')
    calls = []
    payload = {
        'model': '自訂',
        'corner_state': {'door': {'top_left': {'type_id': 'C02', 'rotation_quadrants': 1}}},
        'corner_pair_same': {'door': {'top': False, 'bottom': True}},
        'active_part': 'door',
    }
    project_controller = SimpleNamespace(
        confirm_designer=lambda snapshot: calls.append(('confirm', snapshot))
    )
    app = SimpleNamespace(
        _apply_fold_designer_live_snapshot=lambda incoming: (calls.append(('live', incoming)) or True),
        _compose_phase6_project_snapshot_from_main_gui=lambda: {'committed': True},
        project_controller=project_controller,
    )

    assert apply_tx(app, payload) is True
    assert calls == [('live', payload), ('confirm', {'committed': True})]


def test_legacy_corner_transaction_does_not_confirm_when_live_apply_is_rejected():
    apply_tx = _load_method('_apply_fold_designer_corner_transaction')
    calls = []
    app = SimpleNamespace(
        _apply_fold_designer_live_snapshot=lambda incoming: False,
        _compose_phase6_project_snapshot_from_main_gui=lambda: {'committed': True},
        project_controller=SimpleNamespace(confirm_designer=lambda snapshot: calls.append(snapshot)),
    )
    assert apply_tx(app, {'model': '自訂'}) is False
    assert calls == []
