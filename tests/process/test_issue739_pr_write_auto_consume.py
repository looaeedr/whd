from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import tools.execution_claim_guard as guard


H0 = "1" * 40
CLAIM_BLOB = "2" * 40
ISSUE = 739
WORKER = "chatgpt.sol260926.issue739.prauto1"
BRANCH = "governance/issue739-pr-write-auto-consume-20260926"
BASE_BRANCH = "cleanup/2d-3d-sync"


def _receipt():
    return {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "request_comment_id": 5847665929,
        "run_id": 36253656669,
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "action": "pr-write",
        "branch": BRANCH,
        "base_sha": H0,
        "head_sha": H0,
        "claim_blob_sha": CLAIM_BLOB,
        "guard_authority_sha": H0,
        "tested_target_sha": H0,
        "changed_files": [],
        "issued_at": "2026-09-26T15:56:16Z",
        "expires_at": "2026-09-26T16:36:16Z",
    }


def _pull(*, created_at="2026-09-26T15:56:20Z", merged_at=None, closed_at=None,
          head_sha=H0, head_ref=BRANCH, base_ref=BASE_BRANCH, number=734):
    return {
        "number": number,
        "state": "closed" if merged_at or closed_at else "open",
        "created_at": created_at,
        "updated_at": "2026-09-26T15:56:30Z",
        "closed_at": closed_at or merged_at,
        "merged_at": merged_at,
        "head": {"ref": head_ref, "sha": head_sha},
        "base": {"ref": base_ref},
    }


def _builder():
    builder = getattr(guard, "durable_pr_write_readbacks_from_live_pulls", None)
    assert callable(builder), "RED: exact pr-write durable-readback builder is missing"
    return builder


def test_issue739_create_event_inside_receipt_window_auto_consumes():
    receipt = _receipt()
    readbacks = _builder()(
        [receipt],
        live_pulls=[_pull(created_at="2026-09-26T15:56:20Z")],
        expected_base_branch=BASE_BRANCH,
    )
    decision = guard.classify_guard_transaction(
        receipts=[receipt],
        current_issue=ISSUE,
        current_worker=WORKER,
        current_executor_source="chat",
        current_branch=BRANCH,
        current_claim_head_sha=H0,
        live_branch_head_sha=H0,
        current_claim_blob_sha=CLAIM_BLOB,
        now=datetime.fromisoformat("2026-09-26T15:57:00+00:00"),
        durable_readbacks=readbacks,
        expected_changed_files=(),
    )
    assert decision.state is guard.GuardTransactionState.CONSUMED


def test_issue739_preexisting_pr_does_not_auto_consume_new_pr_write():
    receipt = _receipt()
    readbacks = _builder()(
        [receipt],
        live_pulls=[_pull(created_at="2026-09-26T15:00:00Z")],
        expected_base_branch=BASE_BRANCH,
    )
    assert readbacks == []


def test_issue739_merge_event_inside_receipt_window_proves_mutation():
    receipt = _receipt()
    readbacks = _builder()(
        [receipt],
        live_pulls=[_pull(
            created_at="2026-09-26T15:20:00Z",
            merged_at="2026-09-26T15:56:25Z",
        )],
        expected_base_branch=BASE_BRANCH,
    )
    assert len(readbacks) == 1
    assert readbacks[0]["mutation_applied"] is True
    assert readbacks[0]["reconciled"] is True
    assert readbacks[0]["pr_readback"] is True


@pytest.mark.parametrize(
    "pull",
    [
        _pull(head_sha="9" * 40),
        _pull(head_ref="other/branch"),
        _pull(base_ref="main"),
    ],
)
def test_issue739_wrong_pr_identity_stays_fail_closed(pull):
    assert _builder()(
        [_receipt()],
        live_pulls=[pull],
        expected_base_branch=BASE_BRANCH,
    ) == []


def test_issue739_ambiguous_matching_pr_events_fail_closed():
    with pytest.raises(guard.ExecutionClaimError, match="ambiguous|multiple|PR"):
        _builder()(
            [_receipt()],
            live_pulls=[
                _pull(number=734),
                _pull(number=740),
            ],
            expected_base_branch=BASE_BRANCH,
        )


def test_issue739_trusted_workflow_wires_live_pr_readback():
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "whd-remote-execution-guard.yml"
    ).read_text(encoding="utf-8")
    required = (
        "durable_pr_write_readbacks_from_live_pulls",
        "pr_write_readbacks =",
        "expected_base_branch=claim",
        "durable_readbacks=branch_create_readbacks + pr_write_readbacks",
    )
    missing = [token for token in required if token not in workflow]
    assert not missing, f"RED: trusted Guard missing pr-write durable readback wiring: {missing}"
