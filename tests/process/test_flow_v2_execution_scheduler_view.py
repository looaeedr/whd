from dataclasses import replace

import pytest

from tools.execution_ready_index import build_ready_index
from tools.execution_record import ActionSpec, ChainState, LeaseState, execution_record_from_payload
from tools.execution_scheduler_view import (
    SchedulerViewError,
    build_scheduler_view,
    build_takeover_handoff_effect,
)


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
        owner_kind = "NONE" if state == "DONE" else "UNCLAIMED" if state == "READY" else "SCHEDULER"
    if owner_id is None:
        owner_id = "NONE" if state in {"READY", "DONE"} else (lane or LANE_A)
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
        "lane_id": None if state in {"READY", "DONE"} else lane,
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


def test_no_current_work_deterministically_selects_first_ready_issue():
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
    assert view.selected_issue == 901
    assert view.next_action_kind == "ACQUIRE"
    assert view.next_action_display == "Acquire Issue #901"
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
    assert one.selected_issue == 901


def test_scheduler_view_rejects_non_executable_same_lane_action():
    broken = replace(_record(999, state="ACTIVE", lane=LANE_A), next_action=ActionSpec(kind="UNKNOWN", args={}, display="bad"))
    with pytest.raises(SchedulerViewError, match="non-executable next_action"):
        build_scheduler_view([broken], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW)

def _runtime_observation(
    record,
    *,
    issue: int | None = None,
    state: str = "ENDED",
    observed_at: str = "2026-09-28T01:55:00Z",
):
    issue = record.issue if issue is None else issue
    if state == "LIVE":
        event = "PROGRESS"
        exit_at = None
        exit_state = None
        heartbeat_expires_at = "2026-09-28T02:05:00Z"
    elif state == "EXPIRED":
        event = "PROGRESS"
        exit_at = None
        exit_state = None
        heartbeat_expires_at = "2026-09-28T01:59:00Z"
    elif state == "ENDED":
        event = "EXIT"
        exit_at = observed_at
        exit_state = "ENDED"
        heartbeat_expires_at = "2026-09-28T01:59:00Z"
    else:
        raise AssertionError(state)
    return {
        "schema": "WHD_RUNTIME_OBSERVATION_V2",
        "version": 2,
        "authority": "NON_AUTHORITY",
        "source": "test-runtime",
        "handler": "test-runtime",
        "entrypoint": None,
        "event": event,
        "runtime_state": "ENDED" if state == "ENDED" else "WORKING",
        "issue": issue,
        "slot_id": record.slot_id,
        "claim_worker": record.owner_id,
        "owner_id": record.owner_id,
        "invocation_identity": "runtime.test.owner",
        "conversation_identity": None,
        "branch": record.work_branch,
        "head_sha": record.head_sha,
        "action": None,
        "record_fingerprint": None,
        "last_wake_at": None,
        "last_heartbeat_at": "2026-09-28T01:54:00Z",
        "heartbeat_expires_at": heartbeat_expires_at,
        "last_progress_at": "2026-09-28T01:54:00Z",
        "exit_at": exit_at,
        "exit_state": exit_state,
        "liveness_state": state,
        "observed_at": observed_at,
    }


def test_stranded_foreign_scheduler_work_is_taken_over_before_ready_candidates():
    stranded = _record(
        1080,
        "ACTIVE",
        lane="chatgpt.flowv2.work2",
        owner_kind="SCHEDULER",
        owner_id="chatgpt.flowv2.work2",
    )
    ready = _record(1200, "READY")
    owner_moved_on = _runtime_observation(stranded, issue=1143, state="ENDED")

    view = build_scheduler_view(
        [ready, stranded],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={"chatgpt.flowv2.work2": owner_moved_on},
    )

    assert view.decision == "TAKEOVER_CANDIDATE"
    assert view.selected_issue == 1080
    assert view.takeover_issues == (1080,)
    assert view.takeover_from_owner_id == "chatgpt.flowv2.work2"
    assert view.takeover_reason == (
        "STUCK_UNOWNED_FAMILY_CONFIRMED:OWNER_MOVED_TO_OTHER_ISSUE"
    )
    assert view.requires_transaction == "HANDOFF"
    assert view.next_action_kind == "APPLY_COMMIT"
    assert view.ready_issues == ()


def test_matching_live_runtime_blocks_takeover_and_ready_work_can_proceed():
    foreign = _record(1080, "ACTIVE", lane=LANE_B)
    ready = _record(1200, "READY")
    live = _runtime_observation(foreign, state="LIVE")

    view = build_scheduler_view(
        [foreign, ready],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={LANE_B: live},
    )

    assert view.decision == "READY_CANDIDATES"
    assert view.selected_issue == 1200
    assert view.takeover_issues == ()


