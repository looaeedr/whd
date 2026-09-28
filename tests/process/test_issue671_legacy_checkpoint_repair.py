from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"
WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-claim-activation.yml"

BASE = "1" * 40
HEAD = "2" * 40
BRANCH = "work/legacy-half-pair"


def _load_guard():
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue671", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(**overrides):
    payload = {
        "issue": 617,
        "issue_url": "https://github.com/looaeedr/whd/issues/617",
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T14:14:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "DRIFT_AUDIT",
        "last_update": "2026-09-24T14:31:11Z",
        "production_target": "cleanup/2d-3d-sync",
        "delegated_branches": [],
        "next_action": "finish",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _checkpoint(**overrides):
    payload = {
        "version": 1,
        "issue": "617",
        "branch": BRANCH,
        "head_sha": HEAD,
        "state": "RUNNING",
        "next_action": "reconcile guarded live head, then terminal finalization",
        "run_id": None,
        "job_id": None,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": ["legacy checkpoint bootstrap"],
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "chain_reason": None,
        "closure_state": "CLOSED",
        "closure_next_action": None,
    }
    payload.update(overrides)
    return payload


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_candidate_gate_accepts_strict_unchanged_claim_plus_new_checkpoint(tmp_path: Path):
    guard = _load_guard()
    gate = getattr(guard, "assert_legacy_checkpoint_repair_transaction", None)
    assert callable(gate), "legacy half-pair repair gate is missing"

    prior = _write(tmp_path / "prior-claim.json", _claim())
    candidate = tmp_path / "candidate-claim.json"
    candidate.write_bytes(prior.read_bytes())
    checkpoint = _write(tmp_path / "candidate-checkpoint.json", _checkpoint())

    result = gate(
        prior,
        candidate,
        checkpoint,
        prior_checkpoint_exists=False,
        changed_files=(
            ".dispatch/claims/issue-617.json",
            ".dispatch/checkpoints/issue-617.json",
        ),
    )
    assert result.issue == "617"
    assert result.branch == BRANCH
    assert result.head_sha == HEAD


@pytest.mark.parametrize(
    "mutation",
    [
        {"worker": "scheduler.other"},
        {"executor_source": "chatgpt_interactive"},
        {"work_branch": "work/other"},
        {"base_sha": "3" * 40},
        {"head_sha": "4" * 40},
        {"phase": "RECOVERING"},
        {"next_action": "changed"},
    ],
)
def test_candidate_gate_rejects_any_claim_mutation(tmp_path: Path, mutation: dict):
    guard = _load_guard()
    gate = getattr(guard, "assert_legacy_checkpoint_repair_transaction", None)
    assert callable(gate), "legacy half-pair repair gate is missing"

    prior = _write(tmp_path / "prior-claim.json", _claim())
    candidate = _write(tmp_path / "candidate-claim.json", _claim(**mutation))
    checkpoint = _write(tmp_path / "candidate-checkpoint.json", _checkpoint())

    with pytest.raises(guard.ExecutionClaimError, match="legacy|unchanged|claim"):
        gate(
            prior,
            candidate,
            checkpoint,
            prior_checkpoint_exists=False,
            changed_files=(
                ".dispatch/claims/issue-617.json",
                ".dispatch/checkpoints/issue-617.json",
            ),
        )


def test_candidate_gate_rejects_existing_prior_checkpoint(tmp_path: Path):
    guard = _load_guard()
    gate = getattr(guard, "assert_legacy_checkpoint_repair_transaction", None)
    assert callable(gate), "legacy half-pair repair gate is missing"
    prior = _write(tmp_path / "prior-claim.json", _claim())
    candidate = tmp_path / "candidate-claim.json"
    candidate.write_bytes(prior.read_bytes())
    checkpoint = _write(tmp_path / "candidate-checkpoint.json", _checkpoint())

    with pytest.raises(guard.ExecutionClaimError, match="checkpoint|legacy"):
        gate(
            prior,
            candidate,
            checkpoint,
            prior_checkpoint_exists=True,
            changed_files=(
                ".dispatch/claims/issue-617.json",
                ".dispatch/checkpoints/issue-617.json",
            ),
        )


def test_candidate_gate_rejects_non_pair_scope(tmp_path: Path):
    guard = _load_guard()
    gate = getattr(guard, "assert_legacy_checkpoint_repair_transaction", None)
    assert callable(gate), "legacy half-pair repair gate is missing"
    prior = _write(tmp_path / "prior-claim.json", _claim())
    candidate = tmp_path / "candidate-claim.json"
    candidate.write_bytes(prior.read_bytes())
    checkpoint = _write(tmp_path / "candidate-checkpoint.json", _checkpoint())

    with pytest.raises(guard.ExecutionClaimError, match="pair|claim|checkpoint"):
        gate(
            prior,
            candidate,
            checkpoint,
            prior_checkpoint_exists=False,
            changed_files=(".dispatch/checkpoints/issue-617.json",),
        )


def test_candidate_gate_rejects_checkpoint_identity_drift(tmp_path: Path):
    guard = _load_guard()
    gate = getattr(guard, "assert_legacy_checkpoint_repair_transaction", None)
    assert callable(gate), "legacy half-pair repair gate is missing"
    prior = _write(tmp_path / "prior-claim.json", _claim())
    candidate = tmp_path / "candidate-claim.json"
    candidate.write_bytes(prior.read_bytes())
    checkpoint = _write(
        tmp_path / "candidate-checkpoint.json",
        _checkpoint(head_sha="9" * 40),
    )
    with pytest.raises(guard.ExecutionClaimError, match="checkpoint|head"):
        gate(
            prior,
            candidate,
            checkpoint,
            prior_checkpoint_exists=False,
            changed_files=(
                ".dispatch/claims/issue-617.json",
                ".dispatch/checkpoints/issue-617.json",
            ),
        )


def test_activation_transaction_accepts_legacy_repair_candidate_pair(tmp_path: Path):
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    checkpoint = _write(tmp_path / "checkpoint.json", _checkpoint())
    claim = guard.load_execution_claim(claim_path)

    result = guard.assert_active_claim_activation_transaction(
        claim,
        checkpoint,
        transition="legacy-checkpoint-repair",
        changed_files=(
            ".dispatch/claims/issue-617.json",
            ".dispatch/checkpoints/issue-617.json",
        ),
    )
    assert result.state == "RUNNING"


def test_trusted_workflow_binds_legacy_repair_prior_identity():
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "legacy-checkpoint-repair",
        "prior_claim_blob_sha",
        "assert_legacy_checkpoint_repair_transaction",
        "prior_checkpoint",
        "candidate_claim_blob_sha",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"trusted activation workflow lacks legacy repair identity: {missing}"
    assert "prior claim must exist" in text.lower()
    assert "prior checkpoint must be missing" in text.lower()


LIVE_HEAD = "3" * 40
MUTATED_FILE = "docs/superpowers/checkpoints/issue617-a2-target-completion.json"
RECOVERY_RUN_ID = 36013452861
RECOVERY_REQUEST_ID = 5816149112


def _postcommit_request(comment_id: int, claim_blob: str) -> dict:
    body = "\n".join([
        "WHD_REMOTE_GUARD_REQUEST_V1",
        "issue=617",
        "worker=scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source=scheduler",
        "action=commit",
        f"branch={BRANCH}",
        f"base_sha={BASE}",
        f"head_sha={HEAD}",
        f"claim_blob_sha={claim_blob}",
        f"guard_authority_sha={'4' * 40}",
        f"tested_target_sha={HEAD}",
        f"changed_file={MUTATED_FILE}",
    ])
    return {"id": comment_id, "user": {"login": "looaeedr"}, "body": body}


def _postcommit_receipt(comment_id: int, claim_blob: str) -> dict:
    payload = {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "issue": 617,
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "action": "commit",
        "branch": BRANCH,
        "base_sha": BASE,
        "head_sha": HEAD,
        "claim_blob_sha": claim_blob,
        "guard_authority_sha": "4" * 40,
        "tested_target_sha": HEAD,
        "changed_files": [MUTATED_FILE],
        "request_comment_id": RECOVERY_REQUEST_ID,
        "run_id": RECOVERY_RUN_ID,
        "issued_at": "2026-09-24T14:31:54Z",
        "expires_at": "2026-09-24T14:51:54Z",
    }
    return {"id": comment_id, "user": {"login": "github-actions[bot]"},
            "body": "WHD_REMOTE_GUARD_RESULT_V1\n~~~json\n" + json.dumps(payload) + "\n~~~"}


def _install_expired_postcommit(monkeypatch, guard, claim_path: Path) -> None:
    claim_blob = guard._git_blob_sha(claim_path)
    monkeypatch.setattr(guard, "_github_commit", lambda sha: {
        "sha": LIVE_HEAD,
        "parents": [{"sha": HEAD}],
        "files": [{"filename": MUTATED_FILE}],
        "commit": {"committer": {"date": "2026-09-24T15:18:40Z"}},
    })
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: [
        _postcommit_request(RECOVERY_REQUEST_ID, claim_blob),
        _postcommit_receipt(9002, claim_blob),
    ])


