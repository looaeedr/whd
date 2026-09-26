from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"
WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-execution-guard.yml"

ISSUE = 617
BASE = "1" * 40
HEAD = "2" * 40
LIVE_HEAD = "3" * 40
BRANCH = "work/legacy-half-pair"
MUTATED_FILE = "docs/superpowers/checkpoints/issue617-a2-target-completion.json"
RECOVERY_RUN_ID = 36013452861
RECOVERY_REQUEST_ID = 5816149112


def _load_guard():
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue675", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim() -> dict:
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
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


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _postcommit_request(comment_id: int, claim_blob: str) -> dict:
    body = "\n".join([
        "WHD_REMOTE_GUARD_REQUEST_V1",
        f"issue={ISSUE}",
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
        "issue": ISSUE,
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
    return {
        "id": comment_id,
        "user": {"login": "github-actions[bot]"},
        "body": "WHD_REMOTE_GUARD_RESULT_V1\n~~~json\n"
        + json.dumps(payload)
        + "\n~~~",
    }


def _install_expired_postcommit(monkeypatch, guard, claim_path: Path) -> None:
    claim_blob = guard._git_blob_sha(claim_path)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: {
            "sha": LIVE_HEAD,
            "parents": [{"sha": HEAD}],
            "files": [{"filename": MUTATED_FILE}],
            "commit": {"committer": {"date": "2026-09-24T15:18:40Z"}},
        },
    )
    monkeypatch.setattr(
        guard,
        "_github_issue_comments",
        lambda issue: [
            _postcommit_request(RECOVERY_REQUEST_ID, claim_blob),
            _postcommit_receipt(9002, claim_blob),
        ],
    )


def _write_recovery_comment(path: Path, claim_blob_sha: str, **overrides) -> Path:
    fields = {
        "issue": str(ISSUE),
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "branch": BRANCH,
        "claim_blob_sha": claim_blob_sha,
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


def test_expired_postcommit_stays_red_without_owner_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)

    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=_claim(),
            issue=ISSUE,
            worker=claim.worker,
            branch=BRANCH,
            expected_live_head_sha=LIVE_HEAD,
            changed_files=(f".dispatch/claims/issue-{ISSUE}.json",),
        )


def test_expired_postcommit_accepts_exact_owner_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(tmp_path / "recovery.json", guard._git_blob_sha(claim_path))

    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=_claim(),
        issue=ISSUE,
        worker=claim.worker,
        branch=BRANCH,
        expected_live_head_sha=LIVE_HEAD,
        changed_files=(f".dispatch/claims/issue-{ISSUE}.json",),
        legacy_reconcile_recovery=recovery,
    )


def test_expired_postcommit_recovery_rejects_live_head_drift(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(
        tmp_path / "recovery.json",
        guard._git_blob_sha(claim_path),
        live_head_sha="9" * 40,
    )

    with pytest.raises(guard.ExecutionClaimError, match="recovery|authority|head"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=_claim(),
            issue=ISSUE,
            worker=claim.worker,
            branch=BRANCH,
            expected_live_head_sha=LIVE_HEAD,
            changed_files=(f".dispatch/claims/issue-{ISSUE}.json",),
            legacy_reconcile_recovery=recovery,
        )


def test_expired_postcommit_recovery_rejects_wrong_prior_guard_run(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)
    _install_expired_postcommit(monkeypatch, guard, claim_path)
    recovery = _write_recovery_comment(
        tmp_path / "recovery.json",
        guard._git_blob_sha(claim_path),
        prior_guard_run_id=str(RECOVERY_RUN_ID + 1),
    )

    with pytest.raises(guard.ExecutionClaimError, match="recovery|authority|guard|run"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=_claim(),
            issue=ISSUE,
            worker=claim.worker,
            branch=BRANCH,
            expected_live_head_sha=LIVE_HEAD,
            changed_files=(f".dispatch/claims/issue-{ISSUE}.json",),
            legacy_reconcile_recovery=recovery,
        )


def test_trusted_remote_guard_transports_legacy_recovery_authority() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "legacy_reconcile_recovery_comment_id",
        "WHD_LEGACY_POSTCOMMIT_RECONCILE_V1",
        "--legacy-reconcile-recovery",
    )
    missing = [token for token in required if token not in workflow]
    assert not missing, (
        "trusted Remote Guard lacks legacy expired postcommit recovery transport: "
        f"{missing}"
    )
