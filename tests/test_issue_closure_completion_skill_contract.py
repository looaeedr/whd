from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / ".agents" / "skills" / "engineering" / "issue-closure-gate" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_issue_closure_skill_separates_code_integration_from_process_completion():
    text = _text(CLOSURE)
    for required in (
        "合併不等於關單",
        "integration != completion",
        "target integration 只是 code-state gate",
        "逐票反讀",
        "state=closed",
        "state_reason=completed",
        "code integrated, process incomplete",
        "不得回報正式完成",
    ):
        assert required in text


def test_issue_closure_skill_closes_dependency_chain_leaf_to_master():
    text = _text(CLOSURE)
    for required in (
        "leaf/current ticket",
        "closing/Final Combined ticket",
        "Master/parent",
        "依 dependency 順序",
        "所有 required child",
        "全部 CLOSED/completed",
        "不得宣告 Master 完成",
    ):
        assert required in text


def test_issue_closure_skill_requires_explicit_closure_ownership():
    text = _text(CLOSURE)
    for required in (
        "Issue Closure owner",
        "closing/acceptance ticket",
        "逐票關單",
        "不得把 target 已整合當成工單完成",
        "GitHub completion gate",
        "open issue",
    ):
        assert required in text


def test_registry_routes_dispatch_release_and_closure_to_issue_closure_gate():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {item["id"]: item for item in registry["routes"]}

    assert "issue-closure-gate" in routes
    assert "issue-closure-gate" in routes["dispatching-workflow"]["required_skills"]
    assert "issue-closure-gate" in routes["phase6-release-packaging"]["required_skills"]

    closure_route = routes["issue-closure-gate"]
    assert "issue-closure-gate" in closure_route["required_skills"]
    keywords = set(closure_route["keywords"])
    assert {"關單", "關議題", "Master issue", "Final Combined", "production integration"} <= keywords
