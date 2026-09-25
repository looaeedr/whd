from pathlib import Path


MARKER = "INVARIANT_MANIFEST_CANONICAL_PATH_HASH"
SKILL = Path(".agents/skills/engineering/UI設計與去AI味/SKILL.md")
PITFALLS = Path("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ui_skill_records_canonical_path_hash_invariant_rule():
    text = _text(SKILL)
    assert MARKER in text, f"{MARKER} missing from UI acceptance Skill"
    assert "canonical path" in text.lower()
    assert "sha256sum" in text
    assert "snapshot" in text.lower()


def test_global_ai_pitfall_library_records_same_invariant_rule():
    text = _text(PITFALLS)
    assert MARKER in text, f"{MARKER} missing from global AI pitfall library"
    assert "canonical path" in text.lower()
    assert "sha256sum" in text
    assert "snapshot" in text.lower()
