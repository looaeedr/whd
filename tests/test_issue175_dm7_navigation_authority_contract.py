from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / ".agents" / "skills" / "engineering" / "截角資料入口收斂" / "SKILL.md"
AI_RULE_PATH = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD截角資料與2D入口收斂規則.md"
CANONICAL_PITFALL = "個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_dm7_contract(text: str) -> None:
    assert CANONICAL_PITFALL in text
    assert "RESTORE_CHILD_CONTEXT" in text
    assert "explicit parent" in text
    assert "stale explicit" in text
    assert "fail closed" in text


def test_corner_data_skill_points_to_canonical_dm7_contract_and_forbids_old_fallbacks():
    text = _read(SKILL_PATH)
    _assert_dm7_contract(text)
    assert "從 current parts 重新 resolve" not in text
    assert "否則取 `_phase6_box_body_piece_keys(available_parts)` 的第一個 child" not in text
    assert "stale explicit child -> remembered sibling" not in text
    assert "stale explicit child -> children[0]" not in text


def test_corner_data_ai_rule_points_to_canonical_dm7_contract_and_forbids_old_fallbacks():
    text = _read(AI_RULE_PATH)
    _assert_dm7_contract(text)
    assert "板件被移除後 stale selection 必須丟棄並重新 resolve" not in text
    assert "否則使用 authoritative workspace order 第一個 child" not in text
    assert "stale explicit child -> remembered sibling" not in text
    assert "stale explicit child -> children[0]" not in text
