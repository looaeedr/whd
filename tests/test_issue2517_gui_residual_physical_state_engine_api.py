"""#2517: remaining GUI Family/Corner/Receiving physical decisions are Engine API."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import cabinet_family_model_transition as model_owner
from ae_engine import corner_state_transactions as corner_owner
from ae_engine import operator_part_session_profiles as session_owner
import phase6_settings_transitions as gui_settings
import phase6_sync_envelope as gui_sync
from phase6_settings_transaction_controller import Phase6SettingsTransactionController


@pytest.mark.parametrize("target,previous,changed,normalized", [
    ("受電箱", "金庫型", True, "受電箱"),
    (" 金庫型 ", "金庫型", False, "金庫型"),
    ("RECEIVING", "受電箱", True, "RECEIVING"),
    ("", "金庫型", False, ""),
    (None, "受電箱", False, ""),
    ("受電箱", "受電箱", False, "受電箱"),
])
def test_headless_and_gui_external_model_decisions_identical(
    target, previous, changed, normalized,
):
    direct = api.plan_operator_external_model_change(target, previous)
    adapter = gui_settings.plan_external_model_change(target, previous)
    assert direct == adapter
    assert type(adapter) is api.OperatorExternalModelPlan
    assert gui_settings.ExternalModelPlan is model_owner.OperatorExternalModelPlan
    assert direct.changed is changed
    assert direct.target_model == normalized
    with pytest.raises(FrozenInstanceError):
        direct.changed = False


def test_corner_replace_uses_same_engine_result_and_detaches_both_saved_maps():
    raw = {"head": {"top_left": {"type_id": "STANDARD", "note": [1, 2]}}}
    paired = {"head": {"top": False, "bottom": True}}
    before = deepcopy((raw, paired))
    actual = api.replace_corner_state(raw, paired)
    GUI = gui_settings.replace_corner_state(raw, paired)
    assert actual == GUI and type(actual) is api.CornerStateTransition
    assert api.replace_corner_state is corner_owner.replace_corner_state
    actual.corner_state["head"]["top_left"]["note"].append(99)
    actual.corner_pair_same["head"]["top"] = True
    assert (raw, paired) == before


def _sync_state(active="head", *, family="受電箱", mode="set_bay"):
    return {
        "model": family, "active_mode": mode, "active_part": active,
        "workspace": {
            "active_part": active,
            "existing_parts": ["box_body", "head", "tail", "door"],
        },
        "w": 820.0, "h": 1600.0, "d": 350.0,
        "corner_state": {"head": {"top_left": {"type_id": "STANDARD"}}},
        "assembly_relief": {"head": {"source": "persisted"}},
    }


def test_receiving_navigation_only_physical_skip_through_same_engine_gate():
    before = _sync_state("head")
    after = _sync_state("tail")
    original = deepcopy((before, after))
    assert api.operator_receiving_navigation_only_sync_change(before, after) is True
    assert gui_sync.navigation_only_change(before, after) is True
    assert (before, after) == original
    assert (gui_sync.navigation_only_change(before, after)
            == session_owner.operator_receiving_navigation_only_sync_change(before, after))

    metadata_after = deepcopy(after)
    metadata_after.update({"origin": "fold_designer", "revision": 16,
                           "transaction_id": "tx:16", "fingerprint": "x",
                           "delta": {"active_part": "tail"}})
    assert gui_sync.navigation_only_change(before, metadata_after) is True


@pytest.mark.parametrize("change", [
    lambda s: s.update({"w": 821.0}),
    lambda s: s.update({"model": "金庫型"}),
    lambda s: s.update({"model": "receiving"}),
    lambda s: s.update({"active_mode": "quantity"}),
    lambda s: s["workspace"].update({"existing_parts": ["head"]}),
    lambda s: s["workspace"].update({"active_part": "head"}),
    lambda s: s["corner_state"]["head"]["top_left"].update({"type_id": "CUT"}),
    lambda s: s.pop("assembly_relief"),
    lambda s: s.update({"unrecognized_source": "unsafe"}),
])
def test_physical_changes_or_unknown_fields_never_skip_sync(change):
    before = _sync_state("head")
    after = _sync_state("tail")
    change(after)
    assert api.operator_receiving_navigation_only_sync_change(before, after) is False
    assert gui_sync.navigation_only_change(before, after) is False


def test_same_active_part_and_invalid_envelopes_never_skip_sync():
    current = _sync_state("head")
    assert not gui_sync.navigation_only_change(current, deepcopy(current))
    assert not gui_sync.navigation_only_change(None, current)
    assert not gui_sync.navigation_only_change(current, None)


def test_gui_delegates_and_engine_owner_has_no_reverse_gui_dependency():
    assert "manufacturing_api.plan_operator_external_model_change(" in inspect.getsource(
        gui_settings.plan_external_model_change)
    assert "manufacturing_api.replace_corner_state(" in inspect.getsource(
        gui_settings.replace_corner_state)
    assert "manufacturing_api.operator_receiving_navigation_only_sync_change(" in inspect.getsource(
        gui_sync.navigation_only_change)
    assert "settings_transitions.plan_external_model_change(" in inspect.getsource(
        Phase6SettingsTransactionController.plan_external_model_change)
    for owner in (model_owner, corner_owner, session_owner):
        code = inspect.getsource(owner)
        assert "import tkinter" not in code and "from phase6_" not in code
        assert "from gui_modules" not in code