def test_takeover_fails_closed_when_owner_runtime_was_not_fresh_read():
    foreign = _record(1080, "ACTIVE", lane=LANE_B)
    ready = _record(1200, "READY")

    view = build_scheduler_view(
        [foreign, ready],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={},
    )

    assert view.decision == "READY_CANDIDATES"
    assert view.selected_issue == 1200


def test_live_foreign_lease_blocks_takeover_even_if_runtime_ended():
    foreign = _record(
        1080,
        "ACTIVE",
        lane=LANE_B,
        lease={
            "token": "live-foreign",
            "invocation_identity": "scheduled:B15:live",
            "expires_at": "2026-09-28T02:05:00Z",
        },
    )

    view = build_scheduler_view(
        [foreign],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={LANE_B: _runtime_observation(foreign, state="ENDED")},
    )

    assert view.decision == "NO_EXECUTABLE_WORK"


def test_active_or_unknown_delegated_family_node_blocks_parent_takeover():
    parent = _record(
        1080,
        "ACTIVE",
        lane="chatgpt.flowv2.work2",
        owner_id="chatgpt.flowv2.work2",
    )
    child = replace(
        _record(
            1081,
            "ACTIVE",
            lane="chatgpt.flowv2.work3",
            owner_id="chatgpt.flowv2.work3",
        ),
        chain=ChainState(parent_issue=1080),
    )
    observations = {
        "chatgpt.flowv2.work2": _runtime_observation(parent, issue=1143, state="ENDED"),
        "chatgpt.flowv2.work3": _runtime_observation(child, state="LIVE"),
    }

    view = build_scheduler_view(
        [parent, child],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations=observations,
    )

    assert view.decision == "NO_EXECUTABLE_WORK"


def test_takeover_handoff_effect_changes_only_scheduler_owner_routing():
    stranded = _record(
        1080,
        "ACTIVE",
        lane="chatgpt.flowv2.work2",
        owner_id="chatgpt.flowv2.work2",
    )
    view = build_scheduler_view(
        [stranded],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={
            "chatgpt.flowv2.work2": _runtime_observation(
                stranded, issue=1143, state="ENDED"
            )
        },
    )

    assert build_takeover_handoff_effect(view) == {
        "owner_kind": "SCHEDULER",
        "owner_id": LANE_A,
        "lane_id": LANE_A,
    }

def test_same_lane_current_work_beats_foreign_takeover_candidate():
    current = _record(844, "ACTIVE", lane=LANE_A)
    stranded = _record(
        1080,
        "ACTIVE",
        lane="chatgpt.flowv2.work2",
        owner_id="chatgpt.flowv2.work2",
    )

    view = build_scheduler_view(
        [stranded, current],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={
            "chatgpt.flowv2.work2": _runtime_observation(
                stranded, issue=1143, state="ENDED"
            )
        },
    )

    assert view.decision == "RESUME_CURRENT"
    assert view.current_issue == 844


def test_legitimate_blocked_foreign_work_is_not_takeover_candidate():
    blocked = _record(
        1080,
        "BLOCKED",
        lane="chatgpt.flowv2.work2",
        owner_id="chatgpt.flowv2.work2",
    )

    view = build_scheduler_view(
        [blocked],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={
            "chatgpt.flowv2.work2": _runtime_observation(
                blocked, issue=1143, state="ENDED"
            )
        },
    )

    assert view.decision == "NO_EXECUTABLE_WORK"


def test_issue1080_shape_projects_takeover_before_new_work():
    stranded = replace(
        _record(
            1080,
            "ACTIVE",
            lane="chatgpt.flowv2.work2",
            owner_kind="SCHEDULER",
            owner_id="chatgpt.flowv2.work2",
        ),
        next_action=ActionSpec(
            kind="START_BRANCH",
            args={},
            display="Repair READY→ACQUIRE continuation then start exact-tested delivery branch",
        ),
        semantic_state="TARGET_RECONCILED_FOR_TAKEOVER",
    )
    ready = _record(1112, "READY")
    work2_latest = _runtime_observation(
        stranded,
        issue=1143,
        state="ENDED",
        observed_at="2026-09-28T01:58:00Z",
    )
    work2_latest["branch"] = "delivery/issue1143-docs-gen4"
    work2_latest["head_sha"] = "e" * 40

    view = build_scheduler_view(
        [ready, stranded],
        lane_id=LANE_A,
        invocation_identity="scheduled:A00:new",
        now=NOW,
        runtime_observations={"chatgpt.flowv2.work2": work2_latest},
    )

    assert view.decision == "TAKEOVER_CANDIDATE"
    assert view.selected_issue == 1080
    assert view.requires_transaction == "HANDOFF"
    assert view.next_action_kind == "START_BRANCH"

