from __future__ import annotations

from datetime import datetime
from pathlib import Path

import tools.execution_claim_guard as guard


H0 = "1" * 40
H1 = "2" * 40
CLAIM_BLOB = "3" * 40
ISSUE = 731
WORKER = "chatgpt.sol260926.issue731.autoconsume1"
BRANCH = "governance/issue731-branch-create-auto-consume-20260926"


def _branch_create_receipt():
    return {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "request_comment_id": 1234,
        "run_id": 36250701375,
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "action": "branch-create",
        "branch": BRANCH,
        "base_sha": H0,
        "head_sha": H0,
        "claim_blob_sha": CLAIM_BLOB,
        "guard_authority_sha": H0,
        "tested_target_sha": H0,
        "changed_files": [],
        "issued_at": "2026-09-26T15:05:00Z",
        "expires_at": "2026-09-26T15:45:00Z",
    }


def test_issue731_exact_live_branch_readback_auto_consumes_branch_create_green():
    builder = getattr(guard, "durable_branch_create_readbacks_from_live_branch", None)
    assert callable(builder), "RED: canonical exact branch-create durable-readback builder is missing"

    receipt = _branch_create_receipt()
    readbacks = builder([receipt], live_branch_head_sha=H0)
    decision = guard.classify_guard_transaction(
        receipts=[receipt],
        current_issue=ISSUE,
        current_worker=WORKER,
        current_executor_source="chat",
        current_branch=BRANCH,
        current_claim_head_sha=H0,
        live_branch_head_sha=H0,
        current_claim_blob_sha=CLAIM_BLOB,
        now=datetime.fromisoformat("2026-09-26T15:10:00+00:00"),
        durable_readbacks=readbacks,
        expected_changed_files=(),
    )
    assert decision.state is guard.GuardTransactionState.CONSUMED


def test_issue731_wrong_live_head_does_not_auto_consume_branch_create_green():
    builder = getattr(guard, "durable_branch_create_readbacks_from_live_branch", None)
    assert callable(builder), "RED: canonical exact branch-create durable-readback builder is missing"

    receipt = _branch_create_receipt()
    assert builder([receipt], live_branch_head_sha=H1) == []


def test_issue731_trusted_workflow_wires_live_branch_readback_into_classifier():
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "whd-remote-execution-guard.yml"
    ).read_text(encoding="utf-8")
    required = (
        "durable_branch_create_readbacks_from_live_branch",
        "branch_create_readbacks =",
        "durable_readbacks=branch_create_readbacks",
    )
    missing = [token for token in required if token not in workflow]
    assert not missing, f"RED: trusted Guard is missing branch-create auto-consume wiring: {missing}"
