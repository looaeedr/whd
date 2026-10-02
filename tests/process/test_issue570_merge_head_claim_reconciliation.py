from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ISSUE = 570
BASE = "a" * 40
CLAIM_HEAD = "b" * 40
PRODUCTION_HEAD = "c" * 40
MERGE_HEAD = "d" * 40
BRANCH = "governance/issue570-merge-head-claim-reconcile-20260924"
WORKER = "scheduler.6ab13f881c34819180cee63f5dd9446b"
PRODUCTION_TARGET = "cleanup/2d-3d-sync"
CLAIM_PATH = f".dispatch/claims/issue-{ISSUE}.json"
MUTATED_FILES = ("docs/governance/example.md", "tools/example.py")


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _claim(tmp_path: Path):
    guard = _guard()
    payload = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": WORKER,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T01:23:20+08:00",
        "base_sha": BASE,
        "head_sha": CLAIM_HEAD,
        "phase": "GREEN",
        "production_target": PRODUCTION_TARGET,
    }
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    claim = guard.ExecutionClaim(
        issue=ISSUE,
        issue_url=payload["issue_url"],
        worker=WORKER,
        work_branch=BRANCH,
        claimed_at=payload["claimed_at"],
        base_sha=BASE,
        head_sha=CLAIM_HEAD,
        phase="GREEN",
    )
    return guard, path, claim, payload


def _request(comment_id: int, claim_blob: str) -> dict:
    body = "\n".join(
        [
            "WHD_REMOTE_GUARD_REQUEST_V1",
            f"issue={ISSUE}",
            f"worker={WORKER}",
            "executor_source=scheduler",
            "action=commit",
            f"branch={BRANCH}",
            f"base_sha={BASE}",
            f"head_sha={CLAIM_HEAD}",
            f"claim_blob_sha={claim_blob}",
            f"guard_authority_sha={PRODUCTION_HEAD}",
            f"tested_target_sha={CLAIM_HEAD}",
            *(f"changed_file={path}" for path in MUTATED_FILES),
        ]
    )
    return {"id": comment_id, "user": {"login": "looaeedr"}, "body": body}


def _receipt(
    comment_id: int, request_id: int, claim_blob: str, **overrides
) -> dict:
    payload = {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "scheduler",
        "action": "commit",
        "branch": BRANCH,
        "base_sha": BASE,
        "head_sha": CLAIM_HEAD,
        "claim_blob_sha": claim_blob,
        "guard_authority_sha": PRODUCTION_HEAD,
        "tested_target_sha": CLAIM_HEAD,
        "changed_files": list(MUTATED_FILES),
        "request_comment_id": request_id,
        "issued_at": "2026-09-23T17:20:00Z",
        "expires_at": "2026-09-23T17:40:00Z",
    }
    payload.update(overrides)
    return {
        "id": comment_id,
        "user": {"login": "github-actions[bot]"},
        "body": "WHD_REMOTE_GUARD_RESULT_V1\n~~~json\n"
        + json.dumps(payload)
        + "\n~~~",
    }


def _install(
    monkeypatch,
    guard,
    claim_path: Path,
    *,
    parents=None,
    files=None,
    current_production_head=PRODUCTION_HEAD,
    receipt_overrides=None,
    work_delta_files=None,
):
    claim_blob = guard._git_blob_sha(claim_path)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: {
            "sha": MERGE_HEAD,
            "parents": parents
            if parents is not None
            else [{"sha": PRODUCTION_HEAD}, {"sha": CLAIM_HEAD}],
            "files": files
            if files is not None
            else [
                {"filename": "production-parent-only-governance.md"},
                *({"filename": path} for path in MUTATED_FILES),
            ],
            "commit": {"committer": {"date": "2026-09-23T17:25:00Z"}},
        },
    )
    request_id = 1001
    monkeypatch.setattr(
        guard,
        "_github_issue_comments",
        lambda issue: [
            _request(request_id, claim_blob),
            _receipt(
                1002,
                request_id,
                claim_blob,
                **(receipt_overrides or {}),
            ),
        ],
    )

    def fake_api(path: str):
        if path.startswith("branches/"):
            return {
                "name": PRODUCTION_TARGET,
                "commit": {"sha": current_production_head},
            }
        if path == f"compare/{PRODUCTION_HEAD}...{MERGE_HEAD}":
            return {
                "status": "ahead",
                "merge_base_commit": {"sha": PRODUCTION_HEAD},
                "files": [
                    {"filename": item}
                    for item in (
                        work_delta_files
                        if work_delta_files is not None
                        else MUTATED_FILES
                    )
                ],
            }
        if path.startswith("compare/"):
            return {
                "status": "ahead",
                "merge_base_commit": {"sha": PRODUCTION_HEAD},
                "files": [],
            }
        raise AssertionError(f"unexpected API path: {path}")

    monkeypatch.setattr(guard, "_github_api_json", fake_api)


def test_merge_sync_reconciliation_accepts_exact_production_first_parent(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(monkeypatch, guard, claim_path)

    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=raw,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=MERGE_HEAD,
        changed_files=(CLAIM_PATH,),
    )


def test_merge_sync_reconciliation_ignores_production_parent_only_commit_files(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        files=[
            {"filename": "production-parent-only-governance.md"},
            *({"filename": path} for path in MUTATED_FILES),
        ],
        work_delta_files=MUTATED_FILES,
    )

    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=raw,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=MERGE_HEAD,
        changed_files=(CLAIM_PATH,),
    )


def test_merge_sync_reconciliation_accepts_claim_first_parent(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        parents=[{"sha": CLAIM_HEAD}, {"sha": PRODUCTION_HEAD}],
    )

    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=raw,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=MERGE_HEAD,
        changed_files=(CLAIM_PATH,),
    )


def test_merge_sync_reconciliation_rejects_duplicate_claim_parents(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        parents=[{"sha": CLAIM_HEAD}, {"sha": CLAIM_HEAD}],
    )

    with pytest.raises(guard.ExecutionClaimError, match="production|parent"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_merge_sync_reconciliation_allows_production_target_to_advance(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        current_production_head="f" * 40,
    )

    guard._assert_post_commit_claim_head_reconciliation(
        claim_path,
        claim=claim,
        raw_claim=raw,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=MERGE_HEAD,
        changed_files=(CLAIM_PATH,),
    )


def test_merge_sync_reconciliation_rejects_wrong_guard_authority_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        receipt_overrides={"guard_authority_sha": "e" * 40},
    )

    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_merge_sync_reconciliation_rejects_wrong_claim_blob_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        receipt_overrides={"claim_blob_sha": "e" * 40},
    )

    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_merge_sync_reconciliation_rejects_foreign_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        receipt_overrides={"worker": "scheduler.foreign-lane"},
    )

    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_merge_sync_reconciliation_rejects_unrelated_other_parent(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        parents=[{"sha": "e" * 40}, {"sha": CLAIM_HEAD}],
    )

    with pytest.raises(guard.ExecutionClaimError, match="production"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_merge_sync_reconciliation_rejects_extra_tree_change(
    tmp_path: Path, monkeypatch
) -> None:
    guard, claim_path, claim, raw = _claim(tmp_path)
    _install(
        monkeypatch,
        guard,
        claim_path,
        work_delta_files=(*MUTATED_FILES, "unexpected.txt"),
    )

    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            claim_path,
            claim=claim,
            raw_claim=raw,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=MERGE_HEAD,
            changed_files=(CLAIM_PATH,),
        )
