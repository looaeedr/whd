from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

UTC = timezone.utc
CURRENT_LANE = "scheduler.6ab13f881c34819180cee63f5dd9446b"
SIBLING_LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
ISSUE = 578
BRANCH = "work/example"
BASE = "b" * 40
HEAD = "a" * 40
CLAIM_BLOB = "c" * 40


def _module():
    return importlib.import_module("tools.stale_claim_takeover")


def _claim(*, worker=SIBLING_LANE, source="scheduler", last_update="2026-09-24T00:02:00Z", remote_qa=None):
    return {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": worker,
        "executor_source": source,
        "work_branch": BRANCH,
        "claimed_at": "2026-09-24T00:00:00Z",
        "base_sha": BASE,
        "head_sha": HEAD,
        "phase": "IMPLEMENTING",
        "last_update": last_update,
        "remote_qa": remote_qa,
        "next_action": "continue",
        "blocker": None,
    }


def _heartbeat(*, lane=SIBLING_LANE, claim_blob=CLAIM_BLOB, branch=BRANCH, head=HEAD,
               emitted_at="2026-09-24T00:00:00Z", expires_at="2026-09-24T00:03:00Z",
               invocation_identity="invocation.sibling.1", active_run_id=None, active_run_head_sha=None):
    return {
        "schema": "WHD_SCHEDULER_RUNTIME_LIVENESS_V1",
        "issue": ISSUE,
        "scheduler_lane": lane,
        "invocation_identity": invocation_identity,
        "claim_blob_sha": claim_blob,
        "branch": branch,
        "head_sha": head,
        "executor_source": "scheduler",
        "emitted_at": emitted_at,
        "expires_at": expires_at,
        "active_run_id": active_run_id,
        "active_run_head_sha": active_run_head_sha,
    }


def _evaluate(
    *,
    claim=None,
    now=None,
    heartbeat=None,
    remote_run=None,
    requester=CURRENT_LANE,
    live_commit_at="2026-09-24T00:00:00Z",
    claim_blob=CLAIM_BLOB,
):
    return _module().evaluate_stale_claim_takeover(
        claim or _claim(),
        now=now or datetime(2026, 9, 24, 0, 5, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at=live_commit_at,
        remote_run=remote_run,
        stale_after_seconds=600,
        requesting_worker=requester,
        requesting_executor_source="scheduler",
        claim_blob_sha=claim_blob,
        runtime_liveness=heartbeat,
        orphan_grace_seconds=90,
    )


def test_expired_scheduler_heartbeat_makes_recent_foreign_owner_actionable():
    result = _evaluate(heartbeat=_heartbeat())
    assert result.classification.value == "ORPHANED_SCHEDULER_OWNER"
    assert result.actionable is True
    assert result.stale_seconds == 180
    assert result.orphan_grace_seconds == 90
    assert result.runtime_liveness_status == "EXPIRED"
    assert result.runtime_invocation_identity == "invocation.sibling.1"
    assert result.claim_blob_sha == CLAIM_BLOB


def test_missing_scheduler_heartbeat_becomes_orphaned_after_grace_without_waiting_600s():
    result = _evaluate(heartbeat=None)
    assert result.classification.value == "ORPHANED_SCHEDULER_OWNER"
    assert result.actionable is True
    assert result.stale_seconds == 180
    assert result.runtime_liveness_status == "MISSING"


def test_valid_scheduler_heartbeat_blocks_foreign_sibling_even_when_progress_is_old():
    result = _evaluate(
        claim=_claim(last_update="2026-09-23T23:30:00Z"),
        heartbeat=_heartbeat(
            emitted_at="2026-09-24T00:04:00Z",
            expires_at="2026-09-24T00:06:00Z",
        ),
    )
    assert result.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert result.actionable is False
    assert result.runtime_liveness_status == "ACTIVE"


def test_active_exact_run_remains_absolute_lock_even_if_heartbeat_expired():
    claim = _claim(remote_qa={"run_id": 77, "head_sha": HEAD})
    remote = {
        "found": True,
        "run_id": 77,
        "head_sha": HEAD,
        "status": "in_progress",
        "conclusion": None,
        "updated_at": "2026-09-24T00:04:30Z",
    }
    result = _evaluate(claim=claim, heartbeat=_heartbeat(), remote_run=remote)
    assert result.classification.value == "RUN_LIVE"
    assert result.actionable is False


def test_same_lane_cross_cycle_resume_never_self_takeovers():
    claim = _claim(worker=CURRENT_LANE)
    result = _evaluate(claim=claim, heartbeat=None, requester=CURRENT_LANE)
    assert result.classification.value == "ALREADY_SCHEDULER"
    assert result.actionable is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_blob_sha", "d" * 40),
        ("branch", "other/branch"),
        ("head_sha", "e" * 40),
        ("scheduler_lane", CURRENT_LANE),
        ("executor_source", "chat"),
    ],
)
def test_scheduler_heartbeat_identity_drift_fails_closed(field, value):
    heartbeat = _heartbeat()
    heartbeat[field] = value
    with pytest.raises(Exception, match="runtime liveness|heartbeat|claim blob|branch|head|lane|executor"):
        _evaluate(heartbeat=heartbeat)


