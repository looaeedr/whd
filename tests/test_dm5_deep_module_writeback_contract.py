from pathlib import Path


def test_dm5_scan_to_implementation_handoff_contract_is_documented():
    scan = Path(".agents/skills/engineering/掃描深模組/SKILL.md").read_text(encoding="utf-8")
    tickets = Path(".agents/skills/engineering/拆解任務工單/SKILL.md").read_text(encoding="utf-8")
    dispatch = Path(".agents/skills/engineering/派工/SKILL.md").read_text(encoding="utf-8")

    for text in (scan, tickets, dispatch):
        assert "GitHub owning Issue" in text
        assert "AI Library Writeback owner" in text
        assert "Combined Acceptance owner" in text

    assert "掃描報告不是工單" in scan
    assert "掃描深模組" in tickets
    assert "掃描深模組" in dispatch


def test_dm5_divider_physical_geometry_contract_is_written_back():
    context = Path("CONTEXT.md").read_text(encoding="utf-8")
    pitfall = Path("個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md").read_text(encoding="utf-8")
    sop = Path("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md").read_text(encoding="utf-8")

    assert "Divider Physical Geometry Contract" in context
    assert "Divider Physical Geometry Contract" in pitfall
    assert "深模組掃描候選進入實作的交接閘門" in sop

    required = (
        "frame_width_segment_index",
        "FW physical face",
        "中隔.dxf",
        "resolved geometry sinks",
        "Save",
        "Reload",
    )
    for token in required:
        assert token in context
