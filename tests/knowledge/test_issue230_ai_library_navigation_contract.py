from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_README = ROOT / "個人AI檔案庫/README.md"
CORE_RULES = ROOT / "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md"
AUTHORITY_MAP = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ai_library_readme_is_reference_navigation_with_structured_metadata() -> None:
    text = _read(AI_README)
    assert text.startswith("---\n")
    for marker in (
        "whd_doc_role: REFERENCE",
        "whd_contract: ai-library-reference",
        "whd_canonical: null",
        "whd_schema: WHD_DOC_META_V1",
    ):
        assert marker in text


def test_ai_library_readme_matches_current_structure_and_authority_flow() -> None:
    text = _read(AI_README)
    for entry in (
        "第一層_核心檔案",
        "第二層_專案與SOP",
        "踩坑庫",
        "06_踩坑記錄與防錯經驗庫.md",
        "07_Phase6尺寸語意與標準截角母規則.md",
        "07_WHD技能發現與掃描深模組規則.md",
        "08_WHD截角資料與2D入口收斂規則.md",
        "08_WHD技能建立與修改規則.md",
        "09_WHD_Canonical_Authority_Map.md",
    ):
        assert entry in text
    assert AUTHORITY_MAP in text
    assert "先找 Authority Map" in text
    assert "CURRENT owner" in text
    assert "REFERENCE" in text


def test_ai_library_readme_uses_git_rollback_and_drops_dated_product_current_prose() -> None:
    text = _read(AI_README)
    assert "Pre-Edit 備份" not in text
    assert "Git branch / commit" in text
    for exception in ("使用者明確要求", "Git 無法", "高風險"):
        assert exception in text
    assert "二進位" in text or "binary" in text.lower()
    assert re.search(r"^## .*20\d{2}-\d{2}-\d{2}", text, re.MULTILINE) is None
    for stale_heading in (
        "最新固化",
        "3D Designer UI 固化",
        "EndCap 組合體視覺防錯",
    ):
        assert stale_heading not in text


def test_core_ai_rules_remain_reference_and_point_to_canonical_owners() -> None:
    text = _read(CORE_RULES)
    assert "role=REFERENCE" in text
    assert "[REFERENCE]" in text
    assert "AGENTS.md" in text
    assert AUTHORITY_MAP in text
    assert "04_WHD鈑金展開幾何引擎規範.md" in text
    assert "Git branch / commit" in text
    assert "不得再為每個檔案自動建立 `BACKUP/` 複本" in text
