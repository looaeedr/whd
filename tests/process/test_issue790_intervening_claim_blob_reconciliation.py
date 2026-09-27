from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path

import pytest

ISSUE = 790
BASE = "1" * 40
H0 = "2" * 40
H1 = "3" * 40
BRANCH = "governance/issue790-intervening-claim-blob-reconcile-20260927"
WORKER = "chatgpt.sol260927.issue790.dep769.1"
MUTATED = ".github/workflows/qa-issue769-terminal-scheduler-census.yml"
CLAIM_PATH = f".dispatch/claims/issue-{ISSUE}.json"
CHECKPOINT_PATH = f".dispatch/checkpoints/issue-{ISSUE}.json"


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _claim_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": WORKER,
        "executor_source": "chat",
        "actual_invocation_source": "chatgpt_interactive",
        "invocation_identity": "chat.issue790",
        "conversation_identity": "UNAVAILABLE",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-27T00:00:00Z",
        "base_sha": BASE,
        "head_sha": H0,
        "phase": "GREEN",
        "last_update": "2026-09-27T00:10:00Z",
        "production_target": "main",
        "delegated_branches": [],
        "remote_qa": None,
        "next_action": "continue",
        "blocker": None,
        "checkpoint": CHECKPOINT_PATH,
        "evidence": ["old"],
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _request(historical_blob: str) -> dict[str, object]:
    body = "\n".join(
        [
            "WHD_REMOTE_GUARD_REQUEST_V1",
            f"issue={ISSUE}",
            f"worker={WORKER}",
            "executor_source=chat",
            "action=commit",
            f"branch={BRANCH}",
            f"base_sha={BASE}",
            f"head_sha={H0}",
            f"claim_blob_sha={historical_blob}",
            "guard_authority_sha=" + "4" * 40,
            f"tested_target_sha={H0}",
            f"changed_file={MUTATED}",
        ]
    )
    return {"id": 101, "user": {"login": "looaeedr"}, "body": body}


def _receipt(historical_blob: str) -> dict[str, object]:
    payload = {
        "schema": "WHD_REMOTE_GUARD_RECEIPT_V1",
        "result": "GREEN",
        "reason": "EXECUTION_CLAIM_GUARD_GREEN",
        "issue": ISSUE,
        "worker": WORKER,
        "executor_source": "chat",
        "action": "commit",
        "branch": BRANCH,
        "base_sha": BASE,
        "head_sha": H0,
        "claim_blob_sha": historical_blob,
        "guard_authority_sha": "4" * 40,
        "tested_target_sha": H0,
        "changed_files": [MUTATED],
        "request_comment_id": 101,
        "issued_at": "2026-09-27T00:20:00Z",
        "expires_at": "2026-09-27T01:00:00Z",
        "run_id": 123456,
    }
    return {
        "id": 102,
        "user": {"login": "github-actions[bot]"},
        "body": "WHD_REMOTE_GUARD_RESULT_V1\n~~~json\n"
        + json.dumps(payload)
        + "\n~~~",
    }


def _recovery(
    current_blob: str,
    historical_blob: str,
    *,
    author: str = "looaeedr",
    **overrides: str,
) -> dict[str, object]:
    fields = {
        "issue": str(ISSUE),
        "worker": WORKER,
        "executor_source": "chat",
        "branch": BRANCH,
        "current_claim_blob_sha": current_blob,
        "historical_claim_blob_sha": historical_blob,
        "claim_head_sha": H0,
        "live_head_sha": H1,
        "prior_guard_run_id": "123456",
        "prior_request_comment_id": "101",
        "recovery_reason": "INTERVENING_SAME_OWNER_COORD_WRITE",
    }
    fields.update(overrides)
    body = "\n".join(
        [
            "WHD_INTERVENING_COORD_POSTCOMMIT_RECONCILE_V1",
            *(f"{key}={value}" for key, value in fields.items()),
            f"changed_file={MUTATED}",
        ]
    )
    return {"id": 103, "user": {"login": author}, "body": body}


def _install(
    monkeypatch: pytest.MonkeyPatch,
    guard,
    *,
    current_path: Path,
    historical_path: Path,
    recovery: dict[str, object],
    commit_files: list[str] | None = None,
) -> tuple[str, str]:
    current_blob = guard._git_blob_sha(current_path)
    historical_blob = guard._git_blob_sha(historical_path)
    comments = [_request(historical_blob), _receipt(historical_blob), recovery]
    monkeypatch.setattr(guard, "_github_issue_comments", lambda issue: comments)
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: {
            "sha": H1,
            "parents": [{"sha": H0}],
            "files": [
                {"filename": item}
                for item in (commit_files if commit_files is not None else [MUTATED])
            ],
            "commit": {"committer": {"date": "2026-09-27T00:30:00Z"}},
        },
    )

    raw = historical_path.read_bytes()

    def fake_api(path: str):
        if path == f"git/blobs/{historical_blob}":
            return {
                "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
            }
        raise AssertionError(f"unexpected API path: {path}")

    monkeypatch.setattr(guard, "_github_api_json", fake_api)
    return current_blob, historical_blob


def _assert_reconcile(
    guard,
    current_path: Path,
    recovery_path: Path,
    current_payload: dict[str, object],
) -> None:
    claim = guard.load_execution_claim(current_path)
    guard._assert_post_commit_claim_head_reconciliation(
        current_path,
        claim=claim,
        raw_claim=current_payload,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        expected_live_head_sha=H1,
        changed_files=(CLAIM_PATH, CHECKPOINT_PATH),
        intervening_coord_recovery=recovery_path,
    )