def _write_recovery_comment(path: Path, **overrides) -> Path:
    fields = {
        "issue": "617",
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "branch": BRANCH,
        "claim_blob_sha": _load_guard()._git_blob_sha(path.parent / "claim.json"),
        "claim_head_sha": HEAD,
        "live_head_sha": LIVE_HEAD,
        "prior_guard_run_id": str(RECOVERY_RUN_ID),
        "prior_request_comment_id": str(RECOVERY_REQUEST_ID),
        "recovery_reason": "LEGACY_RECEIPT_WINDOW_EXPIRED_AFTER_MUTATION",
        "changed_file": MUTATED_FILE,
    }
    fields.update(overrides)

    body = "\n".join([
        "WHD_LEGACY_POSTCOMMIT_RECONCILE_V1",
        *(f"{key}={value}" for key, value in fields.items()),
    ])
    payload = {"id": 9003, "user": {"login": "looaeedr"}, "body": body}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_expired_postcommit_reconciliation_stays_red_without_owner_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path, claim=claim, raw_claim=_claim(), issue=617,
            worker=claim.worker, branch=BRANCH,
            expected_live_head_sha=LIVE_HEAD,
            changed_files=(".dispatch/claims/issue-617.json",),
        )


def test_expired_postcommit_reconciliation_accepts_exact_owner_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(tmp_path / "recovery.json")
    guard._assert_post_commit_claim_head_reconciliation(
        claim_path, claim=claim, raw_claim=_claim(), issue=617,
        worker=claim.worker, branch=BRANCH,
        expected_live_head_sha=LIVE_HEAD,
        changed_files=(".dispatch/claims/issue-617.json",),
        legacy_reconcile_recovery=recovery,
    )


