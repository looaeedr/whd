from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ISSUE = 558
BASE = "c" * 40
H0 = "a" * 40
H1 = "b" * 40
BRANCH = "fix/issue558-post-commit-claim-head-reconcile-20260923"
WORKER = "chatgpt.sol260923.issue558"
CLAIM_PATH = f".dispatch/claims/issue-{ISSUE}.json"


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _write_claim(tmp_path: Path, *, executor_source: str = "chatgpt_interactive") -> Path:
    path = tmp_path / "claim.json"
    path.write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
                "worker": WORKER,
                "executor_source": executor_source,
                "work_branch": BRANCH,
                "claimed_at": "2026-09-23T14:00:00Z",
                "base_sha": BASE,
                "head_sha": H0,
                "phase": "IMPLEMENTING",
                "last_update": "2026-09-23T14:00:00Z",
                "remote_qa": None,
                "next_action": "continue",
                "blocker": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _request_comment(*, blob: str, changed_files: list[str], executor_source: str = "chat") -> dict:
    body = "\n".join(
        [
            "WHD_REMOTE_GUARD_REQUEST_V1",
            f"issue={ISSUE}",
            f"worker={WORKER}",
            f"executor_source={executor_source}",
            "action=commit",
            f"branch={BRANCH}",
            f"base_sha={BASE}",
            f"head_sha={H0}",
            f"claim_blob_sha={blob}",
            "guard_authority_sha=" + "d" * 40,
            f"tested_target_sha={H0}",
            *[f"changed_file={item}" for item in changed_files],
        ]
    )
    return {"id": 101, "user": {"login": "looaeedr"}, "body": body}


def _result_comment(
    *,
    blob: str,
    changed_files: list[str],
    issued_at: str = "2026-09-23T14:05:00Z",
    expires_at: str = "2026-09-23T14:25:00Z",
    executor_source: str = "chat",
) -> dict:
    payload = {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "request_comment_id": 101,
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": executor_source,
        "action": "commit",
        "branch": BRANCH,
        "base_sha": BASE,
        "head_sha": H0,
        "claim_blob_sha": blob,
        "guard_authority_sha": "d" * 40,
        "tested_target_sha": H0,
        "changed_files": changed_files,
        "run_id": 123456,
        "orchestrator_head_sha": "e" * 40,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    return {
        "id": 102,
        "user": {"login": "github-actions[bot]"},
        "body": "WHD_REMOTE_GUARD_RESULT_V1\n~~~json\n"
        + json.dumps(payload)
        + "\n~~~",
    }


def _commit(*, parent: str = H0, files: list[str] | None = None, date: str = "2026-09-23T14:10:00Z") -> dict:
    files = files or ["docs/example.md"]
    return {
        "sha": H1,
        "parents": [{"sha": parent}],
        "commit": {"committer": {"date": date}},
        "files": [{"filename": item} for item in files],
    }


def _install_remote_evidence(monkeypatch, guard, claim_path: Path, *, files=None, parent=H0, issued_at="2026-09-23T14:05:00Z", expires_at="2026-09-23T14:25:00Z", date="2026-09-23T14:10:00Z"):
    files = files or ["docs/example.md"]
    blob = guard._git_blob_sha(claim_path)
    comments = [
        _request_comment(blob=blob, changed_files=files),
        _result_comment(blob=blob, changed_files=files, issued_at=issued_at, expires_at=expires_at),
    ]
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: _commit(parent=parent, files=files, date=date),
    )


def test_ordinary_stale_write_still_fails_closed(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: (_ for _ in ()).throw(AssertionError("must not fetch remote evidence")),
    )
    with pytest.raises(guard.ExecutionClaimError, match="stale claim head SHA"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=("tools/example.py",),
        )


def test_post_commit_claim_head_reconcile_accepts_bound_direct_child(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    _install_remote_evidence(monkeypatch, guard, claim_path)
    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="write",
        expected_base_sha=BASE,
        expected_head_sha=H1,
        changed_files=(CLAIM_PATH,),
    )
    assert claim.head_sha == H0



def test_post_commit_reconcile_accepts_authorized_noop_scope_superset(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    blob = guard._git_blob_sha(claim_path)
    authorized = ["docs/example.md", "tests/noop.py"]
    comments = [
        _request_comment(blob=blob, changed_files=authorized),
        _result_comment(blob=blob, changed_files=authorized),
    ]
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: _commit(files=["docs/example.md"]),
    )

    claim = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="write",
        expected_base_sha=BASE,
        expected_head_sha=H1,
        changed_files=(CLAIM_PATH,),
    )
    assert claim.head_sha == H0


def test_post_commit_reconcile_rejects_request_receipt_scope_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    blob = guard._git_blob_sha(claim_path)
    comments = [
        _request_comment(
            blob=blob,
            changed_files=["docs/example.md", "tests/noop.py"],
        ),
        _result_comment(blob=blob, changed_files=["docs/example.md"]),
    ]
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: _commit(files=["docs/example.md"]),
    )

    with pytest.raises(
        guard.ExecutionClaimError,
        match="matching prior GREEN mutation receipt",
    ):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=(CLAIM_PATH,),
        )


def test_post_commit_reconcile_rejects_non_direct_child(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    _install_remote_evidence(monkeypatch, guard, claim_path, parent="f" * 40)
    with pytest.raises(guard.ExecutionClaimError, match="single direct child"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=(CLAIM_PATH,),
        )


def test_post_commit_reconcile_rejects_receipt_file_scope_mismatch(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    blob = guard._git_blob_sha(claim_path)
    comments = [
        _request_comment(blob=blob, changed_files=["docs/authorized.md"]),
        _result_comment(blob=blob, changed_files=["docs/authorized.md"]),
    ]
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)
    monkeypatch.setattr(guard, "_github_commit", lambda sha: _commit(files=["docs/other.md"]))
    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN mutation receipt"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=(CLAIM_PATH,),
        )


def test_post_commit_reconcile_rejects_commit_outside_receipt_window(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    _install_remote_evidence(
        monkeypatch,
        guard,
        claim_path,
        issued_at="2026-09-23T14:05:00Z",
        expires_at="2026-09-23T14:06:00Z",
        date="2026-09-23T14:10:00Z",
    )
    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN mutation receipt"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=(CLAIM_PATH,),
        )


def test_post_commit_reconcile_requires_exact_claim_path(tmp_path: Path, monkeypatch) -> None:
    guard = _guard()
    claim_path = _write_claim(tmp_path)
    _install_remote_evidence(monkeypatch, guard, claim_path)
    with pytest.raises(guard.ExecutionClaimError, match="stale claim head SHA"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=H1,
            changed_files=(".dispatch/claims/issue-999.json",),
        )
