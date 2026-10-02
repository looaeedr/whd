from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SKILL = ROOT / ".agents" / "skills" / "engineering" / "UI設計與去AI味" / "SKILL.md"
PART_DXF_SKILL = ROOT / ".agents" / "skills" / "engineering" / "驗證板件與DXF" / "SKILL.md"
PITFALLS = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "06_踩坑記錄與防錯經驗庫.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_issue164_unfold_workspace_ownership_is_durable():
    text = _text(UI_SKILL)
    assert "ISSUE164_UNFOLD_WORKSPACE_OWNERSHIP" in text
    assert "上方只保留 `檔案` 與 `截角資料庫`" in text
    assert "左側整欄只負責板件選擇與目前板件輸入" in text
    assert "右側控制區" in text
    assert "1.0 / 1.2 / 1.4" in text


def test_issue164_viewport_transform_is_presentation_only():
    text = _text(UI_SKILL)
    assert "ISSUE164_VIEWPORT_PRESENTATION_ONLY" in text
    assert "zoom / fit / pan" in text
    assert "PartRenderData" in text
    assert "material WKB" in text
    assert "不得回灌" in text


def test_issue164_receiving_aggregate_parent_cannot_be_hijacked_by_remembered_child():
    text = _text(PART_DXF_SKILL)
    assert "ISSUE164_RECEIVING_AGGREGATE_SELECTION_IDENTITY" in text
    assert "明確選擇 `box_body`" in text
    assert "remembered child" in text
    assert "不得" in text
    assert "`box_body:<role>`" in text


def test_issue164_pitfalls_record_history_recovery_and_supersede_old_layout_rule():
    text = _text(PITFALLS)
    for marker in (
        "ISSUE164_AGGREGATE_PARENT_NOT_CHILD_MEMORY",
        "ISSUE164_HISTORY_RECOVERY_BEFORE_REDERIVATION",
        "ISSUE164_VIEWPORT_PRESENTATION_BOUNDARY",
        "ISSUE164_LAYOUT_OWNERSHIP_AND_SCROLL",
        "SUPERSEDED_BY_ISSUE163_LAYOUT",
    ):
        assert marker in text
    assert "Git history / diff" in text
    assert "已知正確公式" in text
