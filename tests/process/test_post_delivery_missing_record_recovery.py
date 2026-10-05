from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tools.control_transaction import (
    POST_DELIVERY_RECOVERY_MODE,
    POST_DELIVERY_RECOVERY_PROOF_SCHEMA,
    ControlTransactionError,
    execute_transaction,
    is_post_delivery_recovery_finalize_record,
    prepare_transaction,
)
from tools.execution_record import (
    ActionSpec,
    ClosureState,
    ExecutionRecord,
    LeaseState,
)


def _record(*, trusted_source: str = "control_transaction_production_executor") -> ExecutionRecord:
    head = "b" * 40
    merged = "d" * 40
    proof = {
        "schema": POST_DELIVERY_RECOVERY_PROOF_SCHEMA,
        "kind": POST_DELIVERY_RECOVERY_MODE,
        "issue": 1197,
        "pr_number": 1205,
        "pr_head_ref": "refactor/issue1197-recovery",
        "pr_head_sha": head,
        "target_branch": "cleanup/2d-3d-sync",
        "observed_target_sha": merged,
        "merged_sha": merged,
        "merged_anchor_is_ancestor": True,
        "required_checks_green": True,
        "qa_history_reconstructed": False,
        "trusted_source": trusted_source,
    }
    return ExecutionRecord(
        issue=1197,
        execution_intent="POST_DELIVERY_RECOVERY",
        owner_kind="RECOVERY",
        owner_id="chatgpt.flowv2.work0",
        lane_id="chatgpt.flowv2.work0",
        slot_id="worker.slot.0",
        source_branch="refactor/issue1197-recovery",
        source_sha=head,
        work_branch="refactor/issue1197-recovery",
        head_sha=head,
        target_branch="cleanup/2d-3d-sync",
        target_sha=merged,
        state="INTEGRATING",
        semantic_state="POST_DELIVERY_RECOVERY_FINALIZATION",
        next_action=ActionSpec(
            kind="FINALIZE",
            args={"recovery_mode": POST_DELIVERY_RECOVERY_MODE, "pr_number": 1205},
            display="finalize recovered delivery",
        ),
        lease=LeaseState(
            token="lease-recovery",
            invocation_identity="interactive:recovery:1197",
            expires_at="2026-10-05T05:00:00Z",
        ),
        closure=ClosureState(
            merged_sha=merged,
            issue_closed=False,
            released_at=None,
        ),
        recovery_history=(proof,),
        generation=1,
        updated_at="2026-10-05T04:40:00Z",
    )


def test_recovery_finalize_uses_trusted_current_proof_without_reconstructing_qa():
    record = _record()
    assert record.qa.last_accepted_run is None
    assert record.qa.accepted_head_sha is None
    assert is_post_delivery_recovery_finalize_record(record) is True

    plan = prepare_transaction(
        record,
        kind="FINALIZE",
        transaction_id="tx-recovery-finalize",
        invocation_identity="interactive:recovery:1197",
    )
    done = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-10-05T04:41:00Z",
            "observed_target_sha": "d" * 40,
            "issue_closed": True,
            "issue_state": "closed",
            "issue_state_reason": "completed",
            "released_at": "2026-10-05T04:41:00Z",
        },
    )

    assert done.state == "DONE"
    assert done.qa.last_accepted_run is None
    assert done.qa.accepted_head_sha is None
    assert done.closure.merged_sha == "d" * 40
    assert done.closure.issue_closed is True
    assert done.owner_id == "NONE"


def test_recovery_finalize_fails_closed_when_trusted_proof_is_malformed():
    record = _record(trusted_source="caller-supplied")
    assert is_post_delivery_recovery_finalize_record(record) is False
    plan = prepare_transaction(
        record,
        kind="FINALIZE",
        transaction_id="tx-bad-recovery-finalize",
        invocation_identity="interactive:recovery:1197",
    )
    with pytest.raises(ControlTransactionError, match="accepted QA"):
        execute_transaction(
            record,
            plan,
            effect={
                "updated_at": "2026-10-05T04:41:00Z",
                "observed_target_sha": "d" * 40,
                "issue_closed": True,
                "issue_state": "closed",
                "issue_state_reason": "completed",
                "released_at": "2026-10-05T04:41:00Z",
            },
        )


def _fake_api(_repo, method, path, _token, payload=None):
    assert method == "GET"
    assert payload is None
    if path == "/pulls/1205":
        return {
            "number": 1205,
            "state": "closed",
            "merged": True,
            "body": "Delivery for the existing work.\n\nCloses #1197",
            "merge_commit_sha": "d" * 40,
            "head": {
                "ref": "refactor/issue1197-recovery",
                "sha": "b" * 40,
                "repo": {"full_name": "looaeedr/whd"},
            },
            "base": {"ref": "cleanup/2d-3d-sync"},
        }
    if path == "/issues/1197":
        return {"number": 1197, "state": "open"}
    raise AssertionError(path)


def test_trusted_builder_mints_only_current_recovery_evidence(monkeypatch):
    import tools.control_transaction_production_executor as executor

    monkeypatch.setattr(executor, "_api", _fake_api)
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda _repo, _token, _branch: "d" * 40,
    )
    monkeypatch.setattr(
        executor,
        "_required_checks_for_target",
        lambda _repo, _token, _branch: [
            "Governance Mirror Hard Gate",
            "WHD Product Regression",
        ],
    )
    monkeypatch.setattr(
        executor,
        "_check_conclusions_for_head",
        lambda _repo, _token, _head: {
            "Governance Mirror Hard Gate": "success",
            "WHD Product Regression": "success",
        },
    )
    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 5, 4, 40, tzinfo=timezone.utc),
    )

    record = executor._build_post_delivery_recovery_record(
        "looaeedr/whd",
        "token",
        issue=1197,
        lane_id="chatgpt.flowv2.work0",
        invocation_identity="interactive:recovery:1197",
        supplied_effect={"pr_number": 1205},
    )

    assert record.execution_intent == "POST_DELIVERY_RECOVERY"
    assert record.state == "INTEGRATING"
    assert record.next_action.kind == "FINALIZE"
    assert record.qa.last_accepted_run is None
    assert record.qa.accepted_head_sha is None
    assert record.recovery_history[0]["qa_history_reconstructed"] is False
    assert is_post_delivery_recovery_finalize_record(record) is True


def test_trusted_builder_rejects_non_green_required_check(monkeypatch):
    import tools.control_transaction_production_executor as executor

    monkeypatch.setattr(executor, "_api", _fake_api)
    monkeypatch.setattr(
        executor,
        "_read_branch_head",
        lambda _repo, _token, _branch: "d" * 40,
    )
    monkeypatch.setattr(
        executor,
        "_required_checks_for_target",
        lambda _repo, _token, _branch: ["WHD Product Regression"],
    )
    monkeypatch.setattr(
        executor,
        "_check_conclusions_for_head",
        lambda _repo, _token, _head: {"WHD Product Regression": "failure"},
    )

    with pytest.raises(executor.ProductionExecutorError, match="not GREEN"):
        executor._build_post_delivery_recovery_record(
            "looaeedr/whd",
            "token",
            issue=1197,
            lane_id="chatgpt.flowv2.work0",
            invocation_identity="interactive:recovery:1197",
            supplied_effect={"pr_number": 1205},
        )
