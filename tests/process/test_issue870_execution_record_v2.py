import json

import pytest

from tools.execution_record import (
    ExecutionRecordError,
    execution_record_fingerprint,
    execution_record_from_legacy,
    execution_record_to_payload,
)


def _claim(**overrides):
    payload = {
        "issue": 870,
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "work_branch": "governance/issue870-unified-execution-record-20260928",
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
        "issue": "870",
        "branch": "governance/issue870-unified-execution-record-20260928",
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
    }
    payload.update(overrides)
    return payload


def test_legacy_claim_and_checkpoint_project_to_one_execution_record():
    record = execution_record_from_legacy(_claim(), _checkpoint())

    assert record.issue == 870
    assert record.owner == "scheduler.6ab13fa557fc8191935c671214b865e2"
    assert record.branch == "governance/issue870-unified-execution-record-20260928"
    assert record.head_sha == "b" * 40
    assert record.target_branch == "cleanup/2d-3d-sync"
    assert record.target_sha == "c" * 40
    assert record.semantic_state == "RUNNING"
    assert record.next_action == "run focused GREEN"
    assert record.parent_issue == 842


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


def test_projection_uses_checkpoint_as_semantic_state_and_exact_resume_action():
    record = execution_record_from_legacy(
        _claim(phase="REMOTE_QA", next_action="poll exact run"),
        _checkpoint(
            state="WAITING_REMOTE",
            next_action="poll exact run",
            run_id=36357957512,
        ),
    )

    assert record.semantic_state == "WAITING_REMOTE"
    assert record.next_action == "poll exact run"
    assert record.active_run == 36357957512


def test_serialization_and_fingerprint_are_stable_across_mapping_key_order():
    claim = _claim()
    checkpoint = _checkpoint()
    record_a = execution_record_from_legacy(claim, checkpoint)
    record_b = execution_record_from_legacy(
        json.loads(json.dumps(claim, sort_keys=True)),
        json.loads(json.dumps(checkpoint, sort_keys=True)),
    )

    assert execution_record_to_payload(record_a) == execution_record_to_payload(record_b)
    assert execution_record_fingerprint(record_a) == execution_record_fingerprint(record_b)