"""#2517 Fold Designer -> Main GUI live revisions must be Engine-admitted.

The revision is a gate on canonical Settings, Corner, Joint and Workspace
mutations.  It does not change any physical geometry or publication schema.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.operator_settings_transactions import (
    OperatorFoldDesignerLiveRevisionPlan,
    plan_operator_fold_designer_live_revision as owner_plan,
)
from gui_modules.application import lifecycle


@pytest.mark.parametrize("raw,last", [
    (True, 0), (False, 0),
    (1.0, 0), (2.0, 1), (2.5, 1), (3.75, 1),
    (float("nan"), 0), (float("inf"), 0),
    ("2.5", 1), ("2_0", 1), ("0x2", 0),
    ("true", 0), ("nan", 0), ([], 0), ({}, 0), ((), 0),
    (b"2", 1),
])
def test_public_engine_denies_aliased_live_revisions_before_manufacturing(raw, last):
    plan = api.plan_operator_fold_designer_live_revision(raw, last_revision=last)
    assert isinstance(plan, OperatorFoldDesignerLiveRevisionPlan)
    assert (plan.accepted, plan.reason, plan.revision) == (
        False, "INVALID_REVISION", last,
    )


@pytest.mark.parametrize("raw,last,expected", [
    (2, 1, 2), ("2", 1, 2), (" 2 ", 1, 2),
    ("002", 1, 2), ("+2", 1, 2),
    (1, 0, 1), (3, "2", 3),
])
def test_valid_live_revisions_preserve_original_ascii_and_json_contract(
    raw, last, expected,
):
    plan = api.plan_operator_fold_designer_live_revision(raw, last_revision=last)
    assert plan == owner_plan(raw, last_revision=last)
    assert plan.accepted is True and plan.reason == "OK"
    assert plan.revision == expected
    assert ae_engine.plan_operator_fold_designer_live_revision is owner_plan
    assert api.plan_operator_fold_designer_live_revision is owner_plan
    assert ae_engine.OperatorFoldDesignerLiveRevisionPlan is OperatorFoldDesignerLiveRevisionPlan
    saved = json.loads(json.dumps({"origin": "fold_designer", "revision": expected}))
    assert api.plan_operator_fold_designer_live_revision(
        saved["revision"], last_revision=last,
    ).accepted


@pytest.mark.parametrize("raw,last", [
    (0, 0), (None, 0), ("", 0), ("  ", 0),
    (1, 1), ("1", 1), ("-1", 0), (2, 3),
])
def test_stale_or_empty_revision_keeps_previous_authority(raw, last):
    plan = api.plan_operator_fold_designer_live_revision(raw, last_revision=last)
    assert plan.accepted is False
    assert plan.reason == "STALE_REVISION"


@pytest.mark.parametrize("last", [
    True, False, 1.5, "1_0", float("nan"), [], {}, -1, "-1",
])
def test_corrupt_last_revision_never_authorizes_live_state(last):
    result = api.plan_operator_fold_designer_live_revision(20, last_revision=last)
    assert result.accepted is False
    assert result.reason == "INVALID_PREVIOUS_REVISION"


def _host():
    return SimpleNamespace(
        _phase6_last_fold_designer_revision=1,
        _phase6_last_fold_designer_fingerprint="committed",
        _phase6_last_fold_designer_live_payload={"source": "kept"},
        _fold_designer_live_sync_guard=False,
    )


@pytest.mark.parametrize("raw", [
    True, False, 1.5, 2.5, "2_0", "2.5", "invalid", None,
    0, 1, "1", [], {}, float("nan"),
])
def test_real_main_gui_live_receiver_rejects_before_any_side_effect(
    monkeypatch, raw,
):
    host = _host()
    original = deepcopy(vars(host))
    payload = {
        "origin": "fold_designer", "revision": raw,
        "fingerprint": "new-physical-snapshot",
        "model": "受電箱", "settings": {"w": 910.25},
        "workspace": {"existing_parts": ["box_body"]},
    }
    before_payload = deepcopy(payload)
    calls = []
    real = api.plan_operator_fold_designer_live_revision

    def tracked(value, *, last_revision):
        calls.append((value, last_revision))
        return real(value, last_revision=last_revision)

    monkeypatch.setattr(api, "plan_operator_fold_designer_live_revision", tracked)
    assert lifecycle._apply_fold_designer_live_snapshot(host, payload) is False
    assert calls == [(raw, 1)] or (
        len(calls) == 1
        and isinstance(raw, float) and raw != raw
        and calls[0][1] == 1
    )
    assert vars(host) == original
    assert payload == before_payload


def test_valid_ascii_revision_still_reaches_original_navigation_publish_path(monkeypatch):
    import phase6_sync_envelope

    monkeypatch.setattr(phase6_sync_envelope, "navigation_only_change",
                        lambda previous, current: True)
    events = []
    host = _host()
    host.workspace_controller = SimpleNamespace(
        set_active_part=lambda part: events.append(("active", part)),
    )
    host._sync_fold_designer_manual_corner_context = (
        lambda part: events.append(("corner", part))
    )
    host._compose_phase6_project_snapshot_from_main_gui = lambda: {"model": "金庫型"}
    host.project_controller = SimpleNamespace(
        capture_committed=lambda snapshot: events.append(("committed", snapshot))
    )
    payload = {
        "origin": "fold_designer", "revision": " 2 ",
        "fingerprint": "new-state", "active_part": "door",
    }
    assert lifecycle._apply_fold_designer_live_snapshot(host, payload) is True
    assert events == [
        ("active", "door"), ("corner", "door"),
        ("committed", {"model": "金庫型"}),
    ]
    assert host._phase6_last_fold_designer_revision == 2
    assert host._phase6_last_fold_designer_fingerprint == "new-state"
    assert host._phase6_last_fold_designer_live_payload == payload
    assert host._fold_designer_live_sync_guard is False
    assert lifecycle._apply_fold_designer_live_snapshot(host, payload) is False
    assert len(events) == 3


def test_gui_has_one_engine_revision_gate_and_no_int_coercion_before_it():
    source = inspect.getsource(lifecycle._apply_fold_designer_live_snapshot)
    assert "manufacturing_api.plan_operator_fold_designer_live_revision(" in source
    assert 'revision = int(payload.get("revision"' not in source
    assert '_phase6_last_fold_designer_revision", 0) or 0)' not in source
    assert source.index("plan_operator_fold_designer_live_revision(") < source.index(
        "self._fold_designer_live_sync_guard = True"
    )
    engine = inspect.getsource(owner_plan)
    assert "_external_sync_revision_number(" in engine
