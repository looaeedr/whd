from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 534
OLD_WORKER = "scheduler.6ab13fa557fc8191935c671214b865e2"
NEW_WORKER = "chatgpt.sol260924.issue534"
BRANCH = "work/issue520-phase6-bridge-residual-reduction-20260923"
BASE = "b" * 40
HEAD = "a" * 40
COMMENT_ID = 123456


def _claim():
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": OLD_WORKER,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T06:00:00+08:00",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "RECOVERING",
        "last_update": "2026-09-24T06:00:00+08:00",
        "next_action": "repair",
        "blocker": None,
    }


def _authority():
    return {
        "id": COMMENT_ID,
        "created_at": "2026-09-24T00:00:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_USER_DIRECTED_TAKEOVER_V1\n"
            f"issue={ISSUE}\n"
            f"requesting_worker={NEW_WORKER}\n"
            f"previous_worker={OLD_WORKER}\n"
            "executor_source=chat"
        ),
    }


def _evaluate(*, authority=None):
    module = importlib.import_module("tools.stale_claim_takeover")
    return module.evaluate_stale_claim_takeover(
        _claim(),
        now=datetime(2026, 9, 24, 0, 20, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-23T23:00:00Z",
        stale_after_seconds=600,
        requesting_worker=NEW_WORKER,
        requesting_executor_source="chat",
        user_authority=authority,
    )


def test_interactive_takeover_without_owner_authority_fails_closed():
    with pytest.raises(Exception, match="authority"):
        _evaluate()


def test_explicit_owner_directed_interactive_takeover_is_actionable():
    result = _evaluate(authority=_authority())
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.previous_worker == OLD_WORKER
    assert result.requesting_worker == NEW_WORKER
    assert result.requesting_executor_source == "chat"
    assert result.user_authority_comment_id == COMMENT_ID


def test_active_exact_run_still_blocks_user_directed_takeover():
    module = importlib.import_module("tools.stale_claim_takeover")
    claim = _claim()
    claim["remote_qa"] = {"run_id": 999, "head_sha": HEAD}
    remote = {
        "found": True,
        "run_id": 999,
        "head_sha": HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-24T00:19:00Z",
    }
    result = module.evaluate_stale_claim_takeover(
        claim,
        now=datetime(2026, 9, 24, 0, 20, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-23T23:00:00Z",
        remote_run=remote,
        stale_after_seconds=600,
        requesting_worker=NEW_WORKER,
        requesting_executor_source="chat",
        user_authority=_authority(),
    )
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_claim_guard_requires_and_accepts_same_owner_authority(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(_authority()), encoding="utf-8")
    result = _evaluate(authority=_authority())
    evidence_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(result.to_payload()), encoding="utf-8")

    with pytest.raises(guard.ExecutionClaimError, match="authority"):
        guard.assert_execution_claim(
            claim_path,
            issue=ISSUE,
            worker=OLD_WORKER,
            branch=BRANCH,
            action="claim-takeover",
            expected_base_sha=BASE,
            expected_head_sha=HEAD,
            takeover_evidence=evidence_path,
        )

    claimed = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=OLD_WORKER,
        branch=BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
        takeover_evidence=evidence_path,
        user_authority_evidence=authority_path,
    )
    assert claimed.worker == OLD_WORKER
