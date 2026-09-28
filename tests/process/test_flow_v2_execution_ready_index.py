from dataclasses import replace

import pytest

from tools.execution_ready_index import (
    ReadyIndexError,
    build_ready_index,
    ready_index_to_payload,
    validate_ready_index,
)
from tools.execution_record import ActionSpec, execution_record_from_payload


def _record(issue: int, state: str, *, generation: int = 1, next_kind: str = "ACQUIRE"):
    if state == "DONE":
        next_action = None
    else:
        args = {}
        if next_kind == "APPLY_COMMIT":
            args = {"candidate_commit_sha": "d" * 40}
        elif next_kind == "START_QA":
            args = {"workflow": "qa-flow-v2"}
        elif next_kind == "WAIT_EXTERNAL":
            args = {"blocker_kind": "EXTERNAL_DEPENDENCY"}
        next_action = {
            "kind": next_kind,
            "args": args,
            "display": f"{next_kind.lower()} issue {issue}",
        }
    closure = (
        {"merged_sha": None, "issue_closed": True, "released_at": "2026-09-28T01:00:00Z"}
        if state == "DONE"
        else {"merged_sha": None, "issue_closed": False, "released_at": None}
    )
    blocker = (
        {"kind": "EXTERNAL_DEPENDENCY", "evidence": "waiting dependency", "recheck_after": None}
        if state == "BLOCKED"
        else None
    )
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": generation,
        "issue": issue,
        "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "UNCLAIMED" if state == "READY" else "SCHEDULER",
        "owner_id": "NONE" if state == "READY" else "scheduler.a",
        "lane_id": None if state == "READY" else "scheduler.a",
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
        "lease": None,
        "active_run": None,
        "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": blocker,
        "closure": closure,
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-28T00:50:00Z",
    })


def test_ready_index_contains_only_ready_records_and_exact_identity():
    ready = _record(900, "READY")
    active = _record(901, "ACTIVE", next_kind="APPLY_COMMIT")
    blocked = _record(902, "BLOCKED", next_kind="WAIT_EXTERNAL")
    done = _record(903, "DONE")

    index = build_ready_index([active, ready, done, blocked])

    assert [entry.issue for entry in index.entries] == [900]
    entry = index.entries[0]
    assert entry.generation == ready.generation
    assert entry.record_fingerprint
    assert entry.execution_intent == "SCHEDULER_LANE"
    assert entry.target_branch == "cleanup/2d-3d-sync"
    assert entry.target_sha == "c" * 40
    assert entry.next_action_kind == "ACQUIRE"
    assert entry.next_action_display == "acquire issue 900"


def test_ready_index_is_deterministic_across_input_order():
    a = _record(905, "READY")
    b = _record(904, "READY")

    first = ready_index_to_payload(build_ready_index([a, b]))
    second = ready_index_to_payload(build_ready_index([b, a]))

    assert first == second
    assert [row["issue"] for row in first["entries"]] == [904, 905]


def test_ready_index_source_digest_covers_non_ready_records_too():
    ready = _record(900, "READY")
    active = _record(901, "ACTIVE", generation=1, next_kind="APPLY_COMMIT")
    before = build_ready_index([ready, active])
    changed_active = replace(
        active,
        generation=2,
        next_action=ActionSpec(kind="START_QA", args={}, display="start qa"),
    )
    after = build_ready_index([ready, changed_active])

    assert before.entries == after.entries
    assert before.source_digest != after.source_digest


def test_validate_ready_index_detects_stale_cache():
    records = [_record(900, "READY"), _record(901, "ACTIVE", next_kind="APPLY_COMMIT")]
    index = build_ready_index(records)
    assert validate_ready_index(index, records) is True

    changed = [replace(records[0], generation=2), records[1]]
    assert validate_ready_index(index, changed) is False


def test_duplicate_issue_records_fail_closed():
    one = _record(900, "READY")
    duplicate = replace(one, generation=2)

    with pytest.raises(ReadyIndexError, match="duplicate issue"):
        build_ready_index([one, duplicate])


def test_ready_index_payload_is_cache_only_and_contains_no_claim_or_selection_result():
    payload = ready_index_to_payload(build_ready_index([_record(900, "READY")]))

    assert payload["schema"] == "WHD_EXECUTION_READY_INDEX_V1"
    assert payload["authority"] == "DERIVED_CACHE_ONLY"
    assert "selected_issue" not in payload
    assert "claim_owner" not in payload


def test_ready_index_rejects_non_executable_ready_action():
    broken = _record(910, "READY", next_kind="UNKNOWN")
    with pytest.raises(ReadyIndexError, match="non-executable next_action"):
        build_ready_index([broken])
