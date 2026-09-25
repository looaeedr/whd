from types import SimpleNamespace

from gui_source_contract_helpers import compile_phase6_host_method


def _load_method(name):
    return compile_phase6_host_method(name)


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
