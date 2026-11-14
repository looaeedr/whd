"""#2517: main and Fold Designer FW edits use one headless Engine state machine."""
from copy import deepcopy
import inspect
import json
import math
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.endcap_factory_fold import commit_box_fw as original_commit
from gui_modules.application import lifecycle, state_sync


def _split_state(mode="INDEPENDENT"):
    return {
        "mode": mode,
        "head": {"follow_box": False, "value": 29.5},
        "tail": {"follow_box": False, "value": 31.0},
        "unrelated_source": {"persist": True},
    }


@pytest.mark.parametrize("mode", [
    "FOLLOW_BODY", "FOLLOW_HEAD", "FOLLOW_TAIL", "INDEPENDENT",
])
def test_engine_live_box_fw_change_replays_original_four_state_machine(mode):
    original = _split_state(mode)
    before = deepcopy(original)
    new_state = manufacturing_api.project_operator_box_fw_live_state(
        original, previous_box_fw=25.0, requested_box_fw="32.125",
    )
    expected = deepcopy(original)
    original_commit(expected, 32.125)
    assert new_state == expected
    assert new_state["mode"] == "FOLLOW_BODY"
    assert all(new_state[p] == {"follow_box": True, "value": 32.125}
               for p in ("head", "tail"))
    assert original == before
    assert new_state is not original
    assert ae_engine.project_operator_box_fw_live_state is (
        manufacturing_api.project_operator_box_fw_live_state
    )
    # Full saved FW state is independently reopened by the original Engine.
    reopened = manufacturing_api.normalize_endcap_fw_state({
        "fw": 32.125, "endcap_fw": json.loads(json.dumps(new_state)),
    })
    for part in ("head", "tail"):
        assert manufacturing_api.resolve_endcap_fw(
            {"fw": 32.125, "endcap_fw": reopened}, part, state=reopened,
        ) == 32.125


def test_no_change_does_not_steal_split_or_leader_from_endcaps():
    state = _split_state("FOLLOW_HEAD")
    prior = deepcopy(state)
    result = manufacturing_api.project_operator_box_fw_live_state(
        state, previous_box_fw=25, requested_box_fw=25.0,
    )
    assert result == prior
    assert state == prior
    result["head"]["value"] = 99.0
    assert state == prior


@pytest.mark.parametrize("invalid", [
    True, False, 0.0, -2.0, float("nan"), float("inf"), "-inf", "no-float",
])
def test_invalid_box_fw_rejects_without_mutating_source(invalid):
    source = _split_state()
    prior = deepcopy(source)
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.project_operator_box_fw_live_state(
            source, previous_box_fw=25.0, requested_box_fw=invalid,
        )
    assert source == prior


def test_bad_prior_box_fw_or_invalid_state_rejects_without_write():
    before = _split_state()
    for invalid_prior in (None, True, float("nan")):
        with pytest.raises(ValueError):
            manufacturing_api.project_operator_box_fw_live_state(
                before, previous_box_fw=invalid_prior, requested_box_fw=30,
            )
    with pytest.raises(ValueError, match="ENDCAP_FW_STATE_INVALID"):
        manufacturing_api.project_operator_box_fw_live_state(
            [], previous_box_fw=25, requested_box_fw=30,
        )
    assert before == _split_state()


class _Snapshot(dict):
    def as_dict(self):
        return dict(self)


class _Settings:
    def __init__(self, fw=25.0):
        self.values = {"fw": fw, "door_gap_w": 2.0}
        self.updates = []

    def snapshot(self):
        return _Snapshot(self.values)

    def update(self, values):
        self.updates.append(dict(values))
        for key, value in values.items():
            if key == "fw":
                self.values[key] = manufacturing_api.normalize_operator_source_dimension(
                    value, field="fw",
                )
            else:
                self.values[key] = float(value)
        return self.snapshot()


class _Scheduler:
    def __init__(self):
        self.ops = []

    def begin(self):
        self.ops.append("begin")

    def mark_dirty(self, key):
        self.ops.append(key)

    def end(self):
        self.ops.append("end")


