from __future__ import annotations

from dataclasses import replace

import pytest

from tools.control_transaction import (
    ControlTransactionConflict,
    assert_mutation_writer_guard,
    build_mutation_writer_guard,
    prepare_transaction,
)
from tools.execution_record import ActionSpec, LeaseState, execution_record_from_payload

INV = "interactive:work1:issue1029:test"
LANE = "chatgpt.flowv2.work1"
HEAD = "a" * 40
TARGET = "b" * 40


def _record():
    return execution_record_from_payload({
        "schema":"WHD_EXECUTION_RECORD_V2","version":2,"generation":7,"issue":1029,
        "execution_intent":"EXECUTE_TICKET","owner_kind":"SCHEDULER","owner_id":LANE,
        "lane_id":LANE,"slot_id":"worker.slot.1","source_branch":"cleanup/2d-3d-sync",
        "source_sha":TARGET,"work_branch":"governance/issue1029-stale-plan-writer-guard",
        "head_sha":HEAD,"target_branch":"cleanup/2d-3d-sync","target_sha":TARGET,
        "state":"ACTIVE","semantic_state":"IMPLEMENTING",
        "next_action":{"kind":"APPLY_COMMIT","args":{},"display":"apply"},
        "lease":{"token":"lease-1029","invocation_identity":INV,"expires_at":"2099-09-29T16:00:00Z"},
        "active_run":None,"transaction":None,
        "mutation_scope":{"target_branch":"cleanup/2d-3d-sync","base_sha":TARGET,
            "write_paths":["tools/control_transaction.py"],"delete_paths":[],"reservation_state":"ACTIVE"},
        "qa":{"last_accepted_run":None,"accepted_head_sha":None},"blocker":None,
        "closure":{"merged_sha":None,"issue_closed":False,"released_at":None},
        "chain":{"parent_issue":None,"next_issue":None,"next_action":None},
        "recovery_history":[],"updated_at":"2026-09-29T15:50:00Z"
    })


def test_plan_binds_lease_token_and_next_action_and_stale_plan_dies():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx", invocation_identity=INV)
    assert plan.expected_lease_token == "lease-1029"
    assert plan.expected_next_action_kind == "APPLY_COMMIT"
    changed = replace(record, lease=LeaseState("lease-new", INV, "2099-09-29T16:05:00Z"))
    from tools.control_transaction import _assert_plan_matches
    with pytest.raises(ControlTransactionConflict, match="STALE_PLAN_MUST_DIE lease token drift"):
        _assert_plan_matches(changed, plan)


def test_writer_guard_binds_full_current_writer_identity():
    record = _record()
    guard = build_mutation_writer_guard(record, kind="APPLY_COMMIT", invocation_identity=INV)
    assert guard["generation"] == 7
    assert guard["lease_token"] == "lease-1029"
    assert guard["expected_next_action"] == "APPLY_COMMIT"
    assert guard["expected_work_head"] == HEAD
    assert guard["expected_target_head"] == TARGET
    assert_mutation_writer_guard(record, guard, kind="APPLY_COMMIT", invocation_identity=INV)


def test_writer_guard_dies_when_same_issue_advances_before_mutation():
    record = _record()
    guard = build_mutation_writer_guard(record, kind="APPLY_COMMIT", invocation_identity=INV)
    advanced = replace(record, generation=8, next_action=ActionSpec("START_QA", {}, "qa"))
    with pytest.raises(ControlTransactionConflict, match="STALE_PLAN_MUST_DIE"):
        assert_mutation_writer_guard(advanced, guard, kind="APPLY_COMMIT", invocation_identity=INV)


def test_ingress_rejects_live_work_head_advanced_by_another_writer(monkeypatch):
    import tools.control_transaction_request_ingress as ingress
    record = _record()
    guard = build_mutation_writer_guard(record, kind="APPLY_COMMIT", invocation_identity=INV)
    monkeypatch.setattr(ingress, "validate_git_unlock_receipt", lambda receipt: {
        "issue":1029,"generation":7,"record_fingerprint":guard["record_fingerprint"], "source_sha": TARGET, "target_branch": record.target_branch, "write_paths": list(record.mutation_scope.write_paths), "delete_paths": []
    })
    monkeypatch.setattr(ingress, "_read_branch_head", lambda repo, token, branch: TARGET if branch == record.target_branch else "d" * 40)
    request={
        "kind":"APPLY_COMMIT","invocation_identity":INV,
        "effect":{
            "head_sha":"c" * 40,
            "root_local_first_git_write_receipt":{},
            "mutation_writer_guard":guard,
        },
    }
    with pytest.raises(ControlTransactionConflict, match="ONE_ISSUE_ONE_MUTATION_WRITER"):
        ingress._validate_repository_content_git_write_receipt(
            request, execution_mode="INTERACTIVE", record=record, repo="looaeedr/whd", token="token"
        )


def test_ingress_rejects_live_target_drift_before_mutation(monkeypatch):
    import tools.control_transaction_request_ingress as ingress
    record = _record()
    guard = build_mutation_writer_guard(record, kind="APPLY_COMMIT", invocation_identity=INV)
    monkeypatch.setattr(ingress, "validate_git_unlock_receipt", lambda receipt: {
        "issue":1029,"generation":7,"record_fingerprint":guard["record_fingerprint"], "source_sha": TARGET, "target_branch": record.target_branch, "write_paths": list(record.mutation_scope.write_paths), "delete_paths": []
    })
    monkeypatch.setattr(ingress, "_read_branch_head", lambda repo, token, branch: "e" * 40 if branch == record.target_branch else "c" * 40)
    request={
        "kind":"APPLY_COMMIT","invocation_identity":INV,
        "effect":{
            "head_sha":"c" * 40,
            "root_local_first_git_write_receipt":{},
            "mutation_writer_guard":guard,
        },
    }
    with pytest.raises(ControlTransactionConflict, match="live target drift"):
        ingress._validate_repository_content_git_write_receipt(
            request, execution_mode="INTERACTIVE", record=record, repo="looaeedr/whd", token="token"
        )
