from __future__ import annotations

from dataclasses import replace

import pytest

from tools.control_transaction import (
    ControlTransactionError,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_dispatch_ingress import plan_dispatch_ingress
from tools.scheduler_ready_ingress import (
    SchedulerIssueCandidateError,
    build_scheduler_dispatch_candidate,
)

LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
INV = "scheduled:A40:issue1080:control-only"


def _candidate():
    return build_scheduler_dispatch_candidate(
        {
            "issue_number": 1080,
            "state": "open",
            "user": {"login": "looaeedr"},
            "body": (
                "WHD_SCHEDULER_DISPATCH_REQUEST_V1\n"
                "lane=A\n"
                "completion=CONTROL_ONLY\n\n"
                "Scheduler live ingress smoke test"
            ),
            "created_at": "2026-10-01T06:29:38Z",
        },
        repository_owner="looaeedr",
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        target_branch="cleanup/2d-3d-sync",
        target_sha="a" * 40,
    )


def _ready_record():
    candidate = _candidate()
    return candidate, plan_dispatch_ingress(candidate.ingress_request).record


def _acquire(record):
    import tools.control_transaction_production_executor as executor

    effect = executor._normalize_effect(
        record,
        kind="ACQUIRE",
        lane_id=LANE_A,
        invocation_identity=INV,
        supplied={},
    )
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-1080-acquire",
        invocation_identity=INV,
    )
    return effect, execute_transaction(record, plan, effect=effect)


def test_control_only_marker_binds_durable_post_acquire_finalize_and_no_work_branch():
    candidate, record = _ready_record()

    assert candidate.completion == "CONTROL_ONLY"
    assert candidate.ingress_request.post_acquire.kind == "FINALIZE"
    assert candidate.ingress_request.post_acquire.args == {"completion_mode": "CONTROL_ONLY"}
    assert record.work_branch == record.source_branch
    assert record.next_action.kind == "ACQUIRE"
    assert record.next_action.args["post_acquire"] == {
        "kind": "FINALIZE",
        "args": {"completion_mode": "CONTROL_ONLY"},
        "display": "Finalize control-only scheduler work",
    }


def test_control_only_marker_rejects_unknown_completion_mode():
    with pytest.raises(SchedulerIssueCandidateError, match="completion"):
        build_scheduler_dispatch_candidate(
            {
                "issue_number": 1080,
                "state": "open",
                "user": {"login": "looaeedr"},
                "body": "WHD_SCHEDULER_DISPATCH_REQUEST_V1\nlane=A\ncompletion=LEGACY_HANDOFF\n",
            },
            repository_owner="looaeedr",
            source_branch="cleanup/2d-3d-sync",
            source_sha="a" * 40,
            target_branch="cleanup/2d-3d-sync",
            target_sha="a" * 40,
        )


def test_ready_acquire_uses_bound_continuation_without_caller_guessing():
    _, record = _ready_record()
    effect, active = _acquire(record)

    assert effect["next_action"] == record.next_action.args["post_acquire"]
    assert active.state == "ACTIVE"
    assert active.next_action.kind == "FINALIZE"
    assert active.next_action.args == {"completion_mode": "CONTROL_ONLY"}
    assert active.work_branch == active.source_branch
    assert active.mutation_scope is None


def test_bound_control_only_continuation_rejects_caller_override():
    import tools.control_transaction_production_executor as executor

    _, record = _ready_record()
    with pytest.raises(executor.ProductionExecutorError, match="bound post-acquire"):
        executor._normalize_effect(
            record,
            kind="ACQUIRE",
            lane_id=LANE_A,
            invocation_identity=INV,
            supplied={
                "next_action": {
                    "kind": "START_BRANCH",
                    "args": {},
                    "display": "legacy branch path",
                }
            },
        )


def test_control_only_finalize_closes_without_fake_qa_or_merge_and_tracks_fresh_target():
    _, ready = _ready_record()
    _, active = _acquire(ready)
    plan = prepare_transaction(
        active,
        kind="FINALIZE",
        transaction_id="tx-1080-finalize",
        invocation_identity=INV,
    )
    done = execute_transaction(
        active,
        plan,
        effect={
            "updated_at": "2026-10-04T10:00:00Z",
            "observed_target_sha": "d" * 40,
            "control_only_target_readback": {
                "schema": "WHD_FLOW_V2_CONTROL_ONLY_TARGET_READBACK_V1",
                "target_branch": "cleanup/2d-3d-sync",
                "observed_target_sha": "d" * 40,
                "fresh_readback": True,
                "trusted_source": "control_transaction_production_executor",
            },
            "issue_closed": True,
            "issue_state": "closed",
            "issue_state_reason": "completed",
            "released_at": "2026-10-04T10:00:00Z",
        },
    )

    assert done.state == "DONE"
    assert done.closure.issue_closed is True
    assert done.closure.merged_sha is None
    assert done.qa.last_accepted_run is None
    assert done.target_sha == "d" * 40
    assert done.owner_kind == "NONE"
    assert done.lane_id is None


def test_control_only_finalize_fails_closed_if_content_identity_changed():
    _, ready = _ready_record()
    _, active = _acquire(ready)
    changed = replace(active, head_sha="b" * 40)
    plan = prepare_transaction(
        changed,
        kind="FINALIZE",
        transaction_id="tx-1080-finalize-changed",
        invocation_identity=INV,
    )
    with pytest.raises(ControlTransactionError, match="CONTROL_ONLY|control-only|INTEGRATING"):
        execute_transaction(
            changed,
            plan,
            effect={
                "updated_at": "2026-10-04T10:00:00Z",
                "observed_target_sha": "d" * 40,
                "issue_closed": True,
                "issue_state": "closed",
                "issue_state_reason": "completed",
                "released_at": "2026-10-04T10:00:00Z",
            },
        )


def test_trusted_control_only_finalize_closes_issue_after_fresh_target_readback(monkeypatch):
    import tools.control_transaction_production_executor as executor

    _, ready = _ready_record()
    _, active = _acquire(ready)
    monkeypatch.setattr(executor, "_read_branch_head", lambda *args, **kwargs: "e" * 40)

    calls = []

    def fake_api(repo, method, path, token, payload=None):
        calls.append((method, path, payload))
        if method == "GET" and path == "/issues/1080" and len([c for c in calls if c[:2] == ("GET", "/issues/1080")]) == 1:
            return {"state": "open", "state_reason": None, "closed_at": None}
        if method == "PATCH" and path == "/issues/1080":
            return {"state": "closed", "state_reason": "completed"}
        if method == "GET" and path == "/issues/1080":
            return {
                "state": "closed",
                "state_reason": "completed",
                "closed_at": "2026-10-04T10:00:00Z",
            }
        raise AssertionError((method, path, payload))

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._ensure_issue_closed_for_finalize(
        "looaeedr/whd",
        "token",
        issue=1080,
        record=active,
    )

    assert effect["observed_target_sha"] == "e" * 40
    assert effect["issue_closed"] is True
    assert ("PATCH", "/issues/1080", {"state": "closed", "state_reason": "completed"}) in calls
