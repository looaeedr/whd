from pathlib import Path

import pytest

from tools.execution_entry_contract import (
    STARTUP_COMMUNICATION_SCHEMA,
    build_startup_communication_evidence,
    build_startup_declaration,
)
from tools.root_local_first_gate import build_remote_connection_authority

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_codex_headless_startup_does_not_require_chat_or_ai_library():
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    agents = _read("AGENTS.md")
    for text in (flow, agents):
        assert "NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE" in text
        assert "WHD_EXECUTION_STARTUP_COMMUNICATION_V1" in text
        assert "STDOUT / TASK_EVENT / LOG" in text
    assert "AI Library gate 已完成" not in flow


def test_headless_startup_communication_is_machine_visible():
    declaration = build_startup_declaration(purpose="repair issue 1212")
    evidence = build_startup_communication_evidence(
        runtime_surface="CODEX",
        channel="STDOUT",
        declaration=declaration,
        skills=("flow-v2-execution", "root-local-first"),
    )
    assert evidence["schema"] == STARTUP_COMMUNICATION_SCHEMA
    assert evidence["machine_visible"] is True
    assert evidence["user_visible"] is False
    with pytest.raises(ValueError, match="STDOUT/TASK_EVENT/LOG"):
        build_startup_communication_evidence(
            runtime_surface="CODEX",
            channel="USER_VISIBLE_CHAT",
            declaration=declaration,
        )


def test_interactive_chat_still_requires_user_visible_startup():
    declaration = build_startup_declaration(purpose="interactive task")
    evidence = build_startup_communication_evidence(
        runtime_surface="CHATGPT",
        channel="USER_VISIBLE_CHAT",
        declaration=declaration,
    )
    assert evidence["user_visible"] is True
    with pytest.raises(ValueError, match="user-visible"):
        build_startup_communication_evidence(
            runtime_surface="CHATGPT",
            channel="LOG",
            declaration=declaration,
        )


def test_codex_workspace_recovery_never_returns_to_drive_root():
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    section = root.split("FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY", 1)[1].split(
        "machine owner=", 1
    )[0]
    assert "本 executor 的 repo workspace canonical entry" in section
    assert "不得因這個 recovery 去尋找或等待 `/Google Drive/WHD`" in section
    assert "GITHUB_ONLY/REMOTE_ACTION 回 fresh production branch" in section


def test_same_scope_workspace_delivery_authority_is_machine_valid():
    authority = build_remote_connection_authority(
        kind="WORKSPACE_DELIVERY",
        target="GITHUB",
        user_explicit=True,
    )
    actions = set(authority["allowed_actions"])
    assert {"CREATE_BRANCH", "PUSH", "CREATE_PR", "CI", "MERGE", "READBACK"} <= actions
    assert authority["kind"] == "WORKSPACE_DELIVERY"


def test_skill_authoring_no_longer_requires_drive_first():
    skill = _read(".agents/skills/engineering/寫技能/SKILL.md")
    ref = _read("個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md")
    for text in (skill, ref):
        assert "executor-local repo workspace" in text
        assert "WORKSPACE_DELIVERY" in text
    assert "baseline 必須從 canonical `/Google Drive/WHD` root" not in skill


def test_scheduler_bridge_is_not_truncated_or_ai_library_blocked():
    scheduler = _read(".agents/skills/engineering/排程模擬/SKILL.md")
    assert "若新 \n### SHARED_0_SCHEDULER_HARD_GATE_V1" not in scheduler
    assert "NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE" in scheduler
    assert "machine-visible" in scheduler
