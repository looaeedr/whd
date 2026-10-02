from __future__ import annotations

from pathlib import Path

import pytest

from tools.execution_invocation_exit import (
    InvocationExitError,
    assert_terminal_tail_owning_issue_sticky,
    classify_invocation_exit,
)
from tools.execution_record import execution_record_from_payload

ROOT = Path(__file__).resolve().parents[2]
CURRENT = 1086
INV = "interactive:work0:issue1086:test"


def _terminal_tail_record():
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 7,
            "issue": CURRENT,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work0",
            "lane_id": "chatgpt.flowv2.work0",
            "slot_id": "worker.slot.0",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "a" * 40,
            "work_branch": "governance/issue1086-terminal-tail-no-pivot",
            "head_sha": "b" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "c" * 40,
            "state": "INTEGRATING",
            "semantic_state": "QA_ACCEPTED",
            "next_action": {
                "kind": "MERGE",
                "args": {"pr_number": 1087, "head_sha": "b" * 40},
                "display": "merge exact accepted PR",
            },
            "lease": {
                "token": "lease-1086",
                "invocation_identity": INV,
                "expires_at": "2026-10-01T11:30:00Z",
            },
            "active_run": None,
            "transaction": None,
            "mutation_scope": None,
            "qa": {"last_accepted_run": 36849311967, "accepted_head_sha": "b" * 40},
            "blocker": None,
            "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
            "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
            "recovery_history": [],
            "updated_at": "2026-10-01T10:40:00Z",
        }
    )


def test_terminal_tail_foreign_stale_recovery_cannot_preempt_current_issue():
    record = _terminal_tail_record()
    for action in ("ACQUIRE", "RELEASE_PATHS", "RECONCILE", "HANDOFF", "FINALIZE"):
        with pytest.raises(InvocationExitError, match="TERMINAL_TAIL_NO_PIVOT"):
            assert_terminal_tail_owning_issue_sticky(
                record, requested_issue=1062, requested_action_kind=action
            )


def test_terminal_tail_allows_read_only_foreign_debt_observation_and_current_merge():
    record = _terminal_tail_record()
    assert assert_terminal_tail_owning_issue_sticky(
        record, requested_issue=1062, requested_action_kind="READ_ONLY_DISCOVERY"
    )
    assert assert_terminal_tail_owning_issue_sticky(
        record, requested_issue=CURRENT, requested_action_kind="MERGE"
    )
    decision = classify_invocation_exit(
        record, invocation_identity=INV, now="2026-10-01T10:45:00Z", host_boundary=True
    )
    assert decision.decision == "CONTINUE_TERMINAL_TAIL"
    assert decision.may_return is False
    assert decision.requires_yield is False


def test_flow_skill_forbids_unrelated_stale_reservation_pivot_during_terminal_tail():
    text = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "TERMINAL_TAIL_OWNING_ISSUE_STICKINESS_HARD_GATE_V1" in text
    assert "UNRELATED_COORDINATION_DEBT_DEFERRED" in text
    assert "reservation_state=ACTIVE" in text
    assert "不得自動 takeover / repair foreign Issue" in text
    assert "assert_terminal_tail_owning_issue_sticky" in text
