from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dm7_validation_skill_keeps_navigation_identity_contract():
    text = _read(".agents/skills/engineering/驗證板件與DXF/SKILL.md")
    for marker in (
        "DM7_OPERATOR_NAVIGATION_VALIDATION_CONTRACT",
        "manufacturing physical identity / topology",
        "operator explicit identity",
        "navigation memory",
        "UI hierarchy projection",
        "stale explicit child",
        "remembered sibling",
        "children[0]",
        "Corner Data selection 是 view-only",
        "Save→Reload 保存 authoritative project/workspace state",
    ):
        assert marker in text


def test_dm7_ai_pitfall_keeps_fail_closed_and_projection_rules():
    text = _read("個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md")
    for marker in (
        "DM7_OPERATOR_NAVIGATION_DURABLE_CONTRACT",
        "explicit parent -> remembered child",
        "stale child -> remembered sibling",
        "stale child -> children[0]",
        "Hierarchy 只是 projection",
        "不得為了 UI 好看自行創造 parent",
        "navigation memory、UI hierarchy、display labels 不升格 persistence truth",
        "Validation boundary",
    ):
        assert marker in text
