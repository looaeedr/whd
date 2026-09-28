import json

import pytest

from tools.execution_record import (
    ActionSpec,
    BlockerState,
    ChainState,
    ClosureState,
    ExecutionRecord,
    ExecutionRecordError,
    LeaseState,
    QAState,
    RunState,
    TransactionState,
    execution_record_fingerprint,
    execution_record_from_legacy,
    execution_record_from_payload,
    execution_record_to_payload,
    load_execution_record,
)


def _claim(**overrides):
    payload = {
        "issue": 844,
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "execution_intent": "SCHEDULER_LANE",
        "scheduler_lane": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "work_branch": "governance/issue844-unified-execution-record-20260928",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "phase": "IMPLEMENTING",
        "production_target": "cleanup/2d-3d-sync",
        "production_sha": "c" * 40,
        "slot_id": "UNBOUND",
        "next_action": "run focused GREEN",
        "master_issue": 842,
    }
    payload.update(overrides)
    return payload


def _checkpoint(**overrides):
    payload = {
        "version": 1,
        "issue": "844",
        "branch": "governance/issue844-unified-execution-record-20260928",
        "head_sha": "b" * 40,
        "state": "RUNNING",
        "next_action": "run focused GREEN",
        "run_id": None,
        "job_id": None,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": [],
        "operation": None,
        "master_issue": None,
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "chain_reason": None,
        "closure_state": "CLOSED",
        "closure_next_action": None,
        "last_accepted_run_id": None,
        "last_accepted_head_sha": None,
        "recovery_history": [],
    }
    payload.update(overrides)
    return payload


def _native_payload(**overrides):
    payload = {
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 7,
        "issue": 844,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER",
        "owner_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "lane_id": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "slot_id": None,
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "governance/issue844-unified-execution-record-20260928",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "ACTIVE",
        "semantic_state": "IMPLEMENTING",
        "next_action": {
            "kind": "RUN_TESTS",
            "args": {"nodeid": "tests/process/test_issue844_unified_execution_record.py"},
            "display": "run focused GREEN",
        },
        "lease": {
            "token": "lease-844-a",
            "invocation_identity": "scheduled:00:20260928T081600+0800",
            "expires_at": "2026-09-28T00:21:00Z",
        },
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": 842, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T00:16:00Z",
    }
    payload.update(overrides)
    return payload


def test_legacy_claim_and_checkpoint_project_to_one_execution_record():
    record = execution_record_from_legacy(_claim(), _checkpoint())

    assert record.issue == 844
    assert record.owner_id == "scheduler.6ab13fa557fc8191935c671214b865e2"
    assert record.work_branch == "governance/issue844-unified-execution-record-20260928"
    assert record.head_sha == "b" * 40
    assert record.target_branch == "cleanup/2d-3d-sync"
    assert record.target_sha == "c" * 40
    assert record.semantic_state == "RUNNING"
    assert record.next_action.display == "run focused GREEN"
    assert record.chain.parent_issue == 842


@pytest.mark.parametrize(
    ("claim_override", "checkpoint_override", "match"),
    [
        ({"issue": 845}, {}, "issue"),
        ({"work_branch": "wrong/branch"}, {}, "branch"),
        ({"head_sha": "d" * 40}, {}, "head"),
        ({"next_action": "different action"}, {}, "next_action"),
    ],
)
def test_legacy_projection_rejects_conflicting_identity_or_resume_meaning(
    claim_override, checkpoint_override, match
):
    with pytest.raises(ExecutionRecordError, match=match):
        execution_record_from_legacy(
            _claim(**claim_override),
            _checkpoint(**checkpoint_override),
        )


def test_legacy_projection_normalizes_unbound_slot_sentinel_to_none():
    record = execution_record_from_legacy(_claim(slot_id="UNBOUND"), _checkpoint())

    assert record.slot_id is None


def test_legacy_invocation_provenance_without_lease_fields_does_not_synthesize_lease():
    record = execution_record_from_legacy(
        _claim(invocation_identity="scheduled:00.20260928T0710+0800"),
        _checkpoint(),
    )

    assert record.lease is None


def test_legacy_projection_uses_explicit_execution_intent_lane_slot_and_lease():
    record = execution_record_from_legacy(
        _claim(
            execution_intent="SCHEDULER_LANE",
            slot_id="worker.slot.2",
            lease_token="lease-1",
            invocation_identity="scheduled:B15:abc",
            lease_expires_at="2026-09-28T00:30:00Z",
        ),
        _checkpoint(),
    )

    assert record.execution_intent == "SCHEDULER_LANE"
    assert record.owner_kind == "SCHEDULER"
    assert record.lane_id == "scheduler.6ab13fa557fc8191935c671214b865e2"
    assert record.slot_id == "worker.slot.2"
    assert record.lease == LeaseState(
        token="lease-1",
        invocation_identity="scheduled:B15:abc",
        expires_at="2026-09-28T00:30:00Z",
    )


def test_legacy_projection_does_not_infer_missing_execution_intent_from_prose():
    record = execution_record_from_legacy(
        _claim(execution_intent=None, next_action="please continue implementation carefully"),
        _checkpoint(next_action="please continue implementation carefully"),
    )

    assert record.execution_intent == "LEGACY_UNSPECIFIED"
    assert record.next_action.kind == "LEGACY_TEXT"
    assert record.next_action.display == "please continue implementation carefully"


