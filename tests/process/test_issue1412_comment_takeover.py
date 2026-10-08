"""Issue #1412: Issue comments are the sole intervention-time clock."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from tools.issue_comment_progress import (
    COMMENT_MARKER,
    build_owner_progress_comment,
    evaluate_issue_comment_intervention,
)
from tools.execution_record import LeaseState, execution_record_from_payload
from tools.execution_scheduler_view import build_scheduler_view


LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
NOW = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)


def record(issue=1412, owner=LANE_B):
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2", "version": 2, "generation": 4,
        "issue": issue, "execution_intent": "SCHEDULER_LANE",
        "owner_kind": "SCHEDULER", "owner_id": owner, "lane_id": owner,
        "slot_id": None, "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40, "work_branch": f"work/issue-{issue}",
        "head_sha": "b" * 40, "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40, "state": "ACTIVE", "semantic_state": "ACTIVE",
        "next_action": {"kind": "APPLY_COMMIT", "args": {"candidate_commit_sha": "d" * 40},
                        "display": "continue"},
        "lease": None, "active_run": None, "transaction": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None, "closure": {"merged_sha": None, "issue_closed": False,
                                    "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [], "updated_at": "2026-10-08T07:00:00Z",
    })


def comment(record, seconds_ago, *, login="looaeedr", event="PROGRESS",
            owner=None, generation=None, issue=None, text=None):
    return {
        "user": {"login": login},
        "created_at": (NOW - timedelta(seconds=seconds_ago)).isoformat(),
        "body": text or build_owner_progress_comment(
            issue=record.issue if issue is None else issue,
            generation=record.generation if generation is None else generation,
            owner_kind=record.owner_kind,
            owner_id=record.owner_id if owner is None else owner,
            work_branch=record.work_branch, head_sha=record.head_sha,
            lane_id=record.lane_id, slot_id=record.slot_id,
            event=event, done="完成修復", work="目前執行程式與測試", next_step="測試後送出PR",
        ),
    }


@pytest.mark.parametrize(("seconds", "allowed"), [
    (0, False), (599, False), (600, False), (601, True), (1200, True),
])
def test_only_server_comment_clock_controls_intervention(seconds, allowed):
    r = record()
    result = evaluate_issue_comment_intervention(
        r, [comment(r, seconds)], now=NOW,
        trusted_authors={"looaeedr"},
    )
    assert result.eligible is allowed
    assert result.reason == ("ISSUE_COMMENT_STALE_OVER_600S" if allowed
                             else "ISSUE_COMMENT_PROTECTED_600S")


@pytest.mark.parametrize("invalid", [
    lambda r: comment(r, 601, login="outsider"),
    lambda r: comment(r, 601, owner="wrong-worker"),
    lambda r: comment(r, 601, generation=3),
    lambda r: comment(r, 601, issue=9999),
    lambda r: comment(r, 601, text="HEARTBEAT\nI am working"),
])
def test_untrusted_or_unmatched_comments_never_authorize_takeover(invalid):
    r = record()
    verdict = evaluate_issue_comment_intervention(
        r, [invalid(r)], now=NOW, trusted_authors={"looaeedr"},
    )
    assert not verdict.eligible


def test_missing_comments_fails_closed_and_newest_valid_resets_clock():
    r = record()
    assert not evaluate_issue_comment_intervention(
        r, [], now=NOW, trusted_authors={"looaeedr"},
    ).eligible
    notes = [comment(r, 700), comment(r, 20), comment(r, 900, login="outsider")]
    verdict = evaluate_issue_comment_intervention(
        r, notes, now=NOW, trusted_authors={"looaeedr"},
    )
    assert not verdict.eligible
    assert verdict.age_seconds == 20


def test_event_requires_actual_work_and_next_step():
    r = record()
    fake = comment(r, 601, text=(
        f"{COMMENT_MARKER}\nissue={r.issue}\ngeneration={r.generation}\n"
        f"owner_kind={r.owner_kind}\nowner_id={r.owner_id}\n"
        f"work_branch={r.work_branch}\nhead_sha={r.head_sha}\n"
        f"lane_id={r.lane_id}\nslot_id=NONE\n"
        "event=PROGRESS\ndone=正在處理\nwork=HEARTBEAT\nblocker=無\nnext=HEARTBEAT"
    ))
    assert not evaluate_issue_comment_intervention(
        r, [fake], now=NOW, trusted_authors={"looaeedr"},
    ).eligible


def test_scheduler_takeover_ignores_live_heartbeat_and_lease_for_time_eligibility():
    r = record()
    r = replace(r, lease=LeaseState(
        token="foreign-live-lease", invocation_identity="B15:owner",
        expires_at="2026-10-08T08:09:00Z",
    ))
    notes = {r.issue: [comment(r, 601)]}
    view = build_scheduler_view(
        [r], lane_id=LANE_A, invocation_identity="A00:new",
        now=NOW.isoformat(), issue_comments=notes,
        trusted_comment_authors={"looaeedr"},
        runtime_observations={LANE_B: {"schema": "WHD_RUNTIME_OBSERVATION_V2",
                                      "authority": "NON_AUTHORITY",
                                      "liveness_state": "LIVE"}},
    )
    assert view.decision == "TAKEOVER_CANDIDATE"
    assert view.takeover_reason == "ISSUE_COMMENT_STALE_OVER_600S"
    assert view.requires_transaction == "HANDOFF"


def test_scheduler_does_not_use_heartbeat_to_allow_takeover_without_comment():
    r = record()
    view = build_scheduler_view(
        [r], lane_id=LANE_A, invocation_identity="A00:new",
        now=NOW.isoformat(), issue_comments={},
        runtime_observations={LANE_B: {"schema": "WHD_RUNTIME_OBSERVATION_V2",
                                      "authority": "NON_AUTHORITY",
                                      "liveness_state": "ENDED"}},
    )
    assert view.decision == "NO_EXECUTABLE_WORK"


def test_lane_and_slot_identity_are_required_for_valid_progress():
    r = record()
    note = comment(r, 601)
    note["body"] = note["body"].replace(f"lane_id={r.lane_id}", "lane_id=wrong-lane")
    result = evaluate_issue_comment_intervention(
        r, [note], now=NOW, trusted_authors={"looaeedr"},
    )
    assert not result.eligible


def test_comment_from_future_never_allows_takeover():
    r = record()
    verdict = evaluate_issue_comment_intervention(
        r, [comment(r, -1)], now=NOW, trusted_authors={"looaeedr"},
    )
    assert not verdict.eligible
    assert verdict.reason == "ISSUE_COMMENT_FUTURE_TIMESTAMP"

def test_all_current_execution_entry_skills_retire_legacy_takeover_oracles():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    paths = (
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/engineering/寫排程/SKILL.md",
        ".agents/skills/engineering/排程模擬/SKILL.md",
        ".agents/skills/engineering/工作槽/SKILL.md",
        ".agents/skills/engineering/強制接手/SKILL.md",
    )
    for path in paths:
        body = (root / path).read_text(encoding="utf-8")
        assert "ISSUE_COMMENT_" in body and "600" in body
        assert "STUCK_UNOWNED_FAMILY_TAKEOVER_HARD_GATE_V1" not in body
    assert "ISSUE_COMMENT_10MIN_INTERVENTION_HARD_GATE_V1" in (root / "AGENTS.md").read_text(encoding="utf-8")
