from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ISSUE = 667
LANE = "scheduler.testlane"
OTHER_LANE = "scheduler.otherlane"
BRANCH = "governance/example"
HEAD = "a" * 40
CLAIM_BLOB = "b" * 40
UTC = timezone.utc


def _heartbeat(
    *,
    comment_id: int = 100,
    invocation: str = "invocation.100",
    emitted_at: str = "2026-09-25T00:00:00Z",
    expires_at: str = "2026-09-25T00:05:00Z",
):
    return {
        "id": comment_id,
        "created_at": emitted_at,
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_SCHEDULER_RUNTIME_LIVENESS_V1\n"
            f"issue={ISSUE}\n"
            f"scheduler_lane={LANE}\n"
            f"invocation_identity={invocation}\n"
            f"claim_blob_sha={CLAIM_BLOB}\n"
            f"branch={BRANCH}\n"
            f"head_sha={HEAD}\n"
            "executor_source=scheduler\n"
            f"emitted_at={emitted_at}\n"
            f"expires_at={expires_at}"
        ),
    }


def _end(
    *,
    comment_id: int = 101,
    invocation: str = "invocation.100",
    ended_at: str = "2026-09-25T00:01:00Z",
    head: str = HEAD,
):
    return {
        "id": comment_id,
        "created_at": ended_at,
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_SCHEDULER_RUNTIME_END_V1\n"
            f"issue={ISSUE}\n"
            f"scheduler_lane={LANE}\n"
            f"invocation_identity={invocation}\n"
            f"claim_blob_sha={CLAIM_BLOB}\n"
            f"branch={BRANCH}\n"
            f"head_sha={head}\n"
            "executor_source=scheduler\n"
            f"ended_at={ended_at}\n"
            "turn_exit_run_id=123"
        ),
    }


def test_matching_end_closes_exact_scheduler_invocation() -> None:
    selector = importlib.import_module("tools.scheduler_runtime_liveness")
    selected = selector.select_runtime_liveness_comment(
        [_heartbeat(), _end()],
        issue=ISSUE,
        scheduler_lane=LANE,
    )
    assert selected is not None
    assert selected["runtime_status"] == "ENDED"
    assert selected["invocation_identity"] == "invocation.100"
    assert selected["end_source_comment_id"] == 101
    assert selected["ended_at"] == "2026-09-25T00:01:00Z"
    assert selected["turn_exit_run_id"] == 123


def test_end_for_old_invocation_does_not_close_newer_heartbeat() -> None:
    selector = importlib.import_module("tools.scheduler_runtime_liveness")
    selected = selector.select_runtime_liveness_comment(
        [
            _heartbeat(comment_id=100, invocation="invocation.old"),
            _end(comment_id=101, invocation="invocation.old"),
            _heartbeat(
                comment_id=102,
                invocation="invocation.new",
                emitted_at="2026-09-25T00:02:00Z",
                expires_at="2026-09-25T00:07:00Z",
            ),
        ],
        issue=ISSUE,
        scheduler_lane=LANE,
    )
    assert selected is not None
    assert selected["runtime_status"] == "ACTIVE"
    assert selected["invocation_identity"] == "invocation.new"
    assert selected["end_source_comment_id"] is None


def test_malformed_relevant_end_fails_closed() -> None:
    selector = importlib.import_module("tools.scheduler_runtime_liveness")
    with pytest.raises(selector.RuntimeLivenessCommentError, match="END|end|head"):
        selector.select_runtime_liveness_comment(
            [_heartbeat(), _end(head="not-a-sha")],
            issue=ISSUE,
            scheduler_lane=LANE,
        )


def test_ended_scheduler_runtime_is_not_treated_as_live_lease() -> None:
    selector = importlib.import_module("tools.scheduler_runtime_liveness")
    takeover = importlib.import_module("tools.stale_claim_takeover")
    runtime = selector.select_runtime_liveness_comment(
        [_heartbeat(), _end()],
        issue=ISSUE,
        scheduler_lane=LANE,
    )
    claim = {
        "issue": ISSUE,
        "issue_url": f"https://github.com/looaeedr/whd/issues/{ISSUE}",
        "worker": LANE,
        "executor_source": "scheduler",
        "work_branch": BRANCH,
        "claimed_at": "2026-09-25T00:00:00Z",
        "base_sha": "c" * 40,
        "head_sha": HEAD,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-25T00:00:00Z",
        "remote_qa": None,
        "next_action": "continue",
        "blocker": None,
    }
    result = takeover.evaluate_stale_claim_takeover(
        claim,
        now=datetime(2026, 9, 25, 0, 3, tzinfo=UTC),
        live_head_sha=HEAD,
        live_head_committed_at="2026-09-25T00:00:00Z",
        stale_after_seconds=600,
        requesting_worker=OTHER_LANE,
        requesting_executor_source="scheduler",
        claim_blob_sha=CLAIM_BLOB,
        runtime_liveness=runtime,
        orphan_grace_seconds=90,
    )
    assert result.runtime_liveness_status == "ENDED"
    assert result.classification.value == "ORPHANED_SCHEDULER_OWNER"
    assert result.actionable is True


def test_runtime_liveness_maximum_window_is_300_seconds() -> None:
    takeover = importlib.import_module("tools.stale_claim_takeover")
    assert takeover.MAX_RUNTIME_LIVENESS_SECONDS == 300


def test_force_takeover_skill_encodes_canonical_chain() -> None:
    skill_path = ROOT / ".agents" / "skills" / "engineering" / "強制接手" / "SKILL.md"
    assert skill_path.is_file()
    text = skill_path.read_text(encoding="utf-8")
    required_in_order = [
        "派工",
        "tools/stale_claim_takeover.py",
        "WHD_USER_DIRECTED_TAKEOVER_V1",
        "遠端執行守門",
        "action=claim-takeover",
        "GREEN",
        "CAS",
        "checkpoint / next_action",
    ]
    positions = [text.index(token) for token in required_in_order]
    assert positions == sorted(positions)
    assert "active exact run" in text
    assert "fail closed" in text


def test_remote_guard_supports_user_directed_interactive_takeover() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "whd-remote-execution-guard.yml"
    ).read_text(encoding="utf-8")
    remote_skill = (
        ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "claim-takeover requires executor_source=scheduler" not in workflow
    assert "WHD_USER_DIRECTED_TAKEOVER_V1" in workflow
    assert "--user-authority-json" in workflow
    assert "requesting-executor-source" in workflow
    assert "interactive" in remote_skill.lower()
    assert "WHD_USER_DIRECTED_TAKEOVER_V1" in remote_skill


def test_scheduler_simulation_activation_enables_only_matching_lane() -> None:
    skill = (
        ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "SCHEDULER_ENABLE_ESTABLISHED" in skill
    assert "is_enabled=true" in skill
    assert "00 / 20 / 40" in skill
    assert "B15 / B45" in skill
    assert "不得修改 cadence" in skill
    assert "300 秒" in skill
    assert "420" not in skill
    assert "不自動 enable/disable/reschedule 任何 automation" not in skill


def test_registry_routes_explicit_force_takeover_skill() -> None:
    registry = json.loads(
        (ROOT / ".agents" / "skills" / "skill_registry.json").read_text(encoding="utf-8")
    )
    route = next(item for item in registry["routes"] if item["id"] == "force-takeover")
    assert "強制接手" in route["keywords"]
    assert "強制接手" in route["required_skills"]
    assert "派工" in route["required_skills"]
    assert "遠端執行守門" in route["required_skills"]
