from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_current_execution_docs_use_workspace_default_and_conditional_shared_zero() -> None:
    agents = _read("AGENTS.md")
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    assert "WORKSPACE_DEFAULT" in agents
    assert "SHARED_ZERO_FALLBACK" in agents
    assert "executor-local" in agents
    assert "ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1" in flow
    assert "WORKSPACE_DEFAULT" in flow
    assert "SHARED_ZERO_FALLBACK" in flow
    assert "ACQUIRE.effect.admission_reservation" not in agents


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

def test_path_reservation_contract_is_delivery_only() -> None:
    payload = json.loads(_read(".agents/contracts/WHD_PATH_RESERVATION_V1.json"))
    assert payload["phase"] == "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN"
    assert payload["root_authoring_policy"] == "NO_PREWRITE_RESERVATION__RESERVE_ONLY_FOR_GIT_DELIVERY"
    assert payload["canonical_delivery_reservation"]["phase"] == "AFTER_TESTED_DIFF_FROZEN"
    assert "canonical_new_work_admission" not in payload


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
    contract_text = _read(".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json")
    contract = json.loads(contract_text)

    retired = "SCHEDULER_LANE / GITHUB_ONLY / REMOTE_ACTION` 不直接套用此 workspace content gate"
    assert retired not in flow
    assert "REMOTE_CONTENT_IMPLEMENTATION_ROUTING_HARD_GATE_V3" in flow
    assert "REPOSITORY_CONTENT_ROUTING_HARD_GATE_V2" in scheduler
    assert "executor-local workspace" in agents and "cleanup/2d-3d-sync" in agents
    assert "GitHub-side hotfix" in root and "SHARED_ZERO_FALLBACK" in root

    assert "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK" not in flow
    assert "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK" not in scheduler
    assert "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK" not in contract_text
    assert "ROOT_WORKSPACE_HANDOFF" not in contract_text

    for mode in ("GITHUB_ONLY", "REMOTE_ACTION", "SCHEDULER_LANE"):
        assert contract["execution_modes"][mode] == "CONTROL_PLANE_OR_POST_PUSH_ONLY_REPOSITORY_CONTENT_REQUIRES_WORKSPACE_CAPABLE_RUNTIME_HANDOFF"

    remote = contract["remote_content_implementation"]
    assert remote["route_owner"] == "tools/root_local_first_gate.py::select_repository_content_route"
    assert remote["ordinary_route"] == "WORKSPACE_DEFAULT"
    assert remote["drive_mount_absence_is_blocker"] is False
    assert remote["interactive_workspace_action"] == "CONTINUE_WORKSPACE_DEFAULT"
    assert remote["remote_mode_repository_content_action"] == "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX"
    assert remote["shared_zero_missing_capability_action"] == "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME"
    assert remote["github_side_hotfix_forbidden"] is True

    fallback_gate = contract["direct_root_mutation_test_gate"]
    assert fallback_gate["applies_when"] == "SHARED_ZERO_FALLBACK_ACTIVE"
    assert fallback_gate["remote_without_root_capability_action"] == "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME"
    assert fallback_gate["ordinary_missing_drive_mount_action"] == "CONTINUE_WORKSPACE_DEFAULT_IF_EXECUTOR_WORKSPACE_CAPABLE"


def test_root_local_first_uses_delivery_only_reservation() -> None:
    root = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    contract = json.loads(_read(".agents/contracts/WHD_PATH_RESERVATION_V1.json"))
    assert "DELIVERY_RESERVATION" in root
    assert "Pre-write reservation" in root or "pre-write reservation" in root or "施工前置 single-writer gate" in root
    assert contract["phase"] == "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN"
    assert contract["root_authoring_policy"] == "NO_PREWRITE_RESERVATION__RESERVE_ONLY_FOR_GIT_DELIVERY"


def test_agents_completion_bridge_cannot_restore_legacy_continuity_finalization() -> None:
    agents = _read("AGENTS.md")
    assert "FLOW_V2_DURABLE_COMPLETION_BRIDGE_V1" in agents
    assert "Canonical executable 是 `tools/continuity_controller.py`" not in agents
    assert "python -m tools.continuity_controller assert-finalizable" not in agents
    assert "execution_invocation_exit.py" in agents
    assert "MERGE → FINALIZE → DONE" in agents


