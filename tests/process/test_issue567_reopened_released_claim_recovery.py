from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ISSUE = 567
REOPENED_ISSUE = 558
BASE = "75eaffac799d0dcf164a135591ec00754969fcc6"
HEAD = "df756e8c5a0b5143bd7a2062a080a80dc98dbee0"
BRANCH = "fix/issue558-post-commit-claim-head-reconcile-20260923"
WORKER = "scheduler.6ab13f881c34819180cee63f5dd9446b"
CLAIM_PATH = f".dispatch/claims/issue-{REOPENED_ISSUE}.json"


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _released_claim(tmp_path: Path) -> Path:
    path = tmp_path / "claim.json"
    path.write_text(
        json.dumps(
            {
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
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_ordinary_write_stays_fail_closed_for_released_claim(tmp_path: Path) -> None:
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
            changed_files=(CLAIM_PATH,),
        )


def test_reopened_process_repair_requires_dedicated_claim_reactivation_action() -> None:
    guard = _guard()

    assert "claim-reactivate" in guard.ALLOWED_ACTIONS, (
        "RED #567: reopened invalid-finalization repair has no machine-authorized "
        "way to transition the exact old RELEASED claim back into an active repair state"
    )
