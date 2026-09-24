from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
ISSUE = 589
OLD_WORKER = "chatgpt.sol.old"
NEW_WORKER = "chatgpt.sol.new"
BRANCH = "governance/example"
BASE = "b" * 40
HEAD = "a" * 40
COMMENT_ID = 589001


def _claim(*, worker: str = OLD_WORKER, remote_qa=None):
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": worker,
        "executor_source": "chat",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T00:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "CLOSING",
        "last_update": "2026-09-24T00:00:00Z",
        "remote_qa": remote_qa,
        "next_action": "continue",
        "blocker": None,
    }


def _authority(
    *,
    requesting_worker: str = NEW_WORKER,
    previous_worker: str = OLD_WORKER,
):
    return {
        "id": COMMENT_ID,
        "created_at": "2026-09-24T00:10:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_USER_DIRECTED_TAKEOVER_V1\n"
            f"issue={ISSUE}\n"
            f"requesting_worker={requesting_worker}\n"
            f"previous_worker={previous_worker}\n"
            "executor_source=chat"
        ),
    }


def _evaluate(
    *,
    claim=None,
    requesting_worker: str = NEW_WORKER,
    authority=None,
    remote_run=None,
):
    module = importlib.import_module("tools.stale_claim_takeover")
    return module.evaluate_stale_claim_takeover(
        claim or _claim(),
        now=datetime(2026, 9, 24, 0, 20, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-24T00:00:00Z",
        remote_run=remote_run,
        stale_after_seconds=600,
        requesting_worker=requesting_worker,
        requesting_executor_source="chat",
        user_authority=authority,
    )


def _write_evidence(tmp_path: Path, result) -> Path:
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(result.to_payload()), encoding="utf-8")
    return path


def test_stale_interactive_owner_is_actionable_only_after_normal_600s_gate():
    result = _evaluate(authority=_authority())
    assert result.classification.value == "EXECUTOR_STUCK"
    assert result.actionable is True
    assert result.stale_seconds == 1200
    assert result.previous_executor_source == "chat"
    assert result.requesting_executor_source == "chat"


def test_claim_guard_accepts_owner_authorized_stale_chat_to_chat_takeover(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(_authority()), encoding="utf-8")
    evidence_path = _write_evidence(tmp_path, _evaluate(authority=_authority()))

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


def test_claim_guard_rejects_chat_to_chat_takeover_without_owner_authority(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    evidence_path = _write_evidence(tmp_path, _evaluate(authority=_authority()))

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


def test_claim_guard_rejects_interactive_self_takeover_even_with_owner_authority(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(_claim()), encoding="utf-8")
    authority = _authority(
        requesting_worker=OLD_WORKER,
        previous_worker=OLD_WORKER,
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    evidence_path = _write_evidence(
        tmp_path,
        _evaluate(
            requesting_worker=OLD_WORKER,
            authority=authority,
        ),
    )

    with pytest.raises(guard.ExecutionClaimError, match="distinct requesting worker"):
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


def test_active_exact_run_still_blocks_interactive_owner_takeover():
    claim = _claim(remote_qa={"run_id": 77, "head_sha": HEAD})
    remote = {
        "found": True,
        "run_id": 77,
        "head_sha": HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-24T00:19:00Z",
    }
    result = _evaluate(
        claim=claim,
        authority=_authority(),
        remote_run=remote,
    )
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False
