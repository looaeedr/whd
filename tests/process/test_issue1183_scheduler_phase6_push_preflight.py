from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.phase6_preflight_push_request import (
    Phase6PushRequestError,
    normalize_push_request,
)
from tools.phase6_remote_preflight import run_remote_preflight

ROOT = Path(__file__).resolve().parents[2]
A_LANE = "scheduler.6ab13fa557fc8191935c671214b865e2"
B_LANE = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"


def _push_request(*, lane=A_LANE, issue=1080):
    return {
        "schema": "WHD_REMOTE_PHASE6_PREFLIGHT_PUSH_REQUEST_V1",
        "request_id": "issue1080-a40-20261004T2040",
        "issue": issue,
        "lane_id": lane,
        "worker": lane,
        "invocation_identity": "scheduler-a:a40:20261004T204000Z",
        "executor_source": "scheduler",
        "branch": "cleanup/2d-3d-sync",
        "head_sha": "a" * 40,
        "task": "take over stranded scheduler work and continue exact next_action",
        "changed_files": [],
    }


def test_a_branch_hard_binds_a_lane_and_normalizes_request():
    normalized = normalize_push_request(
        _push_request(),
        request_branch="coord/preflight-requests-a",
    )
    assert normalized["schema"] == "WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1"
    assert normalized["request_source"] == "push"
    assert normalized["lane_id"] == A_LANE
    assert normalized["worker"] == A_LANE
    assert normalized["issue"] == 1080
    assert normalized["invocation_identity"] == "scheduler-a:a40:20261004T204000Z"


def test_cross_lane_push_request_fails_closed():
    with pytest.raises(Phase6PushRequestError, match="lane mismatch"):
        normalize_push_request(
            _push_request(lane=B_LANE),
            request_branch="coord/preflight-requests-a",
        )


def test_push_preflight_result_contains_canonical_invocation_bound_evidence():
    normalized = normalize_push_request(
        _push_request(),
        request_branch="coord/preflight-requests-a",
    )
    observed = datetime(2026, 10, 4, 12, 40, tzinfo=timezone.utc)
    receipt = run_remote_preflight(
        normalized,
        run_id=123456,
        root=ROOT,
        observed_at=observed,
    )

    assert receipt["schema"] == "WHD_REMOTE_PHASE6_PREFLIGHT_RESULT_V1"
    assert receipt["result"] == "GREEN"
    assert receipt["request_source"] == "push"
    evidence = receipt["preflight_evidence"]
    assert evidence["schema"] == "WHD_PHASE6_PREFLIGHT_GATE_EVIDENCE_V1"
    assert evidence["status"] == "GREEN"
    assert evidence["issue"] == 1080
    assert evidence["invocation_identity"] == normalized["invocation_identity"]
    assert evidence["branch"] == "cleanup/2d-3d-sync"
    assert evidence["head_sha"] == "a" * 40
    assert set(evidence["required_skills"]) == set(evidence["completed_skills"])
    assert set(evidence["required_references"]) == set(evidence["completed_references"])


def test_comment_and_push_workflows_share_one_canonical_runner():
    comment = (ROOT / ".github/workflows/whd-phase6-preflight.yml").read_text(encoding="utf-8")
    push = (ROOT / ".github/workflows/whd-phase6-preflight-push.yml").read_text(encoding="utf-8")
    marker = "python -m tools.phase6_remote_preflight"
    assert marker in comment
    assert marker in push
    assert "coord/preflight-requests-a" in push
    assert "coord/preflight-requests-b" in push
    assert ".dispatch/preflight-request.json" in push


def test_scheduler_contract_forbids_issue_comment_preflight_requests():
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    scheduler = (ROOT / ".agents/skills/engineering/排程模擬/SKILL.md").read_text(encoding="utf-8")
    authoring = (ROOT / ".agents/skills/engineering/寫排程/SKILL.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for text in (flow, scheduler, authoring, agents):
        assert "coord/preflight-requests-a" in text or "coord/preflight-requests-a|b" in text
        assert "Issue request comment" in text or "Issue comment mutation" in text
