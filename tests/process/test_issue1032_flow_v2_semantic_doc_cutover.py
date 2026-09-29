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

def test_agents_completion_bridge_cannot_restore_legacy_continuity_finalization() -> None:
    agents = _read("AGENTS.md")
    assert "FLOW_V2_DURABLE_COMPLETION_BRIDGE_V1" in agents
    assert "Canonical executable 是 `tools/continuity_controller.py`" not in agents
    assert "python -m tools.continuity_controller assert-finalizable" not in agents
    assert "execution_invocation_exit.py" in agents
    assert "MERGE → FINALIZE → DONE" in agents


def test_always_read_references_use_reserved_path_root_order_and_no_mntdata_authority() -> None:
    global_pitfalls = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    root_pitfall = _read("個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md")
    expected = "ROOT_SOURCE_CURRENT → PATHS_RESERVED → ROOT_MUTATIONS_COMPLETE → ROOT_TEST_CLASSIFIED → ROOT_TESTS_GREEN → ROOT_DIFF_FROZEN → GIT_WRITE_UNLOCKED"
    assert expected in global_pitfalls
    assert expected in root_pitfall
    assert "固定落 `/mnt/data` 或其他跨回合持久位置" not in global_pitfalls
    assert "/mnt/data` 只可作 transient execution/transport materialization" in global_pitfalls


def test_skill_governance_does_not_name_legacy_execution_tools_as_current_semantic_owners() -> None:
    rules = _read("個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md")
    legacy_current = "Canonical semantic owners remain single-source: generic operation continuity = `tools/continuity_controller.py`"
    assert legacy_current not in rules
    assert "HISTORICAL mapping only" in rules
    assert "WHD_EXECUTION_RECORD_V2" in rules


def test_scheduler_required_reference_uses_flow_v2_current_rules_not_legacy_guard_template() -> None:
    text = _read("個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md")
    assert "### CURRENT 永久規則" in text
    assert "施工型 scheduler prompt 必須顯式保留 **派工 + 遠端執行守門**" not in text
    assert "NORMAL_PATH_FIRST`：正常 implementation 走 `READY → atomic ACQUIRE+reservation" in text
    assert "排程 remote control-plane 與 root content surface 邊界 — CURRENT" in text
    assert "需要 Guard 時走 trusted Remote Guard" not in text


def test_registry_does_not_auto_route_current_execution_into_legacy_guard_or_continuity_references() -> None:
    registry = json.loads(_read(".agents/skills/skill_registry.json"))
    by_id = {route["id"]: route for route in registry["routes"]}
    remote_guard = by_id["remote-execution-guard"]
    assert remote_guard["required_skills"] == ["flow-v2-execution"]
    assert "scheduler no shell" not in remote_guard["keywords"]
    assert "GUARD_EXECUTION_CAPABILITY_BLOCKER" not in remote_guard["keywords"]

    continuity = by_id["executable-continuity-controller"]
    for broad in ("不停工", "持續執行", "runtime cut", "task chain", "implement spec"):
        assert broad not in continuity["keywords"]

    force = by_id["force-takeover"]
    assert "tools/stale_claim_takeover.py" not in force["file_globs"]
    assert ".github/workflows/whd-remote-execution-guard.yml" not in force["file_globs"]

    legacy_ref = "個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md"
    for route_id in ("scheduler-authoring", "scheduler-simulation", "remote-qa-monitoring", "issue-closure-gate", "force-takeover"):
        assert legacy_ref not in by_id[route_id].get("required_references", [])


def test_skill_catalog_canonical_classification_is_routing_not_semantic_current() -> None:
    catalog = json.loads(_read(".agents/skills/skill_catalog.json"))
    policy = catalog["semantic_authority_policy"]
    assert policy["classification_scope"] == "ACTIVE_INVOCATION_ROUTING_ONLY"
    assert policy["canonical_classification_does_not_imply_doc_role_current"] is True
    assert policy["active_mirror_skill_allowed"] is True

