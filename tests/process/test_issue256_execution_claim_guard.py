from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/execution_claim_guard.py"
DISPATCH_SKILL = ROOT / ".agents/skills/engineering/派工/SKILL.md"
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/execution_claim_hard_gate_pitfall.md"


def _load_guard():
    assert GUARD.is_file(), "#256 requires tools/execution_claim_guard.py"
    spec = importlib.util.spec_from_file_location("execution_claim_guard_issue256", GUARD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(**overrides):
    payload = {
        "issue": 256,
        "issue_url": "https://github.com/looaeedr/whd/issues/256",
        "worker": "chatgpt",
        "work_branch": "fix/issue256-execution-claim-hard-gate-20260914",
        "claimed_at": "2026-09-14T15:23:10Z",
        "base_sha": "e0a82f28f4ce3204c9fae56326f34f1a0964851f",
        "head_sha": "e0a82f28f4ce3204c9fae56326f34f1a0964851f",
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-14T15:23:10Z",
        "remote_qa": None,
        "next_action": "continue",
        "blocker": None,
    }
    payload.update(overrides)
    return payload


def _write_claim(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "claim.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_owner_on_claimed_branch_is_allowed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    claim = guard.assert_execution_claim(
        path,
        issue=256,
        worker="chatgpt",
        branch="fix/issue256-execution-claim-hard-gate-20260914",
        action="write",
    )
    assert claim.worker == "chatgpt"
    assert claim.work_branch == "fix/issue256-execution-claim-hard-gate-20260914"


def test_missing_claim_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    with pytest.raises(guard.ExecutionClaimError, match="not found|missing"):
        guard.assert_execution_claim(
            tmp_path / "missing.json",
            issue=256,
            worker="chatgpt",
            branch="fix/issue256-execution-claim-hard-gate-20260914",
            action="write",
        )


def test_competing_worker_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    with pytest.raises(guard.ExecutionClaimError, match="owner|worker"):
        guard.assert_execution_claim(
            path,
            issue=256,
            worker="other-worker",
            branch="fix/issue256-execution-claim-hard-gate-20260914",
            action="write",
        )


def test_competing_branch_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim())
    with pytest.raises(guard.ExecutionClaimError, match="branch"):
        guard.assert_execution_claim(
            path,
            issue=256,
            worker="chatgpt",
            branch="fix/competing-issue256-branch",
            action="qa-dispatch",
        )


def test_explicit_delegated_qa_branch_is_allowed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(
        tmp_path,
        _claim(delegated_branches=["qa/issue256-focused-20260914"]),
    )
    claim = guard.assert_execution_claim(
        path,
        issue=256,
        worker="chatgpt",
        branch="qa/issue256-focused-20260914",
        action="qa-dispatch",
    )
    assert "qa/issue256-focused-20260914" in claim.delegated_branches


def test_issue_or_url_mismatch_is_rejected(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, _claim(issue=255))
    with pytest.raises(guard.ExecutionClaimError, match="issue"):
        guard.assert_execution_claim(
            path,
            issue=256,
            worker="chatgpt",
            branch="fix/issue256-execution-claim-hard-gate-20260914",
            action="branch-create",
        )


def test_malformed_claim_fails_closed(tmp_path: Path) -> None:
    guard = _load_guard()
    path = _write_claim(tmp_path, {"issue": 256, "worker": "chatgpt"})
    with pytest.raises(guard.ExecutionClaimError, match="missing|required|malformed"):
        guard.assert_execution_claim(
            path,
            issue=256,
            worker="chatgpt",
            branch="fix/issue256-execution-claim-hard-gate-20260914",
            action="write",
        )


def test_dispatch_skill_requires_executable_prewrite_gate() -> None:
    text = DISPATCH_SKILL.read_text(encoding="utf-8")
    assert "EXECUTION_CLAIM_PREWRITE_HARD_GATE" in text
    assert "tools/execution_claim_guard.py" in text
    assert "branch-create" in text
    assert "qa-dispatch" in text


def test_ai_pitfall_records_claim_acquisition_is_not_enough() -> None:
    assert PITFALL.is_file()
    text = PITFALL.read_text(encoding="utf-8")
    assert "atomic claim" in text.lower()
    assert "pre-write" in text.lower() or "prewrite" in text.lower()
    assert "非 owner" in text or "non-owner" in text.lower()
