from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scheduler_runtime_liveness import (
    RuntimeLivenessCommentError,
    select_runtime_liveness_comment,
)


ROOT = Path(__file__).resolve().parents[2]
ISSUE = 865
LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
INVOCATION = "issue865-test"
CLAIM = "a" * 40
HEAD = "b" * 40
BRANCH = "governance/issue865-stop-hardening-cleanup-20260928"
CHECKPOINT_FP = "c" * 64
CENSUS_FP = "d" * 64


def _comment(comment_id: int, login: str, body: str, created_at: str) -> dict:
    return {
        "id": comment_id,
        "user": {"login": login},
        "body": body,
        "created_at": created_at,
    }


def _heartbeat() -> dict:
    return _comment(
        100,
        "looaeedr",
        "\n".join(
            [
                "WHD_SCHEDULER_RUNTIME_LIVENESS_V1",
                f"issue={ISSUE}",
                f"scheduler_lane={LANE}",
                f"invocation_identity={INVOCATION}",
                f"claim_blob_sha={CLAIM}",
                f"branch={BRANCH}",
                f"head_sha={HEAD}",
                "executor_source=scheduler",
                "emitted_at=2026-09-28T00:00:00Z",
                "expires_at=2026-09-28T00:05:00Z",
            ]
        ),
        "2026-09-28T00:00:01Z",
    )


def _intermediate_end() -> dict:
    return _comment(
        101,
        "looaeedr",
        "\n".join(
            [
                "WHD_SCHEDULER_RUNTIME_END_V1",
                f"issue={ISSUE}",
                f"scheduler_lane={LANE}",
                f"invocation_identity={INVOCATION}",
                "request_comment_id=90",
                "result_comment_id=91",
                f"checkpoint_fingerprint={CHECKPOINT_FP}",
                "turn_exit_run_id=92",
                f"ready_work_census_fingerprint={CENSUS_FP}",
            ]
        ),
        "2026-09-28T00:00:10Z",
    )


def _validated_end_result(*, head_sha: str = HEAD) -> dict:
    payload = {
        "schema": "WHD_SCHEDULER_RUNTIME_END_RESULT_V1",
        "issue": ISSUE,
        "scheduler_lane": LANE,
        "invocation_identity": INVOCATION,
        "claim_blob_sha": CLAIM,
        "branch": BRANCH,
        "head_sha": head_sha,
        "executor_source": "scheduler",
        "ended_at": "2026-09-28T00:00:09Z",
        "request_comment_id": 90,
        "result_comment_id": 91,
        "checkpoint_fingerprint": CHECKPOINT_FP,
        "turn_exit_run_id": 92,
        "ready_work_census_fingerprint": CENSUS_FP,
        "validation_run_id": 93,
        "result": "GREEN",
        "reason": "EXACT_TURN_EXIT_RECEIPT_BOUND",
    }
    return _comment(
        102,
        "github-actions[bot]",
        "WHD_SCHEDULER_RUNTIME_END_RESULT_V1\n~~~json\n"
        + json.dumps(payload)
        + "\n~~~",
        "2026-09-28T00:00:11Z",
    )


def test_raw_intermediate_end_without_validator_green_does_not_end_runtime() -> None:
    selected = select_runtime_liveness_comment(
        [_heartbeat(), _intermediate_end()],
        issue=ISSUE,
        scheduler_lane=LANE,
    )
    assert selected is not None
    assert selected["runtime_status"] == "ACTIVE"
    assert selected["end_source_comment_id"] is None


def test_bot_validated_end_result_marks_runtime_ended() -> None:
    selected = select_runtime_liveness_comment(
        [_heartbeat(), _intermediate_end(), _validated_end_result()],
        issue=ISSUE,
        scheduler_lane=LANE,
    )
    assert selected is not None
    assert selected["runtime_status"] == "ENDED"
    assert selected["end_source_comment_id"] == 102
    assert selected["turn_exit_run_id"] == 92


def test_validated_end_identity_drift_fails_closed() -> None:
    with pytest.raises(RuntimeLivenessCommentError, match="head_sha"):
        select_runtime_liveness_comment(
            [
                _heartbeat(),
                _validated_end_result(head_sha="e" * 40),
            ],
            issue=ISSUE,
            scheduler_lane=LANE,
        )


def test_turn_exit_workflow_passes_full_end_identity_and_census_to_validator() -> None:
    text = (ROOT / ".github/workflows/whd-turn-exit-gate.yml").read_text(encoding="utf-8")
    for token in (
        '"claim_blob_sha": values["claim_blob_sha"]',
        '"branch": values["branch"]',
        '"head_sha": values["head_sha"]',
        '"executor_source": values["executor_source"]',
        '"ended_at": values["ended_at"]',
        '"ready_work_census_fingerprint": values["ready_work_census_fingerprint"]',
    ):
        assert token in text


def test_remote_phase6_preflight_is_read_only_fixed_schema_transport() -> None:
    text = (ROOT / ".github/workflows/whd-phase6-preflight.yml").read_text(
        encoding="utf-8"
    )
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1" in text
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1" in text
    assert "tools/phase6_skill_preflight.py" in text
    assert "contents: read" in text
    assert "issues: write" in text
    assert "contents: write" not in text
    assert "workflow_dispatch" not in text
    assert "arbitrary command" not in text.lower()


def test_scheduler_authoring_preserves_substantive_progress_and_validated_end() -> None:
    text = (
        ROOT / ".agents/skills/engineering/寫排程/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "SUBSTANTIVE_DURABLE_PROGRESS_HARD_GATE_V1" in text
    assert "substantive durable GitHub effect" in text
    assert "SCHEDULER_EXECUTION_FAILURE" in text
    assert "WHD_SCHEDULER_RUNTIME_END_RESULT_V1" in text
    assert "EXACT_TURN_EXIT_RECEIPT_BOUND" in text


def test_agents_has_github_only_remote_phase6_preflight_bridge() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GITHUB_ONLY_REMOTE_PHASE6_PREFLIGHT_V1" in text
    assert ".github/workflows/whd-phase6-preflight.yml" in text
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1" in text
    assert "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1" in text