def test_without_recovery_current_blob_mismatch_remains_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = _guard()
    historical = _claim_payload(last_update="2026-09-27T00:10:00Z", evidence=["old"])
    current = _claim_payload(
        last_update="2026-09-27T00:31:00Z",
        evidence=["old", "remote QA accepted"],
        remote_qa={"run_id": 999, "status": "completed", "conclusion": "success"},
        next_action="merge after QA",
    )
    historical_path = _write_json(tmp_path / "historical.json", historical)
    current_path = _write_json(tmp_path / "current.json", current)
    historical_blob = guard._git_blob_sha(historical_path)
    monkeypatch.setattr(
        guard,
        "_github_issue_comments",
        lambda issue: [_request(historical_blob), _receipt(historical_blob)],
    )
    monkeypatch.setattr(
        guard,
        "_github_commit",
        lambda sha: {
            "sha": H1,
            "parents": [{"sha": H0}],
            "files": [{"filename": MUTATED}],
            "commit": {"committer": {"date": "2026-09-27T00:30:00Z"}},
        },
    )
    with pytest.raises(guard.ExecutionClaimError, match="matching prior GREEN"):
        guard._assert_post_commit_claim_head_reconciliation(
            current_path,
            claim=guard.load_execution_claim(current_path),
            raw_claim=current,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            expected_live_head_sha=H1,
            changed_files=(CLAIM_PATH, CHECKPOINT_PATH),
        )


def test_exact_intervening_same_owner_coord_refresh_can_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = _guard()
    historical = _claim_payload(last_update="2026-09-27T00:10:00Z", evidence=["old"])
    current = _claim_payload(
        last_update="2026-09-27T00:31:00Z",
        evidence=["old", "remote QA accepted"],
        remote_qa={"run_id": 999, "status": "completed", "conclusion": "success"},
        next_action="merge after QA",
    )
    historical_path = _write_json(tmp_path / "historical.json", historical)
    current_path = _write_json(tmp_path / "current.json", current)
    current_blob = guard._git_blob_sha(current_path)
    historical_blob = guard._git_blob_sha(historical_path)
    recovery = _recovery(current_blob, historical_blob)
    recovery_path = _write_json(tmp_path / "recovery.json", recovery)
    _install(
        monkeypatch,
        guard,
        current_path=current_path,
        historical_path=historical_path,
        recovery=recovery,
    )
    _assert_reconcile(guard, current_path, recovery_path, current)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("worker", "chatgpt.foreign"),
        ("phase", "CLOSING"),
        ("work_branch", "governance/other"),
        ("head_sha", "5" * 40),
    ],
)
def test_recovery_rejects_authority_bearing_claim_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    guard = _guard()
    historical = _claim_payload()
    current = _claim_payload(**{field: value})
    historical_path = _write_json(tmp_path / "historical.json", historical)
    current_path = _write_json(tmp_path / "current.json", current)
    current_blob = guard._git_blob_sha(current_path)
    historical_blob = guard._git_blob_sha(historical_path)
    recovery = _recovery(current_blob, historical_blob)
    recovery_path = _write_json(tmp_path / "recovery.json", recovery)
    _install(
        monkeypatch,
        guard,
        current_path=current_path,
        historical_path=historical_path,
        recovery=recovery,
    )
    with pytest.raises(guard.ExecutionClaimError, match="authority|mismatch"):
        _assert_reconcile(guard, current_path, recovery_path, current)


def test_recovery_rejects_foreign_author(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = _guard()
    historical = _claim_payload()
    current = _claim_payload(last_update="2026-09-27T00:31:00Z")
    historical_path = _write_json(tmp_path / "historical.json", historical)
    current_path = _write_json(tmp_path / "current.json", current)
    current_blob = guard._git_blob_sha(current_path)
    historical_blob = guard._git_blob_sha(historical_path)
    recovery = _recovery(current_blob, historical_blob, author="someone-else")
    recovery_path = _write_json(tmp_path / "recovery.json", recovery)
    _install(
        monkeypatch,
        guard,
        current_path=current_path,
        historical_path=historical_path,
        recovery=recovery,
    )
    with pytest.raises(guard.ExecutionClaimError, match="owner|author"):
        _assert_reconcile(guard, current_path, recovery_path, current)


def test_recovery_rejects_extra_commit_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = _guard()
    historical = _claim_payload()
    current = _claim_payload(last_update="2026-09-27T00:31:00Z")
    historical_path = _write_json(tmp_path / "historical.json", historical)
    current_path = _write_json(tmp_path / "current.json", current)
    current_blob = guard._git_blob_sha(current_path)
    historical_blob = guard._git_blob_sha(historical_path)
    recovery = _recovery(current_blob, historical_blob)
    recovery_path = _write_json(tmp_path / "recovery.json", recovery)
    _install(
        monkeypatch,
        guard,
        current_path=current_path,
        historical_path=historical_path,
        recovery=recovery,
        commit_files=[MUTATED, "unexpected.txt"],
    )
    with pytest.raises(guard.ExecutionClaimError, match="changed-file|matching prior GREEN"):
        _assert_reconcile(guard, current_path, recovery_path, current)


def test_trusted_remote_guard_transports_intervening_coord_recovery() -> None:
    workflow = Path(".github/workflows/whd-remote-execution-guard.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        "intervening_coord_recovery_comment_id",
        "RG_INTERVENING_COORD_RECOVERY_COMMENT_ID",
        "WHD_INTERVENING_COORD_POSTCOMMIT_RECONCILE_V1",
        "--intervening-coord-recovery",
        "intervening-coord-recovery.json",
    ):
        assert token in workflow
