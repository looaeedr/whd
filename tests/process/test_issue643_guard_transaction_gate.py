from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

import tools.continuity_controller as continuity
import tools.execution_claim_guard as guard


H0 = "1" * 40
H1 = "2" * 40
CLAIM_BLOB = "3" * 40
BRANCH = "workorder/issue640-guard-turn-exit-helper-hardening-20260925"
ISSUE = 643
WORKER = "chatgpt.sol260925.issue640t3.a1"


def _api():
    classify = getattr(guard, "classify_guard_transaction", None)
    assert_clear = getattr(guard, "assert_pending_guard_transaction_clear", None)
    assert_consumable = getattr(guard, "assert_guard_receipt_consumable", None)
    state = getattr(guard, "GuardTransactionState", None)
    assert callable(classify), "P-R: canonical classify_guard_transaction is missing"
    assert callable(assert_clear), "P-R: assert_pending_guard_transaction_clear is missing"
    assert callable(assert_consumable), "P-R: assert_guard_receipt_consumable is missing"
    assert state is not None, "P-R: GuardTransactionState is missing"
    return classify, assert_clear, assert_consumable, state


def _receipt(*, run_id=1001, expires="2026-09-25T00:40:00Z", files=("a.txt",)):
    return {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "request_comment_id": run_id + 10000,
        "run_id": run_id,
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "action": "commit",
        "branch": BRANCH,
        "base_sha": H0,
        "head_sha": H0,
        "claim_blob_sha": CLAIM_BLOB,
        "guard_authority_sha": H0,
        "tested_target_sha": H0,
        "changed_files": list(files),
        "issued_at": "2026-09-25T00:00:00Z",
        "expires_at": expires,
    }


def _classify(*, receipts=None, readbacks=(), now="2026-09-25T00:10:00Z",
              claim_head=H0, live_head=H0, worker=WORKER,
              claim_blob=CLAIM_BLOB, expected_files=("a.txt",)):
    classify, _, _, _ = _api()
    return classify(
        receipts=list(receipts or [_receipt()]),
        current_issue=ISSUE,
        current_worker=worker,
        current_executor_source="chat",
        current_branch=BRANCH,
        current_claim_head_sha=claim_head,
        live_branch_head_sha=live_head,
        current_claim_blob_sha=claim_blob,
        now=datetime.fromisoformat(now.replace("Z", "+00:00")),
        durable_readbacks=list(readbacks),
        expected_changed_files=expected_files,
    )


def _commit_readback(*, run_id=1001, reconciled=False, files=("a.txt",)):
    return {
        "guard_run_id": run_id,
        "action": "commit",
        "mutation_applied": True,
        "reconciled": reconciled,
        "parent_sha": H0,
        "post_head_sha": H1,
        "changed_files": list(files),
        "committed_at": "2026-09-25T00:05:00Z",
    }


def _terminal_checkpoint():
    return continuity.Checkpoint(
        issue=str(ISSUE),
        branch=BRANCH,
        head_sha=H0,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        closure_state=continuity.ClosureState.CLOSED,
    )


def test_pr1_pending_green_rejects_new_guard_request():
    _, assert_clear, _, state = _api()
    decision = _classify()
    assert decision.state is state.PENDING
    with pytest.raises(guard.ExecutionClaimError, match="PENDING_GUARD_TRANSACTION_NOT_CONSUMED"):
        assert_clear(decision, operation="new_guard_request")


def test_pr2_pending_green_blocks_turn_exit():
    decision = _classify()
    with pytest.raises(continuity.TurnExitBlocked, match="UNCONSUMED_GREEN"):
        continuity.assert_turn_exitable(
            _terminal_checkpoint(),
            claim_state={"phase": "CLAIMED"},
            transaction_state=decision,
        )


def test_pr3_pending_green_rejects_heartbeat():
    _, assert_clear, _, _ = _api()
    with pytest.raises(guard.ExecutionClaimError, match="PENDING_GUARD_TRANSACTION_NOT_CONSUMED"):
        assert_clear(_classify(), operation="heartbeat")


def test_pr4_pending_green_rejects_other_issue_claim():
    _, assert_clear, _, _ = _api()
    with pytest.raises(guard.ExecutionClaimError, match="PENDING_GUARD_TRANSACTION_NOT_CONSUMED"):
        assert_clear(_classify(), operation="other_issue_claim")


def test_pr5_mutation_done_without_reconcile_is_reconcile_only():
    _, _, _, state = _api()
    decision = _classify(
        readbacks=[_commit_readback(reconciled=False)],
        live_head=H1,
    )
    assert decision.state is state.MUTATION_DONE_RECONCILE_ONLY
    assert decision.required_next_action == "RECONCILE_ONLY"


def test_pr6_expired_unconsumed_receipt_is_not_consumable():
    _, _, assert_consumable, state = _api()
    decision = _classify(now="2026-09-25T00:50:00Z")
    assert decision.state is state.EXPIRED_UNCONSUMED
    with pytest.raises(guard.ExecutionClaimError, match="EXPIRED_UNCONSUMED"):
        assert_consumable(decision, guard_run_id=1001)


def test_pr7_changed_file_mismatch_fails_closed():
    _, _, _, state = _api()
    decision = _classify(expected_files=("other.txt",))
    assert decision.state is state.AMBIGUOUS


def test_pr8_claim_worker_branch_head_or_blob_drift_fails_closed():
    _, _, _, state = _api()
    decision = _classify(worker="different.worker")
    assert decision.state is state.AMBIGUOUS
    decision = _classify(claim_blob="4" * 40)
    assert decision.state is state.AMBIGUOUS
    decision = _classify(claim_head="5" * 40)
    assert decision.state is state.AMBIGUOUS


