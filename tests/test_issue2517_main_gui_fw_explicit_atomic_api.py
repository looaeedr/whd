"""#2517: main GUI box/head/tail FW choices use validated Engine transactions."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import endcap_factory_fold as owner
from gui import Phase6ApplicationHost


def _state(family="受電箱"):
    return api.normalize_endcap_fw_state({"model": family, "fw": 25})


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _gui(state=None, *, box=25.0, head=31.0, tail=36.0):
    calls = []
    gui = SimpleNamespace(
        endcap_fw_state=_state() if state is None else state,
        fw_z_var=_var(box),
        fw_head_var=_var(head),
        fw_tail_var=_var(tail),
        _sync_endcap_fw_controls=lambda: calls.append("sync"),
        _derived_cache_owner=SimpleNamespace(invalidate=lambda reason: calls.append(("invalidate", reason))),
        _request_phase6_update=lambda reason: calls.append(("update", reason)),
    )
    return gui, calls


def test_api_is_original_headless_owner_in_both_public_namespaces():
    assert api.commit_operator_endcap_fw_value is owner.commit_operator_endcap_fw_value
    assert ae_engine.commit_operator_endcap_fw_value is api.commit_operator_endcap_fw_value
    assert "commit_operator_endcap_fw_value" in ae_engine.__all__


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_explicit_head_tail_matches_original_engine_four_mode_transitions(family):
    actual, expected = _state(family), _state(family)
    head_ref, tail_ref = actual["head"], actual["tail"]
    for part, fw in [("head", "31.25"), ("head", 33.0), ("tail", 36.75)]:
        assert api.commit_operator_endcap_fw_value(actual, part, fw, box_fw=25) is actual
        assert owner.commit_endcap_fw(expected, part, float(fw), box_fw=25) is expected
        assert actual == expected
    assert actual["mode"] == api.FW_INDEPENDENT
    assert actual["head"]["value"] == 33
    assert actual["tail"]["value"] == 36.75
    assert actual["head"] is head_ref and actual["tail"] is tail_ref
    for part, value in [("head", 33.0), ("tail", 36.75)]:
        snapshot = {
            "model": family, "w": 500, "h": 600, "d": 200, "t": 2,
            "fw": 25, "endcap_fw": deepcopy(actual),
        }
        assert api.resolve_endcap_fw(snapshot, part) == value
        assert api.build_endcap_xy_fold_profiles(snapshot, part_key=part)["Y"]


@pytest.mark.parametrize("bad", [True, False, None, "", "invalid", 0, -4, float("nan"), float("inf"), "NaN"])
@pytest.mark.parametrize("field", ["head", "tail", "box"])
def test_invalid_explicit_fw_fails_without_source_changes(bad, field):
    state = _state()
    previous = deepcopy(state)
    refs = (state["head"], state["tail"])
    kwargs = {"box_fw": 25.0, "value": 32.0}
    if field == "box":
        kwargs["box_fw"] = bad
    else:
        kwargs["value"] = bad
    with pytest.raises((ValueError, TypeError)):
        api.commit_operator_endcap_fw_value(state, "head", **kwargs)
    assert state == previous
    assert state["head"] is refs[0] and state["tail"] is refs[1]


@pytest.mark.parametrize("malformed", [None, [], 8, "corrupt"])
def test_late_bad_tail_row_refused_before_head_commit(malformed):
    state = _state()
    state["mode"] = api.FW_FOLLOW_HEAD
    state["head"]["value"] = 33
    state["tail"] = malformed
    previous = deepcopy(state)
    with pytest.raises((TypeError, ValueError)):
        api.commit_operator_endcap_fw_value(state, "head", 35, box_fw=25)
    assert state == previous


@pytest.mark.parametrize("invalid", [True, None, "tail2", "", "box_body"])
def test_unknown_or_untyped_part_fails_without_mutation(invalid):
    state = _state()
    previous = deepcopy(state)
    with pytest.raises(ValueError):
        api.commit_operator_endcap_fw_value(state, invalid, 33, box_fw=25)
    assert state == previous


def test_legacy_saved_fw_state_without_mode_still_uses_original_engine_upgrade():
    state = {
        "head": {"follow_box": True, "value": 25},
        "tail": {"follow_box": True, "value": 25},
    }
    actual = deepcopy(state)
    expected = deepcopy(state)
    api.commit_operator_endcap_fw_value(actual, "head", "32", box_fw=25)
    owner.commit_endcap_fw(expected, "head", 32, box_fw=25)
    assert actual == expected
    assert actual["mode"] == api.FW_FOLLOW_HEAD


@pytest.mark.parametrize("source,bad_source", [
    ("z", "NaN"), ("head", float("nan")), ("tail", "bad"),
])
def test_main_gui_invalid_explicit_fw_does_not_touch_source_or_schedule(source, bad_source):
    state = _state()
    previous = deepcopy(state)
    gui, calls = _gui(
        state, box=bad_source if source == "z" else 25,
        head=bad_source if source == "head" else 31,
        tail=bad_source if source == "tail" else 36,
    )
    Phase6ApplicationHost.on_fw_selected(gui, source)
    assert state == previous
    assert calls == ["sync"]


def test_main_gui_valid_selections_follow_real_engine_state_machine():
    gui, calls = _gui()
    state = gui.endcap_fw_state
    assert Phase6ApplicationHost.on_fw_selected(gui, "head") is None
    assert state["mode"] == api.FW_FOLLOW_HEAD
    assert state["head"]["value"] == state["tail"]["value"] == 31.0
    assert Phase6ApplicationHost.on_fw_selected(gui, "tail") is None
    assert state["mode"] == api.FW_INDEPENDENT
    assert state["head"]["value"] == 31 and state["tail"]["value"] == 36
    assert Phase6ApplicationHost.on_fw_selected(gui, "z") is None
    assert state["mode"] == api.FW_FOLLOW_BODY
    assert state["head"]["value"] == state["tail"]["value"] == 25
    assert calls.count("sync") == 3
    assert calls.count(("invalidate", "geometry")) == 3
    assert calls.count(("update", "geometry")) == 3


def test_main_gui_invalid_staged_tail_does_not_partially_commit_or_invalidate():
    state = _state()
    state["tail"] = []
    previous = deepcopy(state)
    gui, calls = _gui(state=state, head="37.125")
    Phase6ApplicationHost.on_fw_selected(gui, "head")
    assert state == previous
    assert calls == ["sync"]


def test_main_gui_no_longer_invokes_unvalidated_legacy_mutating_fw_helpers():
    source = inspect.getsource(Phase6ApplicationHost.on_fw_selected)
    assert "manufacturing_api.commit_operator_box_fw_takeover(" in source
    assert "manufacturing_api.commit_operator_endcap_fw_value(" in source
    assert "commit_endcap_fw(" not in source
    assert "commit_box_fw(" not in source
    assert "float(var.get())" not in source
    assert "float(self.fw_z_var.get())" not in source
