from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

import tools.execution_claim_guard as guard


H0 = "1" * 40
CLAIM_BLOB = "2" * 40
CLAIM_AFTER = "3" * 40
CHECKPOINT_AFTER = "4" * 40
COMMIT_SHA = "5" * 40
ISSUE = 733
WORKER = "chatgpt.sol260926.issue733.parity1"
BRANCH = "governance/issue733-branch-create-auto-consume-cleanup-parity-20260926"
CLAIM_PATH = f".dispatch/claims/issue-{ISSUE}.json"
CHECKPOINT_PATH = f".dispatch/checkpoints/issue-{ISSUE}.json"


def _receipt(*, changed_files=(CHECKPOINT_PATH,)):
    return {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "request_comment_id": 5848004191,
        "run_id": 36256476555,
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "action": "write",
        "branch": BRANCH,
        "base_sha": H0,
        "head_sha": H0,
        "claim_blob_sha": CLAIM_BLOB,
        "guard_authority_sha": H0,
        "tested_target_sha": H0,
        "changed_files": list(changed_files),
        "issued_at": "2026-09-26T16:43:40Z",
        "expires_at": "2026-09-26T17:23:40Z",
    }


def _checkpoint_payload(**overrides):
    payload = {
        "version": 1,
        "issue": str(ISSUE),
        "branch": BRANCH,
        "head_sha": H0,
        "state": "TERMINAL_SUCCESS",
        "next_action": None,
        "closure_state": "ISSUE_CLOSE_PENDING",
        "closure_next_action": "run bound finalization proof",
    }
    payload.update(overrides)
    return payload


def _claim_payload(**overrides):
    payload = {
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "work_branch": BRANCH,
        "head_sha": H0,
        "phase": "CLOSING",
    }
    payload.update(overrides)
    return payload


def _commit(*, changed_files=(CHECKPOINT_PATH,), committed_at="2026-09-26T16:44:00Z",
            claim_payload=None, checkpoint_payload=None):
    targets = {}
    if CLAIM_PATH in changed_files:
        targets[CLAIM_PATH] = {
            "blob_sha": CLAIM_AFTER,
            "payload": claim_payload or _claim_payload(),
        }
    if CHECKPOINT_PATH in changed_files:
        targets[CHECKPOINT_PATH] = {
            "blob_sha": CHECKPOINT_AFTER,
            "payload": checkpoint_payload or _checkpoint_payload(),
        }
    return {
        "sha": COMMIT_SHA,
        "committed_at": committed_at,
        "changed_files": list(changed_files),
        "targets": targets,
    }


def _builder():
    builder = getattr(guard, "durable_coord_write_readbacks_from_live_commits", None)
    assert callable(builder), "RED: exact coordination write durable-readback builder is missing"
    return builder


def test_issue739_exact_checkpoint_write_auto_consumes():
    receipt = _receipt()
    readbacks = _builder()([receipt], live_coord_commits=[_commit()])
    decision = guard.classify_guard_transaction(
        receipts=[receipt],
        current_issue=ISSUE,
        current_worker=WORKER,
        current_executor_source="chat",
        current_branch=BRANCH,
        current_claim_head_sha=H0,
        live_branch_head_sha=H0,
        current_claim_blob_sha=CLAIM_BLOB,
        now=datetime.fromisoformat("2026-09-26T16:45:00+00:00"),
        durable_readbacks=readbacks,
        expected_changed_files=(CHECKPOINT_PATH,),
    )
    assert decision.state is guard.GuardTransactionState.CONSUMED
    assert readbacks[0]["target_changed"] is True
    assert readbacks[0]["coord_commit_sha"] == COMMIT_SHA


def test_issue739_exact_claim_and_checkpoint_write_auto_consumes():
    receipt = _receipt(changed_files=(CLAIM_PATH, CHECKPOINT_PATH))
    readbacks = _builder()(
        [receipt],
        live_coord_commits=[
            _commit(changed_files=(CLAIM_PATH, CHECKPOINT_PATH))
        ],
    )
    assert len(readbacks) == 1
    assert readbacks[0]["changed_files"] == sorted([CLAIM_PATH, CHECKPOINT_PATH])


@pytest.mark.parametrize(
    "changed_files",
    [
        ("tools/example.py",),
        (".dispatch/claims/issue-999.json",),
        (".dispatch/checkpoints/issue-999.json",),
        (CLAIM_PATH, "tools/example.py"),
    ],
)
def test_issue739_non_exact_coord_scope_stays_fail_closed(changed_files):
    assert _builder()(
        [_receipt(changed_files=changed_files)],
        live_coord_commits=[_commit(changed_files=changed_files)],
    ) == []


@pytest.mark.parametrize(
    ("claim_payload", "checkpoint_payload"),
    [
        (_claim_payload(issue=999), None),
        (_claim_payload(worker="other.worker"), None),
        (_claim_payload(work_branch="other/branch"), None),
        (_claim_payload(head_sha="9" * 40), None),
        (None, _checkpoint_payload(issue="999")),
        (None, _checkpoint_payload(branch="other/branch")),
        (None, _checkpoint_payload(head_sha="9" * 40)),
    ],
)
def test_issue739_wrong_postcondition_identity_stays_fail_closed(
    claim_payload, checkpoint_payload
):
    changed = (
        (CLAIM_PATH, CHECKPOINT_PATH)
        if claim_payload is not None
        else (CHECKPOINT_PATH,)
    )
    assert _builder()(
        [_receipt(changed_files=changed)],
        live_coord_commits=[
            _commit(
                changed_files=changed,
                claim_payload=claim_payload,
                checkpoint_payload=checkpoint_payload,
            )
        ],
    ) == []


def test_issue739_out_of_window_coord_commit_does_not_consume():
    assert _builder()(
        [_receipt()],
        live_coord_commits=[_commit(committed_at="2026-09-26T16:30:00Z")],
    ) == []


def test_issue739_ambiguous_exact_coord_writes_fail_closed():
    second = _commit(committed_at="2026-09-26T16:44:30Z")
    second["sha"] = "6" * 40
    with pytest.raises(guard.ExecutionClaimError, match="ambiguous|multiple|coord"):
        _builder()([_receipt()], live_coord_commits=[_commit(), second])


def test_issue739_trusted_workflow_wires_coord_write_readback():
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "whd-remote-execution-guard.yml"
    ).read_text(encoding="utf-8")
    required = (
        "durable_coord_write_readbacks_from_live_commits",
        "coord_write_readbacks =",
        "coord/dispatch-claims",
        "durable_readbacks=branch_create_readbacks + pr_write_readbacks + coord_write_readbacks",
    )
    missing = [token for token in required if token not in workflow]
    assert not missing, f"RED: trusted Guard missing exact coordination write readback wiring: {missing}"
