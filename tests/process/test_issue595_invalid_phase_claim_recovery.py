from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ISSUE = 578
WORKER = "chatgpt.sol260924.issue578.recovery"
BRANCH = "governance/issue578-scheduler-runtime-liveness-20260924"
BASE = "b" * 40
HEAD = "a" * 40
CLAIM_PATH = f".dispatch/claims/issue-{ISSUE}.json"


def _guard():
    return importlib.import_module("tools.execution_claim_guard")


def _payload(*, phase: str = "E2E_WAITING"):
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": WORKER,
        "executor_source": "chat",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T05:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": phase,
        "last_update": "2026-09-24T05:00:00Z",
        "delegated_branches": [],
        "next_action": "normalize",
        "blocker": None,
    }


def _write_claim(tmp_path: Path, **kwargs) -> Path:
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(_payload(**kwargs)), encoding="utf-8")
    return path


def test_unknown_phase_allows_only_exact_same_claim_write_recovery(tmp_path: Path):
    guard = _guard()
    claim = guard.assert_execution_claim(
        _write_claim(tmp_path),
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="write",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
        changed_files=(CLAIM_PATH,),
    )
    assert claim.phase == "E2E_WAITING"


@pytest.mark.parametrize(
    ("action", "changed_files"),
    [
        ("commit", (CLAIM_PATH,)),
        ("write", ("docs/example.md",)),
        ("pr-write", ()),
    ],
)
def test_unknown_phase_stays_fail_closed_outside_exact_claim_write(
    tmp_path: Path, action: str, changed_files: tuple[str, ...]
):
    guard = _guard()
    with pytest.raises(guard.ExecutionClaimError, match="unknown phase"):
        guard.assert_execution_claim(
            _write_claim(tmp_path),
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action=action,
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            changed_files=changed_files,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("worker", "chatgpt.other", "worker is not claim owner"),
        ("branch", "other/branch", "branch is not authorized"),
        ("base", "c" * 40, "base SHA mismatch"),
    ],
)
def test_unknown_phase_recovery_keeps_identity_gates(
    tmp_path: Path, field: str, value: str, message: str
):
    guard = _guard()
    kwargs = dict(
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="write",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
        changed_files=(CLAIM_PATH,),
    )
    if field == "worker":
        kwargs["worker"] = value
    elif field == "branch":
        kwargs["branch"] = value
    else:
        kwargs["expected_base_sha"] = value
    with pytest.raises(guard.ExecutionClaimError, match=message):
        guard.assert_execution_claim(_write_claim(tmp_path), **kwargs)


def test_terminal_released_semantics_are_not_generalized(tmp_path: Path):
    guard = _guard()
    path = _write_claim(tmp_path, phase="RELEASED")
    with pytest.raises(guard.ExecutionClaimError):
        guard.assert_execution_claim(
            path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="commit",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            changed_files=(CLAIM_PATH,),
        )
