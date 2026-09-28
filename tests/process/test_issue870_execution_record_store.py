from dataclasses import replace
import json

import pytest

from tools.execution_record import (
    execution_record_fingerprint,
    execution_record_from_payload,
)
from tools.execution_record_store import (
    ExecutionStoreConflict,
    ExecutionStoreError,
    execution_record_relative_path,
    load_execution_records,
    load_record_file,
    write_execution_record_atomic,
)


def _record(issue=870, *, generation=1, state="ACTIVE"):
    ready = state == "READY"
    done = state == "DONE"
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": generation,
        "issue": issue,
        "execution_intent": "USER_EXPLICIT_MIGRATION",
        "owner_kind": "UNCLAIMED" if ready else "NONE" if done else "INTERACTIVE",
        "owner_id": "NONE" if ready or done else "chatgpt.flow-v2",
        "lane_id": None,
        "slot_id": None,
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": f"flow-v2/issue{issue}",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": state,
        "semantic_state": state,
        "next_action": None if done else (
            {"kind": "ACQUIRE", "args": {}, "display": "claim"}
            if ready
            else {
                "kind": "APPLY_COMMIT",
                "args": {"candidate_commit_sha": "d" * 40},
                "display": "apply",
            }
        ),
        "lease": None,
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {
            "merged_sha": None,
            "issue_closed": done,
            "released_at": "2026-09-28T03:00:00Z" if done else None,
        },
        "chain": {
            "parent_issue": 869,
            "next_issue": None,
            "next_action": None,
        },
        "recovery_history": [],
        "updated_at": "2026-09-28T02:00:00Z",
    })


def test_store_path_is_single_canonical_layout():
    assert (
        str(execution_record_relative_path(870))
        == ".dispatch/execution/issue-870.json"
    )


def test_create_update_and_readback_use_exact_fingerprint_cas(tmp_path):
    record = _record()
    created = write_execution_record_atomic(
        tmp_path, record, expected_fingerprint=None
    )
    assert created == execution_record_fingerprint(record)
    path = tmp_path / execution_record_relative_path(870)
    assert load_record_file(path) == record

    updated = replace(
        record,
        generation=2,
        semantic_state="GREEN",
        updated_at="2026-09-28T02:10:00Z",
    )
    new_fp = write_execution_record_atomic(
        tmp_path, updated, expected_fingerprint=created
    )
    assert new_fp == execution_record_fingerprint(updated)


def test_stale_or_missing_cas_is_rejected(tmp_path):
    record = _record()
    fp = write_execution_record_atomic(
        tmp_path, record, expected_fingerprint=None
    )
    updated = replace(
        record, generation=2, updated_at="2026-09-28T02:10:00Z"
    )
    with pytest.raises(ExecutionStoreConflict, match="fingerprint drift"):
        write_execution_record_atomic(
            tmp_path, updated, expected_fingerprint="f" * 64
        )
    with pytest.raises(ExecutionStoreConflict, match="already exists"):
        write_execution_record_atomic(
            tmp_path, updated, expected_fingerprint=None
        )
    with pytest.raises(ExecutionStoreConflict, match="missing"):
        write_execution_record_atomic(
            tmp_path, _record(871), expected_fingerprint=fp
        )


def test_filename_payload_issue_mismatch_fails_closed(tmp_path):
    path = tmp_path / execution_record_relative_path(870)
    path.parent.mkdir(parents=True)
    from tools.execution_record import execution_record_to_payload

    path.write_text(
        json.dumps(execution_record_to_payload(_record(871))),
        encoding="utf-8",
    )
    with pytest.raises(
        ExecutionStoreError, match="filename/payload issue mismatch"
    ):
        load_record_file(path)


def test_store_loads_records_sorted(tmp_path):
    for record in (_record(872), _record(870), _record(871)):
        write_execution_record_atomic(
            tmp_path, record, expected_fingerprint=None
        )
    assert [r.issue for r in load_execution_records(tmp_path)] == [
        870,
        871,
        872,
    ]
