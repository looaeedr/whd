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




def test_native_v2_round_trip_and_fingerprint_are_stable_across_mapping_order():
    payload = _native_payload()
    record_a = execution_record_from_payload(payload)
    record_b = execution_record_from_payload(json.loads(json.dumps(payload, sort_keys=True)))


    assert execution_record_to_payload(record_a) == execution_record_to_payload(record_b)
    assert execution_record_fingerprint(record_a) == execution_record_fingerprint(record_b)
    assert len(execution_record_fingerprint(record_a)) == 64






def test_native_v2_payload_normalizes_unsorted_mutation_scope_paths():
    payload = _native_payload(
        mutation_scope={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["tests/z.py", "gui_modules/a.py", "tests/a.py"],
            "delete_paths": ["tests/old_z.py", "tests/old_a.py"],
            "reservation_state": "ACTIVE",
        }
    )


    record = execution_record_from_payload(payload)


    assert record.mutation_scope.write_paths == (
        "gui_modules/a.py",
        "tests/a.py",
        "tests/z.py",
    )
    assert record.mutation_scope.delete_paths == (
        "tests/old_a.py",
        "tests/old_z.py",
    )
    serialized = execution_record_to_payload(record)
    assert serialized["mutation_scope"]["write_paths"] == [
        "gui_modules/a.py",
        "tests/a.py",
        "tests/z.py",
    ]




def test_native_v2_payload_unsorted_compatibility_does_not_weaken_path_validation():
    payload = _native_payload(
        mutation_scope={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["tests/b.py", "tests/b.py"],
            "delete_paths": [],
            "reservation_state": "ACTIVE",
        }
    )


    with pytest.raises(ExecutionRecordError, match="duplicate paths"):
        execution_record_from_payload(payload)


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
        owner_kind="NONE",
        owner_id="NONE",
        lane_id=None,
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