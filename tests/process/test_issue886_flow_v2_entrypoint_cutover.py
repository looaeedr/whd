from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]

CANONICAL = ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
BRIDGES = [
    ROOT / ".agents/skills/engineering/排程模擬/SKILL.md",
    ROOT / ".agents/skills/engineering/派工/SKILL.md",
    ROOT / ".agents/skills/engineering/工作槽/SKILL.md",
    ROOT / ".agents/skills/engineering/寫排程/SKILL.md",
    ROOT / ".agents/skills/engineering/remote-execution-guard/SKILL.md",
    ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
    ROOT / ".agents/skills/engineering/issue-closure-gate/SKILL.md",
    ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md",
    ROOT / ".agents/skills/engineering/強制接手/SKILL.md",
    ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
]
BANNED_ACTIVE = [
    "coord/dispatch-claims",
    "WHD_REMOTE_GUARD_REQUEST_V1",
    "WHD_REMOTE_GUARD_RESULT_V1",
    "READY_WORK_CENSUS_V1",
    "SAME_LANE_NONTERMINAL_WORK_V1",
    "GUARD_IN_FLIGHT",
    "FINALIZATION_IN_FLIGHT",
    "claim-takeover",
]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canonical_flow_v2_skill_exists_and_owns_execution():
    body = text(CANONICAL)
    assert "name: flow-v2-execution" in body
    assert "whd_contract: flow-v2-execution" in body
    assert "coord/execution-v2" in body
    assert ".dispatch/execution/issue-<N>.json" in body
    assert "DERIVED_CACHE_ONLY" in body
    assert "YIELD" in body
    assert "ORPHAN_WRITE" in body
    assert "DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1" in body
    assert "WHD_RUNTIME_OBSERVABILITY_V1" in body
    assert "coord/monitor-v2" in body


def test_workflow_entry_skills_are_flow_v2_bridges_not_legacy_authorities():
    for path in BRIDGES:
        body = text(path)
        assert "FLOW_V2_EXECUTION_BRIDGE_V1" in body, path
        assert "flow-v2-execution" in body, path
        for token in BANNED_ACTIVE:
            assert token not in body, (path, token)


def test_registry_routes_workflow_entries_through_flow_v2():
    registry = json.loads(text(ROOT / ".agents/skills/skill_registry.json"))
    routes = {r["id"]: r for r in registry["routes"]}
    assert "/工作0" in routes["work-slot-routing"]["keywords"]
    for route_id in [
        "scheduler-authoring",
        "scheduler-simulation",
        "work-slot-routing",
        "dispatching-workflow",
        "remote-execution-guard",
        "issue-closure-gate",
        "executable-continuity-controller",
        "remote-qa-monitoring",
        "force-takeover",
    ]:
        assert "flow-v2-execution" in routes[route_id]["required_skills"], route_id


def test_ai_library_execution_authority_is_flow_v2():
    authority = text(ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    resume = text(ROOT / "個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md")
    assert "contract=flow-v2-execution role=CURRENT" in authority
    assert "coord/execution-v2" in authority
    assert "FLOW_V2_SCHEDULED_RESUME_V1" in resume
    assert "coord/execution-v2" in resume
    for token in BANNED_ACTIVE:
        assert token not in resume


def test_governance_manifest_includes_flow_v2_canonical_skill_prefix():
    manifest = json.loads(text(ROOT / "docs/governance/governance_mirror_manifest.json"))
    assert ".agents/skills/engineering/flow-v2-execution" in manifest["governance_prefixes"]
