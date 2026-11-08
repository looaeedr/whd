"""#2517: Family switch cache and Receiving Set/Bay rebind use Engine Family IDs."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
import gui_modules.application.fold_designer_composition_shell_settings as shell


class Var:
    def __init__(self, value):
        self.value = str(value)
        self.calls = []
    def set(self, value):
        self.value = str(value)
        self.calls.append(self.value)
    def get(self):
        return self.value


def _host(old_model, new_model, *, prior_parts=None):
    snapshot = {
        "model": new_model,
        "receiving_layout": {"sets": [{"bays": [{"nfb_config_submitted": True}]}]},
        "existing_parts": ["box_body", "head", "tail", "door"],
    }
    rebinding = []
    resets = []
    part_updates = []
    navigation = SimpleNamespace(
        replace_receiving_mode=lambda source: rebinding.append(deepcopy(source)),
    )
    workspace = SimpleNamespace(
        replace_available_parts=lambda items: part_updates.append(tuple(items)),
    )
    app = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(snapshot),
        _phase6_settings_guard=False,
        _phase6_non_receiving_part_presence_state=deepcopy(prior_parts),
        designer_workspace=workspace,
        left_global_vars={}, setting_vars={},
        v_w=Var(800), v_h=Var(1600), v_d=Var(350),
    )
    legacy = SimpleNamespace(tk=SimpleNamespace(BooleanVar=type("BooleanVar", (), {})))
    controller = SimpleNamespace(
        app=app,
        capabilities=SimpleNamespace(
            workspace=SimpleNamespace(navigation=lambda: navigation),
        ),
        receiving_adapter=lambda namespace, *, reset=False: resets.append(reset),
        _required=lambda _ns, key: {
            "original": legacy,
            "_setting_number_text": str,
        }[key],
    )
    plan = SimpleNamespace(
        defaults={}, remember_non_receiving_structure=None,
        assembly_type="INSERT_OVERLAY",
    )
    return controller, app, plan, rebinding, resets, part_updates


def _commit(controller, plan, old_model, new_model):
    shell.settings_application_project_ui_values(
        controller, object(), {}, baseline_transition=plan,
        baseline_stage="commit", old_model=old_model, new_model=new_model,
    )


@pytest.mark.parametrize("alias", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_switching_from_vault_to_any_registered_receiving_alias_rebinds_real_bay(alias):
    ctl, app, plan, rebind, reset, parts = _host("金庫型", alias)
    snapshot = deepcopy(app._phase6_input_snapshot)
    _commit(ctl, plan, "金庫型", alias)
    assert rebind == [snapshot]
    assert reset == [True]
    assert not parts
    assert app._phase6_input_snapshot == snapshot


@pytest.mark.parametrize("old,new", [
    ("受電箱", "RECEIVING"),
    ("RECEIVING", "receiving"),
    ("receiving", "ReCeIvInG"),
    ("ReCeIvInG", "受電箱"),
])
def test_alias_only_switch_is_not_a_new_receiving_family(old, new):
    ctl, app, plan, rebind, reset, parts = _host(old, new)
    _commit(ctl, plan, old, new)
    assert not rebind and not reset and not parts


@pytest.mark.parametrize("alias", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
@pytest.mark.parametrize("target,stored", [("金庫型", "金庫型"), ("VAULT", "金庫型")])
def test_leaving_any_receiving_alias_restores_only_matching_family_part_set(
        alias, target, stored):
    prior = {"model": stored, "parts": ("box_body", "head")}
    ctl, app, plan, rebind, reset, parts = _host(alias, target, prior_parts=prior)
    _commit(ctl, plan, alias, target)
    assert parts == [("box_body", "head")]
    assert app._phase6_input_snapshot["existing_parts"] == ["box_body", "head"]
    assert not rebind and not reset


def test_saved_part_presence_for_different_family_is_not_replayed():
    ctl, app, plan, rebind, reset, parts = _host(
        "receiving", "金庫型",
        prior_parts={"model": "自訂", "parts": ("box_body",)},
    )
    original = deepcopy(app._phase6_input_snapshot["existing_parts"])
    _commit(ctl, plan, "receiving", "金庫型")
    assert not parts
    assert app._phase6_input_snapshot["existing_parts"] == original
    assert not rebind and not reset


def test_real_gui_delegate_uses_public_canonical_identity_not_hardcoded_strings():
    source = inspect.getsource(shell.settings_application_project_ui_values)
    assert "manufacturing_api.operator_canonical_family_name(" in source
    assert 'old_model != "受電箱" and new_model == "受電箱"' not in source
    assert 'old_model == "受電箱" and new_model != "受電箱"' not in source
    assert manufacturing_api.operator_canonical_family_name("ReCeIvInG") == "受電箱"