def test_expired_postcommit_recovery_rejects_live_head_drift(tmp_path: Path, monkeypatch) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(tmp_path / "recovery.json", live_head_sha="9" * 40)
    with pytest.raises(guard.ExecutionClaimError, match="recovery|authority|head"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path, claim=claim, raw_claim=_claim(), issue=617,
            worker=claim.worker, branch=BRANCH, expected_live_head_sha=LIVE_HEAD,
            changed_files=(".dispatch/claims/issue-617.json",),
            legacy_reconcile_recovery=recovery,
        )


def test_trusted_remote_guard_transports_legacy_postcommit_recovery_authority() -> None:
    workflow = (ROOT / ".github" / "workflows" / "whd-remote-execution-guard.yml").read_text(
        encoding="utf-8"
    )
    required = (
        "legacy_reconcile_recovery_comment_id",
        "WHD_LEGACY_POSTCOMMIT_RECONCILE_V1",
        "--legacy-reconcile-recovery",
    )
    missing = [token for token in required if token not in workflow]
    assert not missing, f"trusted Remote Guard lacks legacy postcommit recovery transport: {missing}"

def test_expired_postcommit_recovery_rejects_wrong_prior_guard_run(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(
        tmp_path / "recovery.json",
        prior_guard_run_id=str(RECOVERY_RUN_ID + 1),
    )
    with pytest.raises(guard.ExecutionClaimError, match="recovery|authority|guard|run"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=_claim(),
            issue=617,
            worker=claim.worker,
            branch=BRANCH,
            expected_live_head_sha=LIVE_HEAD,
            changed_files=(".dispatch/claims/issue-617.json",),
            legacy_reconcile_recovery=recovery,
        )
