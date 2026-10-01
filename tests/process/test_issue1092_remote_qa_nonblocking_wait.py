from __future__ import annotations

from pathlib import Path

import pytest

from tools.execution_invocation_exit import (
    InvocationExitError,
    assert_remote_qa_active_observation_budget,
    classify_invocation_exit,
)
from tools.execution_record import execution_record_from_payload

ROOT = Path(__file__).resolve().parents[2]
INV = "interactive:work0:issue1092:test"


def _remote_wait_record(status="in_progress"):
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 4,
        "issue": 1092,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": "chatgpt.flowv2.work0",
        "lane_id": "chatgpt.flowv2.work0",
        "slot_id": "worker.slot.0",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "governance/issue1092-remote-qa-nonblocking",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "VERIFYING",
        "semantic_state": "QA_RUNNING",
        "next_action": {
            "kind": "POLL_QA",
            "args": {"run_id": 36855646477, "head_sha": "b" * 40},
            "display": "observe exact QA run",
        },
        "lease": {
            "token": "lease-1092",
            "invocation_identity": INV,
            "expires_at": "2026-10-01T12:30:00Z",
        },
        "active_run": {
            "id": 36855646477,
            "head_sha": "b" * 40,
            "purpose": "QA",
            "status": status,
        },
        "transaction": None,
        "mutation_scope": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-10-01T11:45:00Z",
    })


def test_first_active_qa_observation_yields_immediately():
    decision = classify_invocation_exit(
        _remote_wait_record(),
        invocation_identity=INV,
        now="2026-10-01T11:46:00Z",
        remote_qa_active_observation_count=1,
    )
    assert decision.decision == "YIELD_REQUIRED_REMOTE_WAIT"
    assert decision.requires_yield is True
    assert decision.may_return is False


def test_second_active_qa_observation_in_same_invocation_is_rejected():
    with pytest.raises(InvocationExitError, match="REMOTE_QA_POLL_BUDGET_EXHAUSTED"):
        classify_invocation_exit(
            _remote_wait_record("queued"),
            invocation_identity=INV,
            now="2026-10-01T11:46:00Z",
            remote_qa_active_observation_count=2,
        )


def test_budget_helper_allows_terminal_status_for_immediate_consumption():
    assert assert_remote_qa_active_observation_budget(
        observation_count=2, run_status="completed"
    )


def test_flow_and_remote_qa_skills_lock_nonblocking_wait_contract():
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    mirror = (ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md").read_text(encoding="utf-8")
    for text in (flow, mirror):
        assert "REMOTE_QA_NONBLOCKING_WAIT_HARD_GATE_V1" in text
        assert "YIELD_REQUIRED_REMOTE_WAIT" in text
        assert "REMOTE_QA_POLL_BUDGET_EXHAUSTED" in text
        assert "assert_remote_qa_active_observation_budget" in text
    assert "同一 invocation 禁止第二次讀同一 active run" in flow
    assert "每個 invocation" in mirror
