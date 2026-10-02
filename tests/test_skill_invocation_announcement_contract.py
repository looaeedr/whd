from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
WRITING_SKILL = ROOT / ".agents" / "skills" / "engineering" / "寫技能" / "SKILL.md"
AI_RULE = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md"

MARKER = "SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1"
FORMAT = '使用「<技能名>」技能…'


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_global_agents_has_skill_invocation_announcement_hard_gate():
    text = _text(AGENTS)
    assert MARKER in text
    assert FORMAT in text
    assert "第一個 user-visible" in text
    assert "不得先輸出" in text
    assert "announcement 本身不算 Skill execution evidence" in text


def test_skill_authoring_preserves_global_invocation_announcement_contract():
    text = _text(WRITING_SKILL)
    assert MARKER in text
    assert FORMAT in text
    assert "所有 canonical Skill" in text
    assert "不得在個別 Skill 關閉" in text


def test_ai_library_durably_records_skill_invocation_announcement_gate():
    text = _text(AI_RULE)
    assert MARKER in text
    assert FORMAT in text
    assert "使用者可見輸出的最前面" in text
    assert "只有實際要使用 Skill 時才公告" in text
    assert "announcement 不能取代" in text
