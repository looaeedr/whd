from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _window(text: str, needle: str, radius: int = 700) -> str:
    pos = text.find(needle)
    assert pos >= 0, f"missing semantic marker: {needle}"
    return text[max(0, pos - radius): pos + len(needle) + radius]


def test_current_overlay_docs_point_to_v3_standard_plus_semantic_delta() -> None:
    for rel in ["AI_HANDOFF.md", "CONTEXT.md"]:
        text = _text(rel)
        assert "ENDCAP_TOP_OVERLAY_STANDARD_V1@3" in text, rel
        current = _window(text, "ENDCAP_TOP_OVERLAY_STANDARD_V1@3")
        assert "CURRENT" in current, rel
        assert "40×39 + 15×2" in current, rel
        assert "formed FW" in current and "shadow" in current, rel


def test_v2_formed_fw_contract_is_explicitly_historical_or_superseded() -> None:
    for rel in [
        "AI_HANDOFF.md",
        "CONTEXT.md",
        "個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md",
        "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
    ]:
        text = _text(rel)
        if "ENDCAP_TOP_OVERLAY_STANDARD_V1@2" not in text:
            continue
        window = _window(text, "ENDCAP_TOP_OVERLAY_STANDARD_V1@2", radius=900)
        assert ("HISTORICAL" in window or "SUPERSEDED" in window), rel
        assert "不可作 runtime oracle" in window or "不得作 runtime oracle" in window, rel


def test_40x23_is_linked_fw_insert_overlay_fixture_not_standard_overlay_oracle() -> None:
    text = _text("AI_HANDOFF.md") + "\n" + _text("CONTEXT.md")
    for occurrence in ["40×23 + 16×4"]:
        window = _window(text, occurrence, radius=900)
        assert "fixture" in window.lower()
        assert "INSERT_OVERLAY" in window
    assert "40×23 = CURRENT OVERLAY" not in text


def test_receiving_and_vault_depth_compensation_are_explicitly_distinct() -> None:
    text = _text("AI_HANDOFF.md") + "\n" + _text("07_Phase6尺寸語意與標準截角母規則.md")
    assert "Receiving EndCap D core = `D - 2T`" in text
    assert "Vault EndCap D core = `D - 3T`" in text


def test_current_terms_keep_overlay_preset_and_wrap_as_distinct_layers() -> None:
    text = _text("AI_HANDOFF.md") + "\n" + _text("07_Phase6尺寸語意與標準截角母規則.md")
    assert "OVERLAY = 貼外" in text
    assert "包覆貼外 = 高階 preset" in text
    assert "WRAP = 下方局部包覆 Joint" in text
    assert "包覆貼外 ≠ OVERLAY ≠ WRAP" in text


def test_mandatory_global_pitfall_points_to_current_overlay_v3() -> None:
    text = _text("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    current = _window(text, "ENDCAP_TOP_OVERLAY_STANDARD_V1@3", radius=900)
    assert "CURRENT" in current
    assert "40×39 + 15×2" in current
    assert "不得作 runtime oracle" in current
