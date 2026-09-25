from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "寫技能" / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_writing_skill_identity_and_size_contract():
    text = _text()
    assert "name: 寫技能" in text
    assert len(text.splitlines()) < 500


def test_writing_skill_is_capability_adaptive_not_claude_locked():
    text = _text()
    for required in (
        "能力偵測",
        "可用工具",
        "背景 runtime",
        "不得假裝",
    ):
        assert required in text
    assert "不得宣稱「已在背景跑」" in text
    assert "claude-with-access-to-the-skill" not in text
    assert "run_loop.py" not in text


def test_writing_skill_existing_skill_update_preserves_identity_unless_user_renames():
    text = _text()
    assert "預設保留既有名稱" in text
    assert "使用者明確要求改名" in text
    assert "frontmatter" in text
    assert "引用" in text
    assert "測試" in text


def test_writing_skill_requires_snapshot_red_green_and_independent_validation():
    text = _text()
    for required in (
        "baseline snapshot",
        "RED",
        "GREEN",
        "驗證只能判定",
        "不能反過來",
    ):
        assert required in text


def test_writing_skill_respects_repository_branch_and_preflight_rules():
    text = _text()
    assert "branch-first" in text
    assert "AGENTS.md" in text
    assert "Preflight" in text
    assert "專案規則優先" in text


def test_writing_skill_never_requires_unavailable_viewer_or_background_wait():
    text = _text()
    assert "viewer" in text.lower()
    assert "有就用，沒有就退化" in text
    assert "等待不存在" in text
    assert "本回合" in text
