from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SKILLS = {
    "dispatch": ROOT / ".agents/skills/engineering/派工/SKILL.md",
    "execute": ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md",
    "scheduler_sim": ROOT / ".agents/skills/engineering/排程模擬/SKILL.md",
    "scheduler_authoring": ROOT / ".agents/skills/engineering/寫排程/SKILL.md",
    "remote_guard": ROOT / ".agents/skills/engineering/remote-execution-guard/SKILL.md",
    "continuity": ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
    "closure": ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md",
}


def _gate():
    return importlib.import_module("tools.execution_scope_gate")


@pytest.mark.parametrize(
    ("mode", "action", "allowed"),
    [
        ("UPDATE_ONLY", "SAME_SCOPE_NEXT_ACTION", True),
        ("UPDATE_ONLY", "START_SUCCESSOR", False),
        ("UPDATE_ONLY", "DYNAMIC_DISCOVERY", False),
        ("EXECUTE_TICKET", "SAME_SCOPE_NEXT_ACTION", True),
        ("EXECUTE_TICKET", "START_SUCCESSOR", False),
        ("EXECUTE_CHAIN", "START_SUCCESSOR", True),
        ("SCHEDULER_LANE", "START_SUCCESSOR", True),
        ("SCHEDULER_LANE", "DYNAMIC_DISCOVERY", True),
    ],
)
def test_mode_boundary(mode, action, allowed):
    decision = _gate().evaluate_execution_scope(
        mode=mode,
        action=action,
        same_scope=True,
        fresh_recovery_evidence=False,
        explicit_user_takeover=False,
    )
    assert decision["allowed"] is allowed


def test_recovery_requires_fresh_machine_evidence():
    gate = _gate()
    denied = gate.evaluate_execution_scope(
        mode="EXECUTE_TICKET",
        action="RECOVERY",
        same_scope=True,
        fresh_recovery_evidence=False,
        explicit_user_takeover=False,
    )
    allowed = gate.evaluate_execution_scope(
        mode="EXECUTE_TICKET",
        action="RECOVERY",
        same_scope=True,
        fresh_recovery_evidence=True,
        explicit_user_takeover=False,
    )
    assert denied["allowed"] is False
    assert denied["reason"] == "RECOVERY_REQUIRES_FRESH_MACHINE_EVIDENCE"
    assert allowed["allowed"] is True


def test_recovery_cannot_escape_current_scope():
    out = _gate().evaluate_execution_scope(
        mode="UPDATE_ONLY",
        action="RECOVERY",
        same_scope=False,
        fresh_recovery_evidence=True,
        explicit_user_takeover=False,
    )
    assert out["allowed"] is False
    assert out["reason"] == "RECOVERY_OUTSIDE_AUTHORIZED_SCOPE"


def test_takeover_requires_scheduler_lane_or_explicit_user_direction():
    gate = _gate()
    normal = gate.evaluate_execution_scope(
        mode="EXECUTE_TICKET",
        action="TAKEOVER",
        same_scope=True,
        fresh_recovery_evidence=True,
        explicit_user_takeover=False,
    )
    explicit = gate.evaluate_execution_scope(
        mode="EXECUTE_TICKET",
        action="TAKEOVER",
        same_scope=True,
        fresh_recovery_evidence=True,
        explicit_user_takeover=True,
    )
    scheduler = gate.evaluate_execution_scope(
        mode="SCHEDULER_LANE",
        action="TAKEOVER",
        same_scope=True,
        fresh_recovery_evidence=True,
        explicit_user_takeover=False,
    )
    assert normal["allowed"] is False
    assert explicit["allowed"] is True
    assert scheduler["allowed"] is True


def test_unknown_mode_or_action_fails_closed():
    gate = _gate()
    with pytest.raises(gate.ExecutionScopeError):
        gate.evaluate_execution_scope(
            mode="MAGIC",
            action="SAME_SCOPE_NEXT_ACTION",
            same_scope=True,
            fresh_recovery_evidence=False,
            explicit_user_takeover=False,
        )
    with pytest.raises(gate.ExecutionScopeError):
        gate.evaluate_execution_scope(
            mode="UPDATE_ONLY",
            action="MAGIC",
            same_scope=True,
            fresh_recovery_evidence=False,
            explicit_user_takeover=False,
        )


def test_all_execution_entrypoints_bridge_to_scope_gate():
    required = {
        "dispatch": (
            "EXECUTION_MODE_HARD_GATE_V1",
            "NORMAL_PATH_FIRST",
            "RECOVERY_IS_EXCEPTION_NOT_PHASE",
            "ISSUE_EXISTENCE_IS_NOT_EXECUTION_AUTHORITY",
            "tools/execution_scope_gate.py",
        ),
        "execute": (
            "WORK_SLOT_EXECUTION_MODE_V1",
            "UPDATE_ONLY",
            "EXECUTE_TICKET",
            "EXECUTE_CHAIN",
            "SCHEDULER_LANE",
            "tools/execution_scope_gate.py",
        ),
        "scheduler_sim": (
            "SCHEDULER_LANE",
            "tools/execution_scope_gate.py",
            "UPDATE_ONLY",
        ),
        "scheduler_authoring": (
            "UPDATE_DOES_NOT_IMPLY_EXECUTION",
            "UPDATE_ONLY",
            "tools/execution_scope_gate.py",
        ),
        "remote_guard": (
            "RECOVERY_IS_EXCEPTION_NOT_PHASE",
            "tools/execution_scope_gate.py",
        ),
        "continuity": (
            "EXECUTION_SCOPE_BRIDGE_V1",
            "tools/execution_scope_gate.py",
            "START_SUCCESSOR",
        ),
        "closure": (
            "SUCCESSOR_SCOPE_GATE_V1",
            "tools/execution_scope_gate.py",
            "START_SUCCESSOR",
        ),
    }
    for key, markers in required.items():
        text = SKILLS[key].read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"{key} missing execution-scope marker: {marker}"


def test_scheduler_simulation_only_explicit_commands_enter_scheduler_lane():
    text = SKILLS["scheduler_sim"].read_text(encoding="utf-8")
    assert "普通文字提到「排程 A/B」不自動取得 lane ownership" in text
    assert "/排程A" in text and "/排程B" in text
    assert "SCHEDULER_LANE" in text


def test_scheduler_authoring_update_only_ends_after_readback():
    text = SKILLS["scheduler_authoring"].read_text(encoding="utf-8")
    assert "update + validation + readback" in text
    assert "不得自動 claim successor" in text
    assert "不得自動啟動工單施工" in text


def test_dispatch_normal_path_is_short_and_recovery_not_preflight_phase():
    text = SKILLS["dispatch"].read_text(encoding="utf-8")
    assert "claim → branch → RED → implementation → GREEN → PR/QA → merge → close/release" in text
    assert "不得預防性執行 recovery" in text
    assert "fresh machine evidence" in text


def test_work_slot_mode_survives_progress_updates():
    text = SKILLS["execute"].read_text(encoding="utf-8")
    assert "progress/status 不得改變 execution_mode" in text
    assert "UPDATE_ONLY" in text
    assert "EXECUTE_TICKET" in text
    assert "EXECUTE_CHAIN" in text
    assert "SCHEDULER_LANE" in text
