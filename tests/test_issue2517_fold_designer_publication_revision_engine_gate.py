"""#2517 Fold Designer outgoing live revision and force flags belong to Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.operator_settings_transactions import (
    OperatorFoldDesignerPublicationRevisions,
    project_operator_fold_designer_publication_revisions as owner,
)
import phase6_sync_envelope as envelope
from gui_modules.application import fold_designer_composition_state as gui


def _publication(*, current_revision=3, force=False, host_relief_present=True,
                 current_state=None, previous_state=None,
                 previous_fingerprint=None, host_relief=None):
    previous = (
        {"settings": {"w": 600.25}, "assembly_relief": {}}
        if previous_state is None else previous_state
    )
    state = (
        {"settings": {"w": 640.5}, "assembly_relief": {}}
        if current_state is None else current_state
    )
    return envelope.plan_live_sync_envelope(
        current_state=state,
        previous_state=previous,
        previous_fingerprint=(
            envelope.stable_fingerprint(previous)
            if previous_fingerprint is None else previous_fingerprint
        ),
        current_revision=current_revision,
        active_transaction_id="",
        host_relief_present=host_relief_present,
        host_relief={} if host_relief is None else host_relief,
        force=force,
    )


@pytest.mark.parametrize("raw", [
    True, False, 1.0, 2.0, 3.25, float("nan"), float("inf"),
    "2_0", "2.5", "0x2", "nan", "bad", [], {}, (),
    b"2", -1, "-1",
])
def test_engine_rejects_invalid_original_publication_counter(raw):
    with pytest.raises(ValueError):
        api.project_operator_fold_designer_publication_revisions(raw)


@pytest.mark.parametrize("raw,current", [
    (None, 0), ("", 0), ("   ", 0), (0, 0),
    (1, 1), ("2", 2), (" 2 ", 2), ("+2", 2), ("002", 2),
])
def test_public_engine_counter_preserves_valid_serialized_source(raw, current):
    projected = api.project_operator_fold_designer_publication_revisions(raw)
    assert projected == owner(raw)
    assert projected == OperatorFoldDesignerPublicationRevisions(current, current + 1)
    assert ae_engine.project_operator_fold_designer_publication_revisions is owner
    assert ae_engine.OperatorFoldDesignerPublicationRevisions is OperatorFoldDesignerPublicationRevisions
    assert projected.next_revision == current + 1


@pytest.mark.parametrize("raw", [
    True, 2.5, "1_0", float("nan"), -1, [], {},
])
def test_publication_rejects_raw_counter_before_any_fingerprint_or_delta(monkeypatch, raw):
    monkeypatch.setattr(
        envelope, "stable_fingerprint",
        lambda *_: pytest.fail("invalid revision must stop before state fingerprint"),
    )
    with pytest.raises(ValueError):
        envelope.plan_live_sync_envelope(
            current_state={"settings": {"w": 640.5}},
            previous_state={},
            previous_fingerprint=None, current_revision=raw,
            active_transaction_id="", host_relief_present=True,
            host_relief={}, force=False,
        )


def test_valid_fractional_settings_publish_as_once_and_keep_json_revision():
    plan = _publication(current_revision=" 3 ")
    assert plan.should_publish is True
    assert plan.next_revision == 4
    assert plan.transaction_id == "fold_designer:4"
    assert plan.payload["revision"] == 4
    assert plan.payload["settings"]["w"] == 640.5
    published = json.loads(json.dumps(envelope.materialize_sync_value(plan.payload)))
    assert published["revision"] == 4
    prior = deepcopy(published)
    no_echo = _publication(
        current_revision=4,
        current_state=published,
        previous_state=published,
        previous_fingerprint=envelope.stable_fingerprint(published),
    )
    assert no_echo.should_publish is False
    assert no_echo.next_revision == 4
    assert prior == published


@pytest.mark.parametrize("flag", [
    "maybe", None, 2, 1.5, [], {},
])
@pytest.mark.parametrize("field", ["force", "host_relief_present"])
def test_corrupt_publication_boolean_is_denied_before_state_fingerprint(
    monkeypatch, flag, field,
):
    monkeypatch.setattr(
        envelope, "stable_fingerprint",
        lambda *_: pytest.fail("invalid boolean must stop before fingerprint"),
    )
    kwargs = {"force": False, "host_relief_present": True}
    kwargs[field] = flag
    with pytest.raises(ValueError, match="布林值"):
        envelope.plan_live_sync_envelope(
            current_state={"settings": {"w": 640.5}},
            previous_state={},
            previous_fingerprint=None,
            current_revision=1,
            active_transaction_id="", host_relief={},
            **kwargs,
        )


@pytest.mark.parametrize("force,host_present,expected_publish", [
    ("false", True, False),
    ("true", "false", False),
    ("true", "true", True),
    (False, True, False),
    (True, True, True),
])
def test_serialized_live_force_respects_engine_boolean_semantics(
    force, host_present, expected_publish,
):
    current = {
        "settings": {"w": 640.5},
        "assembly_relief": {"enabled": True, "parts": {"door": {}}},
    }
    stale_host = {"enabled": False, "parts": {}}
    plan = _publication(
        current_revision=5,
        current_state=current,
        previous_state=current,
        previous_fingerprint=envelope.stable_fingerprint(current),
        host_relief=stale_host,
        force=force,
        host_relief_present=host_present,
    )
    assert plan.should_publish is expected_publish
    assert plan.next_revision == (6 if expected_publish else 5)


def _host_with_revision(raw):
    sent = []
    source = {"settings": {"w": 640.5}, "assembly_relief": {}}
    app = SimpleNamespace(
        _live_sync_callback=lambda item: sent.append(deepcopy(item)),
        _phase6_live_sync_guard=False,
        _phase6_initializing=False,
        _phase6_sync_ready=True,
        _phase6_sync_revision=raw,
        _phase6_input_snapshot=deepcopy(source),
        _phase6_last_live_state={"settings": {"w": 600}, "assembly_relief": {}},
        _phase6_last_live_fingerprint="previous",
        baseline_model_var=object(),
        designer_workspace=object(),
    )
    host = SimpleNamespace(app=app, corner_transaction_payload=lambda _: deepcopy(source))
    return host, sent


@pytest.mark.parametrize("raw", [
    True, 2.5, "1_0", float("inf"),
])
def test_real_fold_designer_publisher_cannot_send_false_revision(raw):
    host, sent = _host_with_revision(raw)
    before = deepcopy({
        "revision": host.app._phase6_sync_revision,
        "input": host.app._phase6_input_snapshot,
        "live_state": host.app._phase6_last_live_state,
        "fingerprint": host.app._phase6_last_live_fingerprint,
    })
    with pytest.raises(ValueError):
        gui.publish_live_state(host, None)
    assert sent == []
    assert host.app._phase6_live_sync_guard is False
    assert host.app._phase6_sync_revision == before["revision"]
    assert host.app._phase6_input_snapshot == before["input"]
    assert host.app._phase6_last_live_state == before["live_state"]
    assert host.app._phase6_last_live_fingerprint == before["fingerprint"]


def test_real_publisher_preserves_raw_false_force_until_engine_verification():
    host, sent = _host_with_revision("3")
    source = host.corner_transaction_payload(None)
    # Use an explicit existing Relief flag transition: the legacy generic
    # mapping delta does not represent deleted keys in an empty mapping.
    # That separate behavior is outside this revision/force source gate.
    source["assembly_relief"] = {"enabled": False, "parts": {}}
    host.corner_transaction_payload = lambda _: deepcopy(source)
    host.app._phase6_last_live_state = deepcopy(source)
    host.app._phase6_last_live_fingerprint = envelope.stable_fingerprint(source)
    host.app._phase6_input_snapshot["assembly_relief"] = {
        "enabled": True, "parts": {},
    }
    assert gui.publish_live_state(host, None, force="false") is False
    assert sent == []
    assert host.app._phase6_sync_revision == "3"
    assert gui.publish_live_state(host, None, force="true") is True
    assert len(sent) == 1
    assert sent[0]["revision"] == 4
    assert host.app._phase6_sync_revision == 4
    assert gui.publish_live_state(host, None, force="false") is False
    assert len(sent) == 1


def test_publication_dto_cannot_coerce_bool_or_fractional_revision():
    data = dict(
        should_publish=False, transaction_id="", delta={}, fingerprint="",
        payload=None, host_relief_repair={},
    )
    for bad in (True, 1.5, "1_0", -1):
        with pytest.raises(ValueError):
            envelope.LiveSyncPublicationPlan(next_revision=bad, **data)


def test_no_presentation_layer_integer_or_boolean_source_coercion():
    planner_source = inspect.getsource(envelope.plan_live_sync_envelope)
    publisher_source = inspect.getsource(gui.publish_live_state)
    dto_source = inspect.getsource(envelope.LiveSyncPublicationPlan.__post_init__)
    assert "manufacturing_api.project_operator_fold_designer_publication_revisions(" in planner_source
    assert "manufacturing_api.normalize_operator_settings_boolean(" in planner_source
    assert "current_revision = int(" not in planner_source
    assert "next_revision = current_revision + 1" not in planner_source
    assert "force=bool(force)" not in publisher_source
    assert 'int(self.next_revision)' not in dto_source
