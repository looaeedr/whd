"""#2517 BoxBody operator symmetry must use the Engine's public boolean gate."""
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.fold_designer_composition_registry_edges import (
    on_box_symmetry_changed,
)
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_settings_transitions import normalize_symmetry


@pytest.mark.parametrize("source,expected", [
    ("false", False), ("FALSE", False), ("0", False), ("off", False),
    ("no", False), ("", False), (False, False), (0, False),
    ("true", True), ("TRUE", True), ("1", True), ("on", True),
    ("yes", True), (True, True), (1, True),
])
def test_symmetry_transition_delegates_to_public_engine_boolean_contract(source, expected):
    assert normalize_symmetry(source) is expected
    assert normalize_symmetry(source) is manufacturing_api.normalize_operator_settings_boolean(source)


@pytest.mark.parametrize("invalid", [
    "surprise", "2", 2, -1, 1.5, float("nan"), float("inf"), None,
])
def test_invalid_symmetry_cannot_be_coerced_to_true_or_false(invalid):
    with pytest.raises(ValueError, match="布林值"):
        normalize_symmetry(invalid)


def _caller(value, *, initial=False, allowed=True):
    effects = []
    state = SimpleNamespace(symmetric=initial)
    operator_var = SimpleNamespace(get=lambda: value)
    app = SimpleNamespace(
        state=state, v_sy=operator_var, _job=None, root=None,
        do_update=lambda: effects.append("redraw"),
    )
    transaction = SimpleNamespace(mark_workspace_dirty=lambda: effects.append("dirty"))
    transaction.commit_symmetry = lambda target_state, raw: (
        Phase6SettingsTransactionController.commit_symmetry(transaction, target_state, raw)
    )
    commands = {
        "_phase6_box_symmetry_allowed": lambda owner: allowed,
        "_phase6_apply_box_symmetry_policy": lambda owner: (
            effects.append("family-block"),
            setattr(owner.state, "symmetric", False),
        ),
    }
    handler = SimpleNamespace(
        app=app, _required=lambda namespace, name: commands[name],
        settings_transactions=lambda: transaction,
    )
    return handler, state, effects


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("0", False), ("true", True), ("1", True),
])
def test_live_gui_switch_preserves_raw_source_until_engine_commit(raw, expected):
    handler, state, effects = _caller(raw, initial=not expected)
    assert on_box_symmetry_changed(handler, None) is expected
    assert state.symmetric is expected
    assert effects == ["dirty", "redraw"]


@pytest.mark.parametrize("bad", ["not-a-boolean", 2, float("nan"), None])
def test_live_invalid_symmetry_rejected_without_mutating_state_or_redraw(bad):
    handler, state, effects = _caller(bad, initial=False)
    assert on_box_symmetry_changed(handler, None) is None
    assert state.symmetric is False
    assert effects == []


def test_receiving_family_forbids_symmetry_even_for_stale_true_widget():
    handler, state, effects = _caller("true", initial=True, allowed=False)
    assert on_box_symmetry_changed(handler, None) is False
    assert state.symmetric is False
    assert effects == ["family-block", "dirty", "redraw"]


def test_symmetry_gui_kernel_does_not_invent_own_boolean_formula():
    import inspect
    from gui_modules.application import fold_designer_composition_registry_edges as gui
    import phase6_settings_transitions as kernel
    src = inspect.getsource(gui.on_box_symmetry_changed)
    assert "bool(var.get())" not in src
    assert "bool(getattr(app.state, " not in src
    assert "self.settings_transactions().commit_symmetry(app.state, target)" in src
    assert "manufacturing_api.normalize_operator_settings_boolean(value)" in inspect.getsource(
        kernel.normalize_symmetry,
    )
