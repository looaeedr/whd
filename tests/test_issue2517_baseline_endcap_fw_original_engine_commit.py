"""#2517: Vault baseline Head/Tail FW authority belongs to the public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_endcap_settings_transactions as owner
from gui_modules.application import cabinet_controller as gui
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


class Var:
    def __init__(self, value):
        self.value = value
        self.writes = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes.append(value)


def state_in_mode(family, mode):
    state = api.normalize_endcap_fw_state({"model": family, "fw": 25})
    if mode in ("FOLLOW_HEAD", "INDEPENDENT"):
        api.commit_endcap_fw(state, "head", 33.125, box_fw=25)
    if mode in ("FOLLOW_TAIL", "INDEPENDENT"):
        api.commit_endcap_fw(state, "tail", 36.375, box_fw=25)
    assert state["mode"] == mode
    return state


def test_original_engine_function_is_public_and_gui_consumer_is_thin():
    assert api.commit_operator_baseline_endcap_fw is owner.commit_operator_baseline_endcap_fw
    assert ae_engine.commit_operator_baseline_endcap_fw is api.commit_operator_baseline_endcap_fw
    assert "commit_operator_baseline_endcap_fw" in ae_engine.__all__
    code = inspect.getsource(gui.on_baseline_changed)
    assert "manufacturing_api.commit_operator_baseline_endcap_fw(" in code
    assert 'state = self.endcap_fw_state.setdefault(' not in code
    assert 'bool(state.get("follow_box"' not in code


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("mode", [
    "FOLLOW_BODY", "FOLLOW_HEAD", "FOLLOW_TAIL", "INDEPENDENT",
])
def test_baseline_replay_preserves_engine_four_state_and_live_row_references(family, mode):
    state = state_in_mode(family, mode)
    original = deepcopy(state)
    refs = (state["head"], state["tail"])
    result = api.commit_operator_baseline_endcap_fw(state, "29.125")
    assert result is state
    assert (state["head"], state["tail"]) == (refs[0], refs[1])
    assert state["head"] is refs[0] and state["tail"] is refs[1]
    assert state["mode"] == mode
    if mode == "FOLLOW_BODY":
        expected = (29.125, 29.125)
    elif mode == "FOLLOW_HEAD":
        expected = (33.125, 33.125)
    elif mode == "FOLLOW_TAIL":
        expected = (36.375, 36.375)
    else:
        expected = (33.125, 36.375)
    actual = tuple(
        api.resolve_endcap_fw({"fw": 29.125, "endcap_fw": state}, part)
        for part in ("head", "tail")
    )
    assert actual == expected
    if mode != "FOLLOW_BODY":
        assert state["mode"] == original["mode"]


def test_legacy_serialized_false_and_independent_follower_are_decoded_before_readback():
    state = {
        "head": {"follow_box": "false", "value": "33.125"},
        "tail": {"follow_box": "true", "value": "stale-but-inactive"},
    }
    refs = (state["head"], state["tail"])
    api.commit_operator_baseline_endcap_fw(state, 29.125)
    assert state["head"] is refs[0] and state["tail"] is refs[1]
    assert state["head"] == {"follow_box": False, "value": "33.125"}
    assert state["tail"] == {"follow_box": True, "value": 29.125}
    assert "mode" not in state
    snapshot = {"fw": 29.125, "endcap_fw": state}
    assert api.resolve_endcap_fw(snapshot, "head") == 33.125
    assert api.resolve_endcap_fw(snapshot, "tail") == 29.125


def test_missing_legacy_endcap_is_seeded_only_by_engine():
    state = {"head": {"follow_box": False, "value": 33.125}}
    api.commit_operator_baseline_endcap_fw(state, 29.125)
    assert state["head"] == {"follow_box": False, "value": 33.125}
    assert state["tail"] == {"follow_box": True, "value": 29.125}


@pytest.mark.parametrize("bad", [True, False, None, "", 0, -1, "nan", float("nan"), float("inf")])
def test_invalid_new_baseline_fw_is_atomic(bad):
    state = state_in_mode("受電箱", "FOLLOW_HEAD")
    before = deepcopy(state)
    rows = (state["head"], state["tail"])
    with pytest.raises(ValueError):
        api.commit_operator_baseline_endcap_fw(state, bad)
    assert state == before
    assert state["head"] is rows[0] and state["tail"] is rows[1]


@pytest.mark.parametrize("field,bad", [
    ("follow_box", "not-a-bool"),
    ("follow_box", None),
    ("value", "NaN"),
    ("value", -5),
])
def test_late_corrupt_inactive_tail_rejected_without_partial_head_update(field, bad):
    state = state_in_mode("金庫型", "INDEPENDENT")
    state["tail"][field] = bad
    before = deepcopy(state)
    rows = (state["head"], state["tail"])
    with pytest.raises(ValueError):
        api.commit_operator_baseline_endcap_fw(state, 29.125)
    assert state == before
    assert state["head"] is rows[0] and state["tail"] is rows[1]


def _host(state):
    calls = []
    host = SimpleNamespace(
        baseline_var=Var("金庫型"),
        t_var=Var("2"),
        _fold_designer_baseline_commit_guard=False,
        _reset_manual_corner_parameter_locks=lambda: None,
        _derived_cache_owner=SimpleNamespace(invalidate=lambda *_: None),
        _apply_cabinet_family_for_current_model=lambda: None,
        _baseline_last_value="金庫型",
        _current_box_assembly_type=lambda: "INSERT_OVERLAY",
        box_assembly_type_var=None,
        cb_box_assembly=None,
        refresh_corner_type_panel=lambda: None,
        fold_designer_app=None,
        _current_cabinet_type_name=lambda: "金庫型",
        endcap_fw_state=state,
        _sync_endcap_fw_controls=lambda: calls.append("sync"),
        _request_phase6_update=lambda reason: calls.append(("update", reason)),
    )
    for name in (
        "yl1_var", "yr1_var", "ytop1_var", "ybottom1_var", "fw_z_var",
        "door_fold_l_var", "door_fold_r_var", "door_fold_t_var", "door_fold_b_var",
    ):
        setattr(host, name, Var("25" if name == "fw_z_var" else "original"))
    return host, calls


def _baseline(_model, *, thickness):
    assert thickness == "2"
    return {
        "endcap": {"yl1": 15., "yr1": 15., "ytop1": 16.,
                   "ybottom1": 15., "fw": 29.125},
        "door": None,
    }


def test_real_gui_event_keeps_head_led_fw_when_vault_baseline_is_reloaded(monkeypatch):
    state = state_in_mode("金庫型", "FOLLOW_HEAD")
    row_ref = state["head"]
    host, calls = _host(state)
    monkeypatch.setattr(api, "read_operator_baseline_fold_defaults", _baseline)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args: pytest.fail(str(args)))
    gui.on_baseline_changed(host)
    assert state["head"] is row_ref
    assert state["mode"] == "FOLLOW_HEAD"
    assert state["head"]["value"] == state["tail"]["value"] == 33.125
    assert host.fw_z_var.get() == "29.125"
    assert calls == ["sync", ("update", "baseline")]


def test_invalid_gui_fw_source_cannot_change_widgets_or_request_manufacturing(monkeypatch):
    state = state_in_mode("金庫型", "INDEPENDENT")
    state["tail"]["follow_box"] = "nonsense"
    before = deepcopy(state)
    host, calls = _host(state)
    errors = []
    monkeypatch.setattr(api, "read_operator_baseline_fold_defaults", _baseline)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args: errors.append(args))
    gui.on_baseline_changed(host)
    assert errors
    assert calls == []
    assert state == before
    assert host.fw_z_var.get() == "25"
    assert all(
        not getattr(host, name).writes for name in (
            "yl1_var", "yr1_var", "ytop1_var", "ybottom1_var", "fw_z_var",
        )
    )


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_committed_follow_and_independent_modes_replay_through_project_file(family, tmp_path):
    state = state_in_mode(family, "INDEPENDENT")
    api.commit_operator_baseline_endcap_fw(state, "29.125")
    snapshot = {
        "model": family, "w": 500, "h": 600, "d": 200, "t": 2,
        "fw": 29.125, "endcap_fw": state,
    }
    filename = write_project(
        tmp_path / f"baseline-follow-{family}",
        {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = read_project(filename)["snapshot"]
    assert restored["endcap_fw"]["mode"] == "INDEPENDENT"
    for part, expected in (("head", 33.125), ("tail", 36.375)):
        assert api.resolve_endcap_fw(restored, part) == expected
        assert api.build_endcap_xy_fold_profiles(restored, part_key=part)["Y"]
