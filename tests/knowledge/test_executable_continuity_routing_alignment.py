import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "AGENTS.md"
REGISTRY = ROOT / ".agents/skills/skill_registry.json"
CATALOG = ROOT / ".agents/skills/skill_catalog.json"
ENGINEERING_README = ROOT / ".agents/skills/engineering/README.md"
SKILL = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"

SKILL_ID = "executable-continuity-controller"
SKILL_REL = ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
BRIDGE_MARKER = "EXECUTABLE_CONTINUITY_BRIDGE_V1"


def test_agents_bridges_nonterminal_finalization_to_executable_continuity():
    text = AGENTS.read_text(encoding="utf-8")
    assert BRIDGE_MARKER in text
    assert SKILL_ID in text
    assert "assert-finalizable" in text
    assert "tools/continuity_controller.py" in text
    assert "ContinuityState" not in text
    assert "CHECKPOINT_VERSION" not in text


def test_registry_routes_executable_continuity_to_the_canonical_skill():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = [route for route in data["routes"] if route["id"] == SKILL_ID]
    assert len(routes) == 1
    route = routes[0]
    assert route["required_skills"] == [SKILL_ID]
    assert "tools/continuity_controller.py" in route["file_globs"]
    assert ".agents/skills/engineering/executable-continuity-controller/**" in route["file_globs"]


def test_catalog_and_filesystem_agree_executable_continuity_is_active_canonical():
    assert SKILL.is_file()
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert "canonical" in data["active_classifications"]
    rules = data["ordered_rules"]
    engineering_rule = next(
        rule for rule in rules if rule["glob"] == ".agents/skills/engineering/**/SKILL.md"
    )
    assert engineering_rule["classification"] == "canonical"


def test_engineering_readme_lists_skill_as_navigation_not_authority():
    text = ENGINEERING_README.read_text(encoding="utf-8")
    assert "Navigation only" in text
    assert "not Skill existence or active-status authority" in text
    assert f"[{SKILL_ID}](./{SKILL_ID}/SKILL.md)" in text
    assert "durable state / resume / finalization" in text