def test_legacy_projection_carries_run_acceptance_transaction_and_recovery_history():
    record = execution_record_from_legacy(
        _claim(next_action="poll exact run"),
        _checkpoint(
            state="WAITING_REMOTE",
            next_action="poll exact run",
            run_id=36357957512,
            active_run_head_sha="b" * 40,
            active_run_purpose="FOCUSED_QA",
            operation={
                "id": "tx-844-1",
                "kind": "START_QA",
                "status": "APPLIED",
                "expected_fingerprint": "d" * 64,
            },
            last_accepted_run_id=36350000000,
            last_accepted_head_sha="9" * 40,
            recovery_history=[{"kind": "RECONCILE", "evidence": "branch-head-readback"}],
        ),
    )

    assert record.state == "VERIFYING"
    assert record.active_run == RunState(
        id=36357957512,
        head_sha="b" * 40,
        purpose="FOCUSED_QA",
        status=None,
    )
    assert record.transaction == TransactionState(
        id="tx-844-1",
        kind="START_QA",
        status="APPLIED",
        expected_fingerprint="d" * 64,
    )
    assert record.qa == QAState(
        last_accepted_run=36350000000,
        accepted_head_sha="9" * 40,
    )
    assert record.recovery_history == (
        {"kind": "RECONCILE", "evidence": "branch-head-readback"},
    )


def test_terminal_successor_projects_exact_next_issue_and_chain_action():
    record = execution_record_from_legacy(
        _claim(next_action=None),
        _checkpoint(
            state="TERMINAL_SUCCESS",
            next_action=None,
            chain_state="NEXT_CHILD_EXECUTABLE",
            next_issue=845,
            chain_next_action="claim exact successor #845",
            closure_state="CLOSED",
        ),
    )

    assert record.state == "INTEGRATING"
    assert record.next_action is None
    assert record.chain == ChainState(
        parent_issue=842,
        next_issue=845,
        next_action=ActionSpec(
            kind="LEGACY_TEXT",
            args={},
            display="claim exact successor #845",
        ),
    )


def test_native_v2_round_trip_and_fingerprint_are_stable_across_mapping_order():
    payload = _native_payload()
    record_a = execution_record_from_payload(payload)
    record_b = execution_record_from_payload(json.loads(json.dumps(payload, sort_keys=True)))

    assert execution_record_to_payload(record_a) == execution_record_to_payload(record_b)
    assert execution_record_fingerprint(record_a) == execution_record_fingerprint(record_b)
    assert len(execution_record_fingerprint(record_a)) == 64


def test_load_execution_record_reads_v2_file(tmp_path):
    path = tmp_path / "issue-844.json"
    path.write_text(json.dumps(_native_payload(), ensure_ascii=False), encoding="utf-8")

    record = load_execution_record(path)

    assert isinstance(record, ExecutionRecord)
    assert record.issue == 844
    assert record.next_action.kind == "RUN_TESTS"
    assert record.lease.token == "lease-844-a"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"state": "DONE", "next_action": {"kind": "RUN_TESTS", "args": {}, "display": "x"}}, "DONE"),
        ({"state": "BLOCKED", "blocker": None}, "BLOCKED"),
        ({"state": "ACTIVE", "blocker": {"kind": "EXTERNAL_DEPENDENCY", "evidence": "x", "recheck_after": None}}, "blocker"),
        ({"active_run": {"id": 1, "head_sha": "f" * 40, "purpose": "QA", "status": None}}, "active_run head"),
        ({"closure": {"merged_sha": None, "issue_closed": False, "released_at": "2026-09-28T00:20:00Z"}}, "released_at"),
        ({"chain": {"parent_issue": 842, "next_issue": None, "next_action": {"kind": "ACQUIRE", "args": {}, "display": "next"}}}, "chain next_action"),
        ({"lease": {"token": "x", "invocation_identity": "y", "expires_at": "not-a-time"}}, "expires_at"),
    ],
)
def test_native_v2_rejects_impossible_combinations(overrides, match):
    with pytest.raises(ExecutionRecordError, match=match):
        execution_record_from_payload(_native_payload(**overrides))


def test_blocked_record_requires_allowed_external_blocker_kind():
    payload = _native_payload(
        state="BLOCKED",
        next_action={"kind": "RECHECK_BLOCKER", "args": {}, "display": "recheck"},
        blocker={"kind": "MISSING_CAPABILITY", "evidence": "connector unavailable", "recheck_after": None},
        lease=None,
    )
    record = execution_record_from_payload(payload)

    assert record.blocker == BlockerState(
        kind="MISSING_CAPABILITY",
        evidence="connector unavailable",
        recheck_after=None,
    )


def test_done_record_requires_closed_and_released_closure():
    payload = _native_payload(
        state="DONE",
        next_action=None,
        lease=None,
        closure={
            "merged_sha": "e" * 40,
            "issue_closed": True,
            "released_at": "2026-09-28T00:20:00Z",
        },
    )
    record = execution_record_from_payload(payload)

    assert record.closure == ClosureState(
        merged_sha="e" * 40,
        issue_closed=True,
        released_at="2026-09-28T00:20:00Z",
    )