def test_ordinary_foreign_owner_keeps_existing_600_second_threshold():
    recent = _evaluate(
        claim=_claim(
            worker="chatgpt.other",
            source="chat",
            last_update="2026-09-24T00:00:30Z",
        ),
        heartbeat=None,
    )
    assert recent.classification.value == "WAIT_ON_FOREIGN_RUNTIME"
    assert recent.actionable is False

    stale = _evaluate(
        claim=_claim(
            worker="chatgpt.other",
            source="chat",
            last_update="2026-09-23T23:50:00Z",
        ),
        heartbeat=None,
        live_commit_at="2026-09-23T23:50:00Z",
    )
    assert stale.classification.value == "EXECUTOR_STUCK"
    assert stale.actionable is True


def test_claim_guard_accepts_orphaned_scheduler_evidence_below_600_seconds(tmp_path: Path):
    guard = importlib.import_module("tools.execution_claim_guard")
    claim = _claim()
    claim_path = tmp_path / "claim.json"
    claim_path.write_text(json.dumps(claim), encoding="utf-8")

    actual_claim_blob = guard._git_blob_sha(claim_path)
    result = _evaluate(
        heartbeat=_heartbeat(claim_blob=actual_claim_blob),
        claim_blob=actual_claim_blob,
    )
    evidence_path = tmp_path / "decision.json"
    evidence_path.write_text(json.dumps(result.to_payload()), encoding="utf-8")

    claimed = guard.assert_execution_claim(
        claim_path,
        issue=ISSUE,
        worker=SIBLING_LANE,
        branch=BRANCH,
        action="claim-takeover",
        expected_base_sha=BASE,
        expected_head_sha=HEAD,
        takeover_evidence=evidence_path,
    )
    assert claimed.worker == SIBLING_LANE


def _liveness_selector():
    return importlib.import_module("tools.scheduler_runtime_liveness")


def _liveness_comment(
    *,
    comment_id: int = 100,
    lane: str = SIBLING_LANE,
    issue: int = ISSUE,
    user: str = "looaeedr",
    emitted_at: str = "2026-09-24T00:01:00Z",
    expires_at: str = "2026-09-24T00:04:00Z",
):
    return {
        "id": comment_id,
        "created_at": emitted_at,
        "user": {"login": user},
        "body": (
            "WHD_SCHEDULER_RUNTIME_LIVENESS_V1\n"
            f"issue={issue}\n"
            f"scheduler_lane={lane}\n"
            f"invocation_identity=invocation.{comment_id}\n"
            f"claim_blob_sha={CLAIM_BLOB}\n"
            f"branch={BRANCH}\n"
            f"head_sha={HEAD}\n"
            "executor_source=scheduler\n"
            f"emitted_at={emitted_at}\n"
            f"expires_at={expires_at}"
        ),
    }


def test_runtime_liveness_selector_chooses_latest_owner_authored_matching_lane():
    selector = _liveness_selector()
    selected = selector.select_runtime_liveness_comment(
        [
            _liveness_comment(comment_id=100),
            _liveness_comment(comment_id=101, user="github-actions[bot]"),
            _liveness_comment(comment_id=102, lane=CURRENT_LANE),
            _liveness_comment(
                comment_id=103,
                emitted_at="2026-09-24T00:02:00Z",
                expires_at="2026-09-24T00:05:00Z",
            ),
        ],
        issue=ISSUE,
        scheduler_lane=SIBLING_LANE,
    )
    assert selected is not None
    assert selected["schema"] == "WHD_SCHEDULER_RUNTIME_LIVENESS_V1"
    assert selected["source_comment_id"] == 103
    assert selected["scheduler_lane"] == SIBLING_LANE


def test_runtime_liveness_selector_missing_is_not_fake_liveness():
    selector = _liveness_selector()
    selected = selector.select_runtime_liveness_comment(
        [_liveness_comment(comment_id=100, lane=CURRENT_LANE)],
        issue=ISSUE,
        scheduler_lane=SIBLING_LANE,
    )
    assert selected is None


def test_runtime_liveness_selector_malformed_relevant_comment_fails_closed():
    selector = _liveness_selector()
    comment = _liveness_comment()
    comment["body"] = comment["body"].replace(
        f"head_sha={HEAD}", "head_sha=not-a-sha"
    )
    with pytest.raises(
        selector.RuntimeLivenessCommentError,
        match="head_sha|runtime liveness",
    ):
        selector.select_runtime_liveness_comment(
            [comment],
            issue=ISSUE,
            scheduler_lane=SIBLING_LANE,
        )
