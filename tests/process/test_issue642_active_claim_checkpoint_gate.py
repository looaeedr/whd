from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "execution_claim_guard.py"

BASE_SHA = "e0a82f28f4ce3204c9fae56326f34f1a0964851f"
HEAD_SHA = "6c1189a1b991bad2c953a5fbc95f0acda903b5d5"
WORK_BRANCH = "fix/issue256-execution-claim-hard-gate-20260914"


def _load_guard():
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue642", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(**overrides):
    payload = {
        "issue": 256,
        "issue_url": "https://github.com/looaeedr/whd/issues/256",
        "worker": "chatgpt",
        "work_branch": WORK_BRANCH,
        "claimed_at": "2026-09-14T15:23:10Z",
        "base_sha": BASE_SHA,
        "head_sha": HEAD_SHA,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-14T22:29:31Z",
        "remote_qa": None,
        "next_action": "continue",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _checkpoint(**overrides):
    payload = {
        "version": 1,
        "issue": "256",
        "branch": WORK_BRANCH,
        "head_sha": HEAD_SHA,
        "state": "RUNNING",
        "next_action": "continue",
        "run_id": None,
        "job_id": None,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": [],
        "master_issue": None,
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "chain_reason": None,
        "closure_state": "CLOSED",
        "closure_next_action": None,
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_active_claim_missing_checkpoint_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    gate = getattr(guard, "assert_active_claim_requires_checkpoint", None)
    assert callable(gate), (
        "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: canonical machine gate is missing"
    )
    claim_path = _write_json(tmp_path / "claim.json", _claim())
    claim = guard.load_execution_claim(claim_path)

    with pytest.raises(
        guard.ExecutionClaimError,
        match="ACTIVE_CLAIM_REQUIRES_CHECKPOINT",
    ):
        gate(claim, tmp_path / "missing-checkpoint.json")


def test_active_claim_exact_checkpoint_passes(tmp_path: Path) -> None:
    guard = _load_guard()
    gate = getattr(guard, "assert_active_claim_requires_checkpoint", None)
    assert callable(gate), (
        "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: canonical machine gate is missing"
    )
    claim_path = _write_json(tmp_path / "claim.json", _claim())
    checkpoint_path = _write_json(tmp_path / "checkpoint.json", _checkpoint())
    claim = guard.load_execution_claim(claim_path)

    checkpoint = gate(claim, checkpoint_path)

    assert checkpoint.issue == "256"
    assert checkpoint.branch == WORK_BRANCH
    assert checkpoint.head_sha == HEAD_SHA


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issue", "999"),
        ("branch", "work/other-branch"),
        ("head_sha", "0" * 40),
    ],
)
def test_active_claim_checkpoint_identity_mismatch_fails_closed(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    guard = _load_guard()
    gate = getattr(guard, "assert_active_claim_requires_checkpoint", None)
    assert callable(gate), (
        "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: canonical machine gate is missing"
    )
    claim_path = _write_json(tmp_path / "claim.json", _claim())
    checkpoint_path = _write_json(
        tmp_path / "checkpoint.json",
        _checkpoint(**{field: value}),
    )
    claim = guard.load_execution_claim(claim_path)

    with pytest.raises(
        guard.ExecutionClaimError,
        match="ACTIVE_CLAIM_REQUIRES_CHECKPOINT",
    ):
        gate(claim, checkpoint_path)


def test_cli_requires_checkpoint_and_accepts_exact_checkpoint(tmp_path: Path) -> None:
    claim_path = _write_json(tmp_path / "claim.json", _claim())
    checkpoint_path = _write_json(tmp_path / "checkpoint.json", _checkpoint())
    common = [
        sys.executable,
        str(GUARD),
        "--claim",
        str(claim_path),
        "--issue",
        "256",
        "--worker",
        "chatgpt",
        "--branch",
        WORK_BRANCH,
        "--action",
        "write",
        "--base-sha",
        BASE_SHA,
        "--head-sha",
        HEAD_SHA,
        "--changed-file",
        "tools/example.py",
    ]

    missing = subprocess.run(
        common,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2
    assert "checkpoint" in (missing.stdout + missing.stderr).lower(), (
        "ACTIVE_CLAIM_REQUIRES_CHECKPOINT: CLI did not require checkpoint"
    )

    exact = subprocess.run(
        [*common, "--checkpoint", str(checkpoint_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert exact.returncode == 0, exact.stdout + exact.stderr
    assert "EXECUTION_CLAIM_GUARD_GREEN" in exact.stdout
