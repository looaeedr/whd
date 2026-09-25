import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "productivity" / "找技能" / "SKILL.md"
README = ROOT / ".agents" / "skills" / "productivity" / "README.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
AI_RULES = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md"
RELEASE = ROOT / "release_required_artifacts.json"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_find_skill_exists_with_chinese_identity():
    text = _skill_text()
    frontmatter = text.split("---", 2)[1]
    assert "name: 找技能" in frontmatter
    assert "# 找技能" in text


def test_find_skill_preserves_source_discovery_flow_and_quality_review():
    text = _skill_text()
    for required in (
        "理解需求",
        "leaderboard",
        "搜尋",
        "品質驗證",
        "呈現候選",
        "安裝",
        "安裝數量",
        "來源信譽",
        "GitHub stars",
    ):
        assert required in text


def test_find_skill_is_capability_adaptive_and_does_not_fake_cli_or_web_results():
    text = _skill_text()
    for required in (
        "能力偵測",
        "npx skills",
        "skills.sh",
        "有就用，沒有就退化",
        "不得假裝",
        "實際結果",
    ):
        assert required in text


def test_find_skill_requires_user_approval_before_install_and_project_admission():
    text = _skill_text()
    assert "使用者明確同意" in text
    assert "不得自動安裝" in text
    assert "不得自動納入 WHD" in text
    assert "寫技能" in text
    assert "Preflight" in text


def test_find_skill_registry_route_is_machine_readable():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in registry["routes"]}
    route = routes["skill-discovery"]
    assert "找技能" in route["required_skills"]
    assert ".agents/skills/productivity/找技能/**" in route["file_globs"]
    assert "找技能" in route["keywords"]
    assert "有沒有技能" in route["keywords"]


def test_find_skill_is_discoverable_from_productivity_readme():
    text = README.read_text(encoding="utf-8")
    assert "[找技能](./找技能/SKILL.md)" in text


def test_find_skill_boundary_is_durable_in_ai_rules():
    text = AI_RULES.read_text(encoding="utf-8")
    assert "## 找技能：外部 Skill 發現與專案納入邊界" in text
    assert "外部 Skill" in text
    assert "不得自動納入 WHD" in text
    assert "使用者明確同意" in text


def test_find_skill_and_contract_are_release_required():
    manifest = json.loads(RELEASE.read_text(encoding="utf-8"))
    mandatory = set(manifest["mandatory_update_files"])
    assert ".agents/skills/productivity/找技能/SKILL.md" in mandatory
    assert "tests/test_find_skill_contract.py" in mandatory