def test_pr9_consumed_receipt_replay_is_rejected():
    _, _, assert_consumable, state = _api()
    decision = _classify(
        readbacks=[_commit_readback(reconciled=True)],
        live_head=H1,
    )
    assert decision.state is state.CONSUMED
    with pytest.raises(guard.ExecutionClaimError, match="CONSUMED|REPLAY"):
        assert_consumable(decision, guard_run_id=1001)


def test_pr10_two_valid_pending_green_receipts_are_ambiguous():
    _, _, _, state = _api()
    decision = _classify(receipts=[_receipt(run_id=1001), _receipt(run_id=1002)])
    assert decision.state is state.AMBIGUOUS


def test_pr11_scheduler_resume_points_to_pending_transaction_first():
    decision = _classify()
    assert decision.required_next_action == "CONSUME_GUARD_TRANSACTION"


def test_pr12_mutation_readback_and_reconciliation_is_consumed():
    _, _, _, state = _api()
    decision = _classify(
        readbacks=[_commit_readback(reconciled=True)],
        live_head=H1,
    )
    assert decision.state is state.CONSUMED


def test_pr13_expired_unconsumed_explicitly_blocks_turn_exit():
    decision = _classify(now="2026-09-25T00:50:00Z")
    with pytest.raises(continuity.TurnExitBlocked, match="EXPIRED_UNCONSUMED_GUARD"):
        continuity.assert_turn_exitable(
            _terminal_checkpoint(),
            claim_state={"phase": "CLAIMED"},
            transaction_state=decision,
        )


def test_pr14_expired_receipt_with_proven_mutation_becomes_reconcile_only():
    _, _, _, state = _api()
    decision = _classify(
        now="2026-09-25T00:50:00Z",
        readbacks=[_commit_readback(reconciled=False)],
        live_head=H1,
    )
    assert decision.state is state.MUTATION_DONE_RECONCILE_ONLY
    with pytest.raises(continuity.TurnExitBlocked, match="DURABLE_MUTATION_ALREADY_HAPPENED"):
        continuity.assert_turn_exitable(
            _terminal_checkpoint(),
            claim_state={"phase": "CLAIMED"},
            transaction_state=decision,
        )


REMOTE_GUARD_WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "whd-remote-execution-guard.yml"
)


def test_remote_guard_request_machine_gate_rejects_pending_and_allows_expired_recovery():
    assert_request = getattr(guard, "assert_remote_guard_request_permitted", None)
    assert callable(assert_request)

    with pytest.raises(
        guard.ExecutionClaimError,
        match="REMOTE_GUARD_REJECTED: PENDING_GUARD_TRANSACTION",
    ):
        assert_request(_classify())

    expired = _classify(now="2026-09-25T00:50:00Z")
    assert_request(expired)


def test_trusted_remote_guard_invokes_canonical_pending_transaction_gate():
    text = REMOTE_GUARD_WORKFLOW.read_text(encoding="utf-8")
    required = (
        "exact_remote_guard_receipts_from_comments",
        "classify_guard_transaction",
        "assert_remote_guard_request_permitted",
        "REMOTE_GUARD_RECONCILE_ONLY",
        "--checkpoint /tmp/execution-checkpoint.json",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"trusted Remote Guard is missing transaction gate tokens: {missing}"



def _write_terminal_cli_state(tmp_path):
    claim_path = tmp_path / "claim.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    claim_path.write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
                "worker": WORKER,
                "work_branch": BRANCH,
                "claimed_at": "2026-09-25T00:00:00Z",
                "base_sha": H0,
                "head_sha": H0,
                "phase": "GREEN",
                "delegated_branches": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    checkpoint_path.write_text(
        json.dumps(
            {
                "version": 1,
                "issue": str(ISSUE),
                "branch": BRANCH,
                "head_sha": H0,
                "state": "TERMINAL_SUCCESS",
                "next_action": None,
                "run_id": 123,
                "job_id": 456,
                "log_cursor": None,
                "blocked_count": 0,
                "blocked_last_notified_at": None,
                "evidence": ["accepted"],
                "closure_state": "FINALIZATION_PENDING",
                "closure_next_action": "advance closure",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return claim_path, checkpoint_path


@pytest.mark.parametrize(
    "changed_files",
    [
        (".dispatch/checkpoints/issue-643.json",),
        (
            ".dispatch/claims/issue-643.json",
            ".dispatch/checkpoints/issue-643.json",
        ),
    ],
)
def test_terminal_checkpoint_allows_exact_closure_coordination_write(
    tmp_path, changed_files
):
    claim_path, checkpoint_path = _write_terminal_cli_state(tmp_path)
    argv = [
        "--claim",
        str(claim_path),
        "--checkpoint",
        str(checkpoint_path),
        "--issue",
        str(ISSUE),
        "--worker",
        WORKER,
        "--branch",
        BRANCH,
        "--action",
        "write",
        "--base-sha",
        H0,
        "--head-sha",
        H0,
    ]
    for changed_file in changed_files:
        argv.extend(["--changed-file", changed_file])
    assert guard.main(argv) == 0


def test_terminal_checkpoint_still_rejects_general_repository_write(tmp_path):
    claim_path, checkpoint_path = _write_terminal_cli_state(tmp_path)
    rc = guard.main(
        [
            "--claim",
            str(claim_path),
            "--checkpoint",
            str(checkpoint_path),
            "--issue",
            str(ISSUE),
            "--worker",
            WORKER,
            "--branch",
            BRANCH,
            "--action",
            "write",
            "--base-sha",
            H0,
            "--head-sha",
            H0,
            "--changed-file",
            "tools/example.py",
        ]
    )
    assert rc == 2
