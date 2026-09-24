from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 578
OLD_WORKER = "chatgpt.sol260924.issue578.recovery"
NEW_WORKER = "chatgpt.sol260924.issue578.final"
BRANCH = "governance/issue578-scheduler-runtime-liveness-20260924"
BASE = "b" * 40
HEAD = "a" * 40
COMMENT_ID = 598001


def _claim(*, remote_qa=None):
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": OLD_WORKER,
        "executor_source": "chat",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T00:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "E2E_WAITING",
        "last_update": "2026-09-24T00:00:00Z",
        "remote_qa": remote_qa,
        "next_action": "finalize",
        "blocker": None,
    }


def _authority(*, requesting_worker: str = NEW_WORKER):
    return {
        "id": COMMENT_ID,
        "created_at": "2026-09-24T00:10:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_USER_DIRECTED_TAKEOVER_V1\n"
            f"issue={ISSUE}\n"
            f"requesting_worker={requesting_worker}\n"
            f"previous_worker={OLD_WORKER}\n"
            "executor_source=chat"
        ),
    }


def _evaluate(*, authority=None, remote_run=None, requesting_worker=NEW_WORKER,
              requesting_source="chat"):
    module = importlib.import_module("tools.stale_claim_takeover")
    return module.evaluate_stale_claim_takeover(
        _claim(remote_qa=(
            {"run_id": 77, "head_sha": HEAD} if remote_run is not None else None
        )),
        now=datetime(2026, 9, 24, 0, 20, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-24T00:00:00Z",
        remote_run=remote_run,
        stale_after_seconds=600,
        requesting_worker=requesting_worker,
        requesting_executor_source=requesting_source,
        user_authority=authority,
    )


def test_unknown_phase_explicit_user_directed_chat_takeover_is_actionable():
    result = _evaluate(authority=_authority())
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.stale_seconds == 1200
    assert result.claim_phase == "E2E_WAITING"
    assert result.previous_worker == OLD_WORKER
    assert result.requesting_worker == NEW_WORKER
    assert result.user_authority_comment_id == COMMENT_ID


def test_unknown_phase_takeover_without_user_authority_fails_closed():
    with pytest.raises(Exception, match="authority|unknown claim phase"):
        _evaluate(authority=None)


def test_unknown_phase_scheduler_requester_cannot_use_interactive_recovery_path():
    module = importlib.import_module("tools.stale_claim_takeover")
    with pytest.raises(module.StaleTakeoverError, match="unknown claim phase"):
        module.evaluate_stale_claim_takeover(
            _claim(),
            now=datetime(2026, 9, 24, 0, 20, tzinfo=UTC),
            live_head_sha=HEAD,
            live_head_committed_at="2026-09-24T00:00:00Z",
            stale_after_seconds=600,
            requesting_worker="scheduler.requester",
            requesting_executor_source="scheduler",
        )


def test_unknown_phase_active_exact_run_remains_absolute_lock():
    remote = {
        "found": True,
        "run_id": 77,
        "head_sha": HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-24T00:19:00Z",
    }
    result = _evaluate(authority=_authority(), remote_run=remote)
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_claim_guard_accepts_exact_user_directed_invalid_phase_takeover(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(_authority()), encoding="utf-8")
    decision = _evaluate(authority=_authority())
    evidence_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(decision.to_payload()), encoding="utf-8")

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
    assert claimed.phase == "E2E_WAITING"
    assert claimed.worker == OLD_WORKER


def test_claim_guard_invalid_phase_takeover_requires_user_authority_file(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    decision = _evaluate(authority=_authority())
    evidence_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(decision.to_payload()), encoding="utf-8")

    with pytest.raises(guard.ExecutionClaimError, match="unknown phase"):
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


def test_claim_guard_rejects_scheduler_evidence_for_invalid_phase(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(_authority()), encoding="utf-8")
    decision = _evaluate(authority=_authority()).to_payload()
    decision["requesting_worker"] = "scheduler.requester"
    decision["requesting_executor_source"] = "scheduler"
    decision["user_authority_comment_id"] = None
    evidence_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(decision), encoding="utf-8")

    with pytest.raises(
        guard.ExecutionClaimError,
        match="invalid-phase claim-takeover requires",
    ):
        guard.assert_execution_claim(
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
