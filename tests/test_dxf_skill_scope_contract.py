from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dxf_modification_is_not_a_whd_project_skill():
    discovered = {path.parent.name for path in SKILLS_ROOT.rglob("SKILL.md")}
    registry = _text(SKILLS_ROOT / "skill_registry.json")
    engineering_readme = _text(SKILLS_ROOT / "engineering" / "README.md")
    router = _text(SKILLS_ROOT / "engineering" / "ask-matt" / "SKILL.md")

    assert "修改DXF" not in discovered
    assert '"修改DXF"' not in registry
    assert "[修改DXF]" not in engineering_readme
    assert "修改DXF ->" not in router


def test_part_dxf_acceptance_explicitly_stays_validation_only():
    text = _text(SKILLS_ROOT / "engineering" / "驗證板件與DXF" / "SKILL.md")
    assert "修改DXF" in text
    assert "不是本專案 Skill" in text
    assert "只負責驗證／驗收" in text
    assert "不得取代" in text
