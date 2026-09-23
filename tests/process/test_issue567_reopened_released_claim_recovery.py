from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

REOPENED_ISSUE = 558
BLOCKING_REPAIR_ISSUE = 560
BASE = "75eaffac799d0dcf164a135591ec00754969fcc6"
HEAD = "df756e8c5a0b5143bd7a2062a080a80dc98dbee0"
BRANCH = "fix/issue558-post-commit-claim-head-reconcile-20260923"
WORKER = "scheduler.6ab13f881c34819180cee63f5dd9446b"
CLAIM_PATH = f".dispatch/claims/issue-{REOPENED_ISSUE}.json"


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _released_claim(tmp_path: Path, **overrides) -> Path:
    payload = {
        "issue": REOPENED_ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{REOPENED_ISSUE}",
        "worker": WORKER,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-23T22:25:30+08:00",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "RELEASED",
        "last_update": "2026-09-23T23:23:59+08:00",
        "next_action": None,
        "blocker": None,
    }
    payload.update(overrides)
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _pointer_comment() -> dict:
    return {
        "id": 5797793861,
        "user": {"login": "looaeedr"},
        "body": "\n".join(
            [
                "WHD_PROCESS_RECOVERY_POINTER_V1",
                "process_state=REOPENED_INVALID_FINALIZATION_EVIDENCE",
                f"blocking_repair_issue={BLOCKING_REPAIR_ISSUE}",
                "resume_condition=TRUSTED_REMOTE_FINALIZATION_EXECUTOR_INTEGRATED",
                "resume_action=RUN_MACHINE_FINALIZATION_PROOF_THEN_CLOSE_READBACK_RELEASE",
            ]
        ),
    }


def _install_recovery_evidence(monkeypatch, guard, *, comments=None) -> None:
    def fake_issue(issue: int) -> dict:
        if issue == REOPENED_ISSUE:
            return {"number": issue, "state": "open", "state_reason": "reopened"}
        if issue == BLOCKING_REPAIR_ISSUE:
            return {
                "number": issue,
                "state": "open",
                "body": (
                    "Trusted remote finalization executor repair for #558. "
                    "Machine proof must replace marker-only finalization."
                ),
            }
        raise AssertionError(f"unexpected issue lookup: {issue}")

    monkeypatch.setattr(guard, "_github_issue", fake_issue)
    monkeypatch.setattr(
        guard,
        "_github_issue_comments",
        lambda issue: list([_pointer_comment()] if comments is None else comments),
    )
    monkeypatch.setattr(
        guard,
        "_github_api_json",
        lambda path: {
            "type": "file",
            "sha": "d" * 40,
            "path": ".github/workflows/whd-remote-finalization.yml",
        },
    )


def test_ordinary_released_claim_write_stays_fail_closed(tmp_path: Path) -> None:
    guard = _guard()
    claim = _released_claim(tmp_path)

    with pytest.raises(guard.ExecutionClaimError, match="inactive.*RELEASED"):
        guard.assert_execution_claim(
            claim,
            issue=REOPENED_ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            changed_files=("tools/example.py",),
        )


def test_reopened_invalid_finalization_can_reactivate_only_exact_claim_path(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _guard()
    claim_path = _released_claim(tmp_path)
    _install_recovery_evidence(monkeypatch, guard)

    claim = guard.assert_execution_claim(
        claim_path,
        issue=REOPENED_ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="write",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
        changed_files=(CLAIM_PATH,),
    )

    assert claim.phase == "RELEASED"
    assert claim.worker == WORKER


def test_reactivation_rejects_missing_process_recovery_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _guard()
    claim_path = _released_claim(tmp_path)
    _install_recovery_evidence(monkeypatch, guard, comments=[])

    with pytest.raises(guard.ExecutionClaimError, match="PROCESS_RECOVERY_POINTER"):
        guard.assert_execution_claim(
            claim_path,
            issue=REOPENED_ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            changed_files=(CLAIM_PATH,),
        )


def test_reactivation_rejects_non_scheduler_released_claim(
    tmp_path: Path, monkeypatch
) -> None:
    guard = _guard()
    claim_path = _released_claim(
        tmp_path,
        worker="chatgpt.sol260923.issue558",
        executor_source="chatgpt_interactive",
    )
    _install_recovery_evidence(monkeypatch, guard)

    with pytest.raises(guard.ExecutionClaimError, match="scheduler-owned"):
        guard.assert_execution_claim(
            claim_path,
            issue=REOPENED_ISSUE,
            worker="chatgpt.sol260923.issue558",
            branch=BRANCH,
            action="write",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            changed_files=(CLAIM_PATH,),
        )