def test_always_read_references_use_workspace_default_and_no_mntdata_authority() -> None:
    global_pitfalls = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    root_pitfall = _read("個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md")
    for text in (global_pitfalls, root_pitfall):
        assert "WORKSPACE_DEFAULT" in text
        assert "SHARED_ZERO_FALLBACK" in text
        assert "executor-local" in text
        assert "ROOT_SOURCE_CURRENT → UNPUSHED_LANE_CLASSIFIED → LATEST_0_BASE_BOUND" not in text
    assert "固定落 `/mnt/data` 或其他跨回合持久位置" not in global_pitfalls
    assert "/mnt/data` 只可作 transient" in global_pitfalls


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
    assert "NORMAL_PATH_FIRST" in text
    assert "WORKSPACE_DEFAULT" in text
    assert "SHARED_ZERO_FALLBACK" in text
    assert "canonical root shared-0 authoring/tests" not in text
    assert "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION" not in text
    assert "READY → atomic ACQUIRE+reservation" not in text
    assert "排程 remote control-plane 與 content workspace 邊界 — CURRENT" in text
    assert "需要 Guard 時走 trusted Remote Guard" not in text


def test_registry_does_not_auto_route_current_execution_into_legacy_guard_or_continuity_references() -> None:
    registry = json.loads(_read(".agents/skills/skill_registry.json"))
    by_id = {route["id"]: route for route in registry["routes"]}
    remote_guard = by_id["remote-execution-guard"]
    assert remote_guard["required_skills"] == ["flow-v2-execution"]
    assert remote_guard["routing_status"] == "RETIRED"
    assert remote_guard["replacement_route_id"] == "flow-v2-execution"
    assert remote_guard["file_globs"] == []
    assert "scheduler no shell" not in remote_guard["keywords"]
    assert "GUARD_EXECUTION_CAPABILITY_BLOCKER" not in remote_guard["keywords"]

    continuity = by_id["executable-continuity-controller"]
    assert continuity["routing_status"] == "RETIRED"
    assert continuity["replacement_route_id"] == "flow-v2-execution"
    assert continuity["file_globs"] == []
    assert "explicit-skill-executable-continuity-controller" not in by_id
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

def test_retired_legacy_execution_artifacts_are_absent_from_production_tree() -> None:
    retired = (
        "docs/governance/whd_scheduler_takeover_usage.md",
        "docs/specs/WHD_排程_GuardTransaction_DelegatedHelper_StaleTakeover_硬閘門規格_2026-09-25.md",
        "UPDATE/AGENTS.md",
    )
    for path in retired:
        assert not (ROOT / path).exists(), f"retired legacy execution artifact regrew: {path}"


def test_flow_v2_declares_no_runtime_compatibility_right_for_legacy_execution() -> None:
    flow = _read(".agents/skills/engineering/flow-v2-execution/SKILL.md")
    assert "LEGACY_FLOW_HAS_NO_RUNTIME_COMPATIBILITY_RIGHT" in flow
    assert "ONE_CANONICAL_EXECUTION_PATH" in flow
    assert "歷史證據只留在 Git history / closed Issues" in flow


def test_control_plane_workflow_watches_semantic_authority_surfaces() -> None:
    workflow = _read(".github/workflows/whd-control-plane-regression.yml")
    for token in (
        ".agents/skills/skill_registry.json",
        ".agents/skills/skill_catalog.json",
        "個人AI檔案庫/**/*.md",
        "docs/governance/**/*.md",
        "docs/specs/**/*.md",
        "UPDATE/**/*.md",
        "tests/knowledge/**",
        "tools/knowledge_governance.py",
    ):
        assert token in workflow


def test_frozen_knowledge_snapshots_cannot_masquerade_as_runtime_authority() -> None:
    for path in (
        "docs/superpowers/verification/knowledge_governance_inventory_v1.json",
        "docs/superpowers/verification/knowledge_authority_classification_v1.json",
    ):
        payload = json.loads(_read(path))
        assert payload["runtime_authority"] is False
        assert payload["snapshot_role"] in {
            "BOOTSTRAP_FREEZE_BASELINE",
            "HISTORICAL_CLASSIFICATION_FREEZE",
        }
        assert "intentionally historical" in payload["snapshot_note"]

