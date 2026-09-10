import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_skill_authoring_route_requires_writing_skill_and_ai_reference():
    registry = json.loads((ROOT / ".agents" / "skills" / "skill_registry.json").read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in registry["routes"]}
    route = routes["skill-authoring"]

    assert "寫技能" in route["required_skills"]
    assert ".agents/skills/**" in route["file_globs"]
    assert "修改技能" in route["keywords"]
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in route["required_references"]


def test_skill_authoring_ai_rule_points_back_to_canonical_writing_skill():
    text = (ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md").read_text(encoding="utf-8")
    assert ".agents/skills/engineering/寫技能/SKILL.md" in text
    assert "不得假裝工具存在" in text
    assert "使用者明確要求改名" in text
