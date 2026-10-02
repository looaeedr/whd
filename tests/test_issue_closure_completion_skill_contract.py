from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / ".agents" / "skills" / "engineering" / "issue-closure-gate" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
RELEASE_POLICY = ROOT / "release_required_artifacts.json"
AUTHORITY = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"

def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def test_issue_closure_skill_is_flow_v2_mirror_not_second_state_machine():
    text = _text(CLOSURE)
    for required in (
        "whd_doc_role: MIRROR",
        "whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md",
        "FLOW_V2_EXECUTION_BRIDGE_V1",
        "不擁有 execution state machine",
        "QA PASS或merge不等於完成",
        "FINALIZE",
        "DONE",
        "next_action=null",
        "record.chain structured fields",
    ):
        assert required in text

def test_issue_closure_skill_requires_durable_close_readback_before_done():
    text = _text(CLOSURE)
    assert "close Issue後fresh-read" in text
    assert "清 lease/owner" in text
    assert "保存 closure evidence" in text
    assert "歷史 evidence" in text and "不得恢復成 CURRENT execution authority" in text

def test_registry_routes_closure_through_flow_v2_and_current_authority_map():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {item["id"]: item for item in registry["routes"]}
    closure = routes["issue-closure-gate"]
    assert closure["required_skills"] == ["flow-v2-execution", "issue-closure-gate"]
    assert closure["required_references"] == [AUTHORITY]
    assert "issue-closure-gate" in routes["dispatching-workflow"]["required_skills"]
    assert "issue-closure-gate" not in routes["phase6-release-packaging"]["required_skills"]
    assert {"關單", "關議題", "Master issue", "Final Combined", "production integration"} <= set(closure["keywords"])

def test_release_policy_always_carries_issue_closure_skill_and_machine_guard():
    policy = json.loads(RELEASE_POLICY.read_text(encoding="utf-8"))
    required = set(policy["mandatory_update_files"])
    assert ".agents/skills/engineering/issue-closure-gate/SKILL.md" in required
    assert "tests/test_issue_closure_completion_skill_contract.py" in required
