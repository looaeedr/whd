from dataclasses import replace

import pytest

from tools.execution_ready_index import build_ready_index
from tools.execution_record import ActionSpec, LeaseState, execution_record_from_payload
from tools.execution_scheduler_view import SchedulerViewError, build_scheduler_view


LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
NOW = "2026-09-28T02:00:00Z"


def _record(
    issue: int,
    state: str,
    *,
    lane: str | None = LANE_A,
    owner_kind: str | None = None,
    owner_id: str | None = None,
    lease: dict | None = None,
    execution_intent: str = "SCHEDULER_LANE",
):
    if owner_kind is None:
        owner_kind = "UNCLAIMED" if state == "READY" else "SCHEDULER"
    if owner_id is None:
        owner_id = "NONE" if state == "READY" else (lane or LANE_A)
    if state == "DONE":
        next_action = None
    elif state == "READY":
        next_action = {"kind": "ACQUIRE", "args": {}, "display": f"continue issue {issue}"}
    elif state == "VERIFYING":
        next_action = {"kind": "POLL_QA", "args": {"run_id": 36370000444, "head_sha": "b" * 40}, "display": f"continue issue {issue}"}
    elif state == "BLOCKED":
        next_action = {"kind": "WAIT_EXTERNAL", "args": {"blocker_kind": "EXTERNAL_DEPENDENCY"}, "display": f"continue issue {issue}"}
    else:
        next_action = {"kind": "APPLY_COMMIT", "args": {"candidate_commit_sha": "d" * 40}, "display": f"continue issue {issue}"}
    blocker = (
        {"kind": "EXTERNAL_DEPENDENCY", "evidence": "waiting external dependency", "recheck_after": None}
        if state == "BLOCKED"
        else None
    )
    closure = (
        {"merged_sha": None, "issue_closed": True, "released_at": "2026-09-28T01:30:00Z"}
        if state == "DONE"
        else {"merged_sha": None, "issue_closed": False, "released_at": None}
    )
    active_run = (
        {"id": 36370000444, "head_sha": "b" * 40, "purpose": "FLOW_V2_QA", "status": "in_progress"}
        if state == "VERIFYING"
        else None
    )
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 4,
        "issue": issue,
        "execution_intent": execution_intent,
        "owner_kind": owner_kind,
        "owner_id": owner_id,
        "lane_id": None if state == "READY" else lane,
        "slot_id": None,
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": f"work/issue-{issue}",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": state,
        "semantic_state": state,
        "next_action": next_action,
        "lease": lease,
        "active_run": active_run,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": blocker,
        "closure": closure,
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T01:50:00Z",
    })


def test_same_lane_nonterminal_has_priority_over_ready_candidates():
    current = _record(844, "ACTIVE")
    ready = _record(900, "READY")

    view = build_scheduler_view([ready, current], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert view.decision == "RESUME_CURRENT"
    assert view.current_issue == 844
    assert view.ready_issues == ()
    assert view.lease_status == "NONE"
    assert view.requires_transaction == "ACQUIRE"
    assert view.next_action_kind == "APPLY_COMMIT"


def test_same_invocation_lease_resumes_without_reacquire():
    current = _record(844, "ACTIVE", lease={
        "token": "lease-1",
        "invocation_identity": "scheduled:00:same",
        "expires_at": "2026-09-28T02:05:00Z",
    })

    view = build_scheduler_view([current], lane_id=LANE_A, invocation_identity="scheduled:00:same", now=NOW)

    assert view.decision == "RESUME_CURRENT"
    assert view.lease_status == "CURRENT_INVOCATION"
    assert view.requires_transaction is None


def test_other_live_invocation_lease_returns_lane_busy_not_no_work():
    current = _record(844, "VERIFYING", lease={
        "token": "lease-1",
        "invocation_identity": "scheduled:20:other",
        "expires_at": "2026-09-28T02:00:01Z",
    })

    view = build_scheduler_view([current], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert view.decision == "LANE_BUSY"
    assert view.current_issue == 844
    assert view.lease_status == "ACTIVE_OTHER_INVOCATION"
    assert view.active_run_id == 36370000444
    assert view.ready_issues == ()
    assert view.requires_transaction is None


def test_expired_other_invocation_lease_resumes_via_acquire_at_exact_boundary():
    current = _record(844, "ACTIVE", lease={
        "token": "lease-old",
        "invocation_identity": "scheduled:20:old",
        "expires_at": NOW,
    })

    view = build_scheduler_view([current], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert view.decision == "RESUME_CURRENT"
    assert view.lease_status == "EXPIRED"
    assert view.requires_transaction == "ACQUIRE"


def test_no_current_work_exposes_ready_candidates_without_selecting_a_winner():
    ready_b = _record(902, "READY")
    ready_a = _record(901, "READY")
    done = _record(844, "DONE")
    records = [ready_b, done, ready_a]
    index = build_ready_index(records)

    view = build_scheduler_view(
        records,
        lane_id=LANE_A,
        invocation_identity="scheduled:00:new",
        now=NOW,
        ready_index=index,
    )

    assert view.decision == "READY_CANDIDATES"
    assert view.current_issue is None
    assert view.ready_issues == (901, 902)
    assert view.selected_issue is None
    assert view.requires_transaction == "ACQUIRE"


def test_non_scheduler_ready_records_are_not_scheduler_candidates():
    update_only = _record(901, "READY", execution_intent="UPDATE_ONLY")

    view = build_scheduler_view([update_only], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert view.decision == "NO_EXECUTABLE_WORK"
    assert view.ready_issues == ()


def test_no_current_and_no_scheduler_ready_record_is_no_executable_work():
    done = _record(844, "DONE")
    foreign = _record(850, "ACTIVE", lane=LANE_B)

    view = build_scheduler_view([foreign, done], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert view.decision == "NO_EXECUTABLE_WORK"
    assert view.current_issue is None
    assert view.ready_issues == ()
    assert view.requires_transaction is None


def test_multiple_same_lane_nonterminal_records_fail_closed():
    first = _record(844, "ACTIVE")
    second = _record(845, "BLOCKED")

    with pytest.raises(SchedulerViewError, match="multiple same-lane"):
        build_scheduler_view([first, second], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)


def test_lane_owner_identity_mismatch_fails_closed_instead_of_false_no_work():
    broken = _record(844, "ACTIVE", lane=LANE_A, owner_id=LANE_B)

    with pytest.raises(SchedulerViewError, match="owner/lane identity mismatch"):
        build_scheduler_view([broken], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)


def test_stale_ready_index_fails_closed():
    ready = _record(901, "READY")
    index = build_ready_index([ready])
    changed = replace(ready, generation=5, next_action=ActionSpec(kind="ACQUIRE", args={}, display="changed"))

    with pytest.raises(SchedulerViewError, match="stale ready index"):
        build_scheduler_view([changed], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW, ready_index=index)


def test_input_order_does_not_change_ready_candidate_projection():
    a = _record(901, "READY")
    b = _record(902, "READY")

    one = build_scheduler_view([a, b], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)
    two = build_scheduler_view([b, a], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

    assert one == two
    assert one.ready_issues == (901, 902)


def test_scheduler_view_rejects_non_executable_same_lane_action():
    broken = replace(_record(999, state="ACTIVE", lane=LANE_A), next_action=ActionSpec(kind="UNKNOWN", args={}, display="bad"))
    with pytest.raises(SchedulerViewError, match="non-executable next_action"):
        build_scheduler_view([broken], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)
