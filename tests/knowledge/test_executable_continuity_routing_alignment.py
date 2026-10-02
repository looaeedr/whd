import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
REGISTRY = ROOT / ".agents/skills/skill_registry.json"
CATALOG = ROOT / ".agents/skills/skill_catalog.json"
ENGINEERING_README = ROOT / ".agents/skills/engineering/README.md"
SKILL = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"

SKILL_ID = "executable-continuity-controller"
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"


def test_agents_completion_bridge_is_flow_v2_not_legacy_continuity() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    assert "FLOW_V2_DURABLE_COMPLETION_BRIDGE_V1" in text
    assert "execution_invocation_exit.py" in text
    assert "MERGE → FINALIZE → DONE" in text
    assert "EXECUTABLE_CONTINUITY_BRIDGE_V1" not in text
    assert "python -m tools.continuity_controller assert-finalizable" not in text


def test_registry_routes_legacy_continuity_terms_through_flow_v2() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    route = next(route for route in data["routes"] if route["id"] == SKILL_ID)
    assert route["required_skills"][0] == "flow-v2-execution"
    assert route["required_references"] == [
        "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
    ]
    for broad in ("不停工", "持續執行", "runtime cut", "task chain", "implement spec"):
        assert broad not in route["keywords"]


def test_compatibility_skill_is_mirror_bridge_to_flow_v2() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "whd_doc_role: MIRROR" in text
    assert f"whd_canonical: {FLOW}" in text
    assert "FLOW_V2_EXECUTION_BRIDGE_V1" in text
    assert "不擁有 execution state machine" in text


def test_catalog_active_routing_does_not_promote_mirror_to_semantic_current() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    policy = data["semantic_authority_policy"]
    assert policy["classification_scope"] == "ACTIVE_INVOCATION_ROUTING_ONLY"
    assert policy["canonical_classification_does_not_imply_doc_role_current"] is True
    assert policy["active_mirror_skill_allowed"] is True


def test_engineering_readme_lists_continuity_as_navigation_bridge() -> None:
    text = ENGINEERING_README.read_text(encoding="utf-8")
    assert "Navigation only" in text
    assert f"[{SKILL_ID}](./{SKILL_ID}/SKILL.md)" in text
    assert "Flow v2 runtime resume bridge" in text
