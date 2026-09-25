from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"

ISSUE = 657
BRANCH = "integration/issue657-main-remote-guard-20260925"
BASE_SHA = "bdb3da203c898d43898b092ff37b7fa9e0c93061"
HEAD_SHA = "53184c28ed1041558cd735817f4aae54f6c3af74"


def _load_guard():
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue660", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim():
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": "chatgpt.sol260925.issue657.a1",
        "executor_source": "chatgpt_interactive",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-25T10:56:55Z",
        "base_sha": BASE_SHA,
        "head_sha": HEAD_SHA,
        "phase": "CLOSING",
        "last_update": "2026-09-25T11:06:00Z",
        "next_action": "finish closure",
        "blocker": None,
    }


def _checkpoint(*, state="TERMINAL_SUCCESS", closure_state="FINALIZATION_PENDING"):
    return {
        "version": 1,
        "issue": str(ISSUE),
        "branch": BRANCH,
        "head_sha": HEAD_SHA,
        "state": state,
        "next_action": None,
        "run_id": None,
        "job_id": None,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": [],
        "closure_state": closure_state,
        "closure_next_action": "continue closure",
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "closure_state",
    ["FINALIZATION_PENDING", "ISSUE_CLOSE_PENDING", "RELEASE_HANDOFF_PENDING"],
)
@pytest.mark.parametrize("state", ["TERMINAL_SUCCESS", "TERMINAL_FAILURE"])
def test_terminal_checkpoint_pending_closure_allows_claim_takeover(
    tmp_path: Path,
    state: str,
    closure_state: str,
) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    checkpoint_path = _write(
        tmp_path / "checkpoint.json",
        _checkpoint(state=state, closure_state=closure_state),
    )
    claim = guard.load_execution_claim(claim_path)

    checkpoint = guard.assert_execution_claim_checkpoint_prewrite(
        claim,
        checkpoint_path,
        action="claim-takeover",
        changed_files=(),
    )

    assert getattr(checkpoint.state, "value", str(checkpoint.state)) == state
    assert getattr(
        checkpoint.closure_state,
        "value",
        str(checkpoint.closure_state),
    ) == closure_state


def test_closed_terminal_checkpoint_still_rejects_claim_takeover(tmp_path: Path) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    checkpoint_path = _write(
        tmp_path / "checkpoint.json",
        _checkpoint(closure_state="CLOSED"),
    )
    claim = guard.load_execution_claim(claim_path)

    with pytest.raises(
        guard.ExecutionClaimError,
        match="terminal checkpoint takeover requires pending closure",
    ):
        guard.assert_execution_claim_checkpoint_prewrite(
            claim,
            checkpoint_path,
            action="claim-takeover",
            changed_files=(),
        )


def test_terminal_checkpoint_takeover_never_accepts_file_mutation(tmp_path: Path) -> None:
    guard = _load_guard()
    claim_path = _write(tmp_path / "claim.json", _claim())
    checkpoint_path = _write(tmp_path / "checkpoint.json", _checkpoint())
    claim = guard.load_execution_claim(claim_path)

    with pytest.raises(
        guard.ExecutionClaimError,
        match="must not mutate repository files",
    ):
        guard.assert_execution_claim_checkpoint_prewrite(
            claim,
            checkpoint_path,
            action="claim-takeover",
            changed_files=("tools/example.py",),
        )