class _Entry:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _host():
    calls = []
    scheduler = _Scheduler()
    host = SimpleNamespace(
        settings_service=_Settings(),
        endcap_fw_state=_split_state(),
        _settings_sync_guard=False,
        _phase6_update_scheduler=scheduler,
        fold_designer_app=None,
        _sync_endcap_fw_controls=lambda: calls.append("sync"),
        _setting_var_map=lambda: {},
    )
    return host, calls, scheduler


def test_main_gui_fw_edit_uses_public_engine_proposal_and_preserves_identity(monkeypatch):
    host, calls, scheduler = _host()
    original = deepcopy(host.endcap_fw_state)
    witnessed = []
    owner = manufacturing_api.project_operator_box_fw_live_state

    def spy(source, *, previous_box_fw, requested_box_fw):
        witnessed.append((deepcopy(source), previous_box_fw, requested_box_fw))
        return owner(
            source, previous_box_fw=previous_box_fw,
            requested_box_fw=requested_box_fw,
        )

    monkeypatch.setattr(manufacturing_api, "project_operator_box_fw_live_state", spy)
    state_sync.on_main_setting_var_changed(host, "fw", _Entry("35.5"))
    assert witnessed == [(original, 25.0, 35.5)]
    assert host.settings_service.snapshot()["fw"] == 35.5
    assert host.endcap_fw_state["mode"] == "FOLLOW_BODY"
    assert host.endcap_fw_state["head"]["value"] == 35.5
    assert host.endcap_fw_state["tail"]["value"] == 35.5
    assert calls == ["sync"]
    assert scheduler.ops == ["begin", "setting:fw", "end"]


def test_main_gui_invalid_fw_does_not_write_settings_or_endcap():
    host, calls, scheduler = _host()
    before = deepcopy(host.endcap_fw_state)
    state_sync.on_main_setting_var_changed(host, "fw", _Entry("nan"))
    assert host.settings_service.updates == []
    assert host.endcap_fw_state == before
    assert scheduler.ops == [] and calls == []


def test_fold_designer_fw_live_update_uses_same_engine_four_state_api():
    host, calls, scheduler = _host()
    lifecycle._apply_fold_designer_live_settings(host, {"fw": 36.75})
    assert host.settings_service.snapshot()["fw"] == 36.75
    assert host.endcap_fw_state["mode"] == "FOLLOW_BODY"
    assert host.endcap_fw_state["head"]["value"] == 36.75
    assert host.endcap_fw_state["tail"]["value"] == 36.75
    assert calls == ["sync"]
    assert scheduler.ops == ["begin", "settings", "end"]
    assert host._settings_sync_guard is False

    # Replaying an equal value must not steal a later Head/Tail split.
    host.endcap_fw_state = _split_state()
    old = host.endcap_fw_state
    lifecycle._apply_fold_designer_live_settings(host, {"fw": 36.75})
    assert host.endcap_fw_state is old
    assert host.endcap_fw_state["mode"] == "INDEPENDENT"


def test_fold_designer_bad_fw_isolated_from_unrelated_valid_fields():
    host, calls, scheduler = _host()
    old = deepcopy(host.endcap_fw_state)
    lifecycle._apply_fold_designer_live_settings(
        host, {"fw": float("nan"), "door_gap_w": 3.25},
    )
    assert host.settings_service.snapshot()["fw"] == 25.0
    assert host.settings_service.snapshot()["door_gap_w"] == 3.25
    assert host.endcap_fw_state == old
    assert calls == []
    assert scheduler.ops == ["begin", "settings", "end"]


def test_gui_no_longer_mutates_head_tail_fw_or_owns_four_state_logic():
    for function in (
        state_sync.on_main_setting_var_changed,
        lifecycle._apply_fold_designer_live_settings,
    ):
        code = inspect.getsource(function)
        assert "manufacturing_api.project_operator_box_fw_live_state(" in code
        assert 'for part in ("head", "tail")' not in code
        assert "endcap_fw_state.setdefault(" not in code
        assert '"follow_box"' not in code
    assert manufacturing_api.commit_box_fw is original_commit
