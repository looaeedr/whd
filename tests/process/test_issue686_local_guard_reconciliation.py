from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"

BASE = "1" * 40
HEAD = "2" * 40
LIVE_HEAD = "3" * 40
BRANCH = "work/issue686-local-proof"
WORKER = "chatgpt.work1.260926.1"
MUTATED_FILE = "tests/process/local-proof-target.txt"


def _load_guard():
    spec = importlib.util.spec_from_file_location("issue686_guard", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(**overrides):
    payload = {
        "issue": 686,
        "issue_url": "https://github.com/looaeedr/whd/issues/686",
        "worker": WORKER,
        "executor_source": "chat",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-26T10:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "RED",
        "last_update": "2026-09-26T10:00:00Z",
        "production_target": "cleanup/2d-3d-sync",
        "delegated_branches": [],
        "next_action": "implement",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _proof_comment(guard, claim_path: Path, comment_id: int = 9001, **overrides):
    fields = {
        "issue": "686",
        "worker": WORKER,
        "executor_source": "chat",
        "action": "commit",
        "branch": BRANCH,
        "base_sha": BASE,
        "claim_blob_sha": guard._git_blob_sha(claim_path),
        "claim_head_sha": HEAD,
        "live_head_sha": LIVE_HEAD,
        "local_guard_result": "EXECUTION_CLAIM_GUARD_GREEN",
    }
    fields.update({k: str(v) for k, v in overrides.items() if k != "changed_file"})
    changed_file = str(overrides.get("changed_file", MUTATED_FILE))
    body = "\n".join([
        "WHD_LOCAL_GUARD_RECONCILE_V1",
        *(f"{key}={value}" for key, value in fields.items()),
        f"changed_file={changed_file}",
    ])
    return {
        "id": comment_id,
        "user": {"login": "looaeedr"},
        "body": body,
    }


def _install_commit(monkeypatch, guard, comments, *, parents=None, files=None):
    monkeypatch.setattr(guard, "_github_commit", lambda sha: {
        "sha": LIVE_HEAD,
        "parents": parents if parents is not None else [{"sha": HEAD}],
        "files": files if files is not None else [{"filename": MUTATED_FILE}],
        "commit": {"committer": {"date": "2026-09-26T10:05:00Z"}},
    })
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)


def _assert_local_proof(guard, claim_path: Path, proof_path: Path):
    claim = guard.load_execution_claim(claim_path)
    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=_claim(),
        issue=686,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=LIVE_HEAD,
        changed_files=(
            ".dispatch/claims/issue-686.json",
            ".dispatch/checkpoints/issue-686.json",
        ),
        local_guard_proof=proof_path,
    )


def test_local_guard_postcommit_reconciliation_accepts_exact_durable_proof(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path)
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [proof])
    _assert_local_proof(guard, claim_path, proof_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("worker", "chatgpt.other", "worker mismatch"),
        ("claim_blob_sha", "4" * 40, "claim_blob_sha mismatch"),
        ("branch", "work/other", "branch mismatch"),
        ("live_head_sha", "5" * 40, "live_head_sha mismatch"),
        ("changed_file", "tests/process/wrong.txt", "changed-file mismatch"),
    ],
)
def test_local_guard_postcommit_reconciliation_rejects_identity_drift(
    tmp_path: Path, monkeypatch, field: str, value: str, message: str
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path, **{field: value})
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [proof])
    with pytest.raises(guard.ExecutionClaimError, match=message):
        _assert_local_proof(guard, claim_path, proof_path)


def test_local_guard_postcommit_reconciliation_rejects_foreign_author(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path)
    proof["user"]["login"] = "someone-else"
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [proof])
    with pytest.raises(guard.ExecutionClaimError, match="repository-owner"):
        _assert_local_proof(guard, claim_path, proof_path)


def test_local_guard_postcommit_reconciliation_rejects_non_direct_child(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path)
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [proof], parents=[{"sha": "9" * 40}])
    with pytest.raises(guard.ExecutionClaimError, match="direct|merge sync"):
        _assert_local_proof(guard, claim_path, proof_path)


def test_local_guard_postcommit_reconciliation_rejects_duplicate_exact_proof(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path, comment_id=9001)
    duplicate = _proof_comment(guard, claim_path, comment_id=9002)
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [proof, duplicate])
    with pytest.raises(guard.ExecutionClaimError, match="duplicate|ambiguous"):
        _assert_local_proof(guard, claim_path, proof_path)


def test_local_guard_postcommit_reconciliation_requires_durable_issue_comment(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    proof = _proof_comment(guard, claim_path)
    proof_path = _write(tmp_path / "proof.json", proof)
    _install_commit(monkeypatch, guard, [])
    with pytest.raises(guard.ExecutionClaimError, match="durably present"):
        _assert_local_proof(guard, claim_path, proof_path)


def test_cli_transports_local_guard_durable_proof() -> None:
    guard = _load_guard()
    parser = guard._build_parser()
    actions = {action.dest for action in parser._actions}
    assert "local_guard_proof" in actions
