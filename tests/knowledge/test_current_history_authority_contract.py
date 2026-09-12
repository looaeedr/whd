from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


ROLE_MARKERS = {
    "README.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=repo-overview -->",
    "AI_HANDOFF.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=handoff-ledger -->",
    "AGENTS.md": "<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->",
    "handoff/00_AI_HANDOFF_README.md": "<!-- WHD_DOC_ROLE role=MIRROR contract=handoff-entry POINTER_ONLY -->",
    "handoff/01_ARCHITECTURE.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=architecture-snapshot -->",
    "handoff/05_NEXT_STEPS.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=roadmap-snapshot -->",
    "目前主要任務.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=task-roadmap-snapshot -->",
    "docs/superpowers/CURRENT_API_INVENTORY_20260818.md": "<!-- WHD_DOC_ROLE role=HISTORICAL contract=api-inventory-snapshot snapshot=2026-08-18 -->",
    "docs/superpowers/README.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=superpowers-history-index -->",
    "個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=global-ai-collaboration-reference -->",
    "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md": "<!-- WHD_DOC_ROLE role=REFERENCE contract=pitfall-ledger -->",
}


def test_t7_documents_have_machine_readable_roles() -> None:
    missing = [path for path, marker in ROLE_MARKERS.items() if marker not in read(path)[:1200]]
    assert missing == []


def test_current_entrypoints_point_to_current_authorities() -> None:
    for rel in ("README.md", "AI_HANDOFF.md", "AGENTS.md", "handoff/00_AI_HANDOFF_README.md"):
        text = read(rel)[:5000]
        assert "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md" in text, rel
        assert "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md" in text, rel


def test_stale_roadmaps_and_dated_api_inventory_are_explicitly_historical() -> None:
    for rel in (
        "handoff/01_ARCHITECTURE.md",
        "handoff/05_NEXT_STEPS.md",
        "目前主要任務.md",
        "docs/superpowers/CURRENT_API_INVENTORY_20260818.md",
    ):
        prefix = read(rel)[:1200]
        assert "role=HISTORICAL" in prefix, rel
        assert "不參與 current routing" in prefix, rel

    dated = read("docs/superpowers/CURRENT_API_INVENTORY_20260818.md")[:1200]
    assert "2026-08-18" in dated
    assert "HISTORICAL SNAPSHOT" in dated


def test_ai_handoff_does_not_keep_2026_09_02_as_current_authority() -> None:
    text = read("AI_HANDOFF.md")
    assert "## [CURRENT] 2026-09-02 Runtime semantic guard" not in text
    assert "## [HISTORICAL/SUPERSEDED] 2026-09-02 Runtime semantic guard" in text


def test_global_pitfall_file_is_reference_index_not_parallel_domain_ssot() -> None:
    text = read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    prefix = text[:2200]
    assert "role=REFERENCE" in prefix
    assert "不是 CURRENT domain authority" in prefix
    assert "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md" in prefix

    collision = text.index("### 50. 先用截角公式猜 Assembly Relief")
    collision_window = text[max(0, collision - 400):collision + 650]
    assert "SUPERSEDED_BY_CERTIFIED_RELIEF_REGISTRY" in collision_window

    divider = text.index("## 2026-09-07 — Receiving Divider / 多件式箱身 / Dynamic 2D 單源規則")
    divider_window = text[max(0, divider - 250):divider + 1100]
    assert "HISTORICAL/SUPERSEDED" in divider_window
    assert "CURRENT Requirement Authority" not in divider_window


def test_global_ai_collaboration_rules_do_not_make_giant_06_the_domain_owner() -> None:
    text = read("個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md")
    assert "06_踩坑記錄與防錯經驗庫.md` 是 REFERENCE / incident ledger" in text
    assert "09_WHD_Canonical_Authority_Map.md" in text
    assert "04_WHD鈑金展開幾何引擎規範.md" in text


def test_authority_map_records_t7_current_history_roles() -> None:
    text = read("個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    required_rows = (
        "contract=agent-startup-process role=CURRENT path=AGENTS.md",
        "contract=manufacturing-architecture role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md",
        "contract=manufacturing-architecture role=HISTORICAL path=handoff/01_ARCHITECTURE.md",
        "contract=api-inventory role=HISTORICAL path=docs/superpowers/CURRENT_API_INVENTORY_20260818.md",
        "contract=pitfall-ledger role=REFERENCE path=個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
    )
    for row in required_rows:
        assert row in text


def test_historical_evidence_is_preserved_instead_of_deleted() -> None:
    assert "下一個真正階段：第二箱型" in read("handoff/05_NEXT_STEPS.md")
    assert "第一階段：先新增一個穩定 API" in read("目前主要任務.md")
    assert "generate_part()" in read("docs/superpowers/CURRENT_API_INVENTORY_20260818.md")
