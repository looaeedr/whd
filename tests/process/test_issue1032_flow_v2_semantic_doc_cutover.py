from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_current_execution_docs_use_atomic_admission_and_session_reuse() -> None:
    agents = _read("AGENTS.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    assert "atomic `ACQUIRE.effect.admission_reservation" in agents
    assert "不得主動拆成 `ACQUIRE → RESERVE_PATHS`" in agents
    assert "session-first" in flow
    assert "LIVE_LEASE_CONTINUATION" in flow
    assert "每次需要 ACQUIRE/RESERVE_PATHS/RELEASE_PATHS/ACCEPT_QA" not in flow

def test_current_qa_docs_prefer_consume_qa_for_existing_terminal_green() -> None:
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    monitor = _read(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    assert "優先送單顆 `CONSUME_QA`" in flow
    assert "直接 `CONSUME_QA`" in monitor

def test_current_skills_do_not_restore_legacy_claim_guard_authority() -> None:
    skill = _read(".agents/skills/engineering/寫技能/SKILL.md")
    execute = _read(".agents/skills/engineering/執行開發任務/SKILL.md")
    wayfinder = _read(".agents/skills/engineering/wayfinder/SKILL.md")
    rules = _read("個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md")
    assert "然後每次 Skill file write/commit 緊接著執行 `tools/execution_claim_guard.py`" not in skill
    assert "Preflight、Guard、claim、repository mutation" not in execute
    assert "That assignee _is_ the claim" not in wayfinder
    assert "NO WORK WITHOUT CLAIM" not in rules
    assert "FLOW_V2_MULTI_AI_SINGLE_WRITER_CURRENT_V1" in rules

def test_path_reservation_contract_names_atomic_new_work_admission() -> None:
    payload = json.loads(_read(".agents/contracts/WHD_PATH_RESERVATION_V1.json"))
    assert payload["canonical_new_work_admission"]["transaction"] == "ACQUIRE"
    assert payload["canonical_new_work_admission"]["effect_field"] == "admission_reservation"
    assert payload["separate_reserve_policy"] == "COMPATIBILITY_OR_MONOTONIC_SCOPE_EXPANSION_ONLY"

def test_required_legacy_execution_references_are_explicitly_fenced() -> None:
    paths = [
        "個人AI檔案庫/踩坑庫/execution_claim_hard_gate_pitfall.md",
        "個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md",
        "個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md",
        "個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md",
    ]
    for path in paths:
        text = _read(path)
        assert "FLOW_V2_LEGACY_EXECUTION_HISTORY_FENCE_V1" in text
        assert "都不是 CURRENT 執行指令" in text

def test_authority_map_does_not_promote_liveness_claim_blob_to_execution_authority() -> None:
    text = _read("個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    assert "claim_blob_sha` 在此只屬 liveness compatibility identity" in text
    assert "native ExecutionRecord" in text


def test_scheduler_and_remote_modes_cannot_bypass_root_local_first_content_work() -> None:
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    scheduler = _read(".agents/skills/engineering/排程模擬/SKILL.md")
    agents = _read("AGENTS.md")
    contract = json.loads(_read(".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"))

    retired = "SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 不直接套用此 workspace content gate"
    assert retired not in flow
    assert "REMOTE_CONTENT_IMPLEMENTATION_HANDOFF_HARD_GATE_V1" in flow
    assert "REPOSITORY_CONTENT_HANDOFF_HARD_GATE_V1" in scheduler
    assert "remote lane 禁止 GitHub-side authoring/hotfix" in agents
    assert "remote lane **不得在 GitHub branch 直接施工或熱修**" in root
    assert contract["execution_modes"]["SCHEDULER_LANE"].endswith("ROOT_WORKSPACE_HANDOFF")
    assert contract["remote_content_implementation"]["github_side_hotfix_forbidden"] is True


def test_root_local_first_uses_atomic_admission_for_new_work() -> None:
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    assert "ACQUIRE.effect.admission_reservation" in root
    assert "新 work 不得主動拆成 `ACQUIRE → RESERVE_PATHS`" in root
