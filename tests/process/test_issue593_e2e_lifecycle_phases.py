from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
PHASES = ("E2E_OWNER", "E2E_TAKEN_OVER", "E2E_PROVEN")
ISSUE = 592
WORKER = "scheduler.owner"
BRANCH = "governance/issue592-sibling-orphan-e2e-20260924"
BASE = "b" * 40
HEAD = "a" * 40


def _claim(phase: str):
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": WORKER,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T05:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": phase,
        "last_update": "2026-09-24T05:00:00Z",
        "next_action": "continue",
        "blocker": None,
        "remote_qa": None,
    }


@pytest.mark.parametrize("phase", PHASES)
def test_execution_claim_guard_accepts_e2e_active_phase(tmp_path: Path, phase: str):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim(phase)), encoding="utf-8")
    claimed = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=WORKER,
        branch=BRANCH,
        action="branch-create",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
    )
    assert claimed.phase == phase


@pytest.mark.parametrize("phase", PHASES)
def test_stale_takeover_evaluator_treats_e2e_phase_as_active(phase: str):
    module = importlib.import_module("tools.stale_claim_takeover")
    result = module.evaluate_stale_claim_takeover(
        _claim(phase),
        now=datetime(2026, 9, 24, 5, 20, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-24T05:00:00Z",
        requesting_worker="scheduler.requester",
        requesting_executor_source="scheduler",
        stale_after_seconds=600,
    )
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.claim_phase == phase


def test_execution_claim_guard_still_rejects_unknown_phase(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim("E2E_UNKNOWN")), encoding="utf-8")
    with pytest.raises(guard.ExecutionClaimError, match="unknown phase"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=WORKER,
            branch=BRANCH,
            action="branch-create",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
        )


def test_stale_takeover_evaluator_still_rejects_unknown_phase():
    module = importlib.import_module("tools.stale_claim_takeover")
    with pytest.raises(module.StaleTakeoverError, match="unknown claim phase"):
        module.evaluate_stale_claim_takeover(
            _claim("E2E_UNKNOWN"),
            now=datetime(2026, 9, 24, 5, 20, tzinfo=UTC),
            live_head_sha=HEAD,
            live_head_committed_at="2026-09-24T05:00:00Z",
            requesting_worker="scheduler.requester",
            requesting_executor_source="scheduler",
            stale_after_seconds=600,
        )
