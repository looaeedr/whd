from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
AGENTS = ROOT / "AGENTS.md"
AI_LIBRARY_README = ROOT / "個人AI檔案庫/README.md"
ENGINEERING_README = ROOT / ".agents/skills/engineering/README.md"
LEGACY_CONTINUITY_PITFALL = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"
HISTORICAL_API_SNAPSHOT = ROOT / "docs/superpowers/CURRENT_API_INVENTORY_20260818.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"required file is missing: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _yaml_frontmatter(text: str) -> str:
    assert text.startswith("---\n"), "governed Markdown must start with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, "governed Markdown frontmatter must be closed with ---"
    return text[4:end]


def test_red_r1_authority_map_is_permanent_map_not_ticket_era_narrative() -> None:
    text = _read(AUTHORITY_MAP)
    assert "## T1 scope boundary" not in text
    assert "## T8 Combined Acceptance guard matrix" not in text
    for contract in (
        "continuous-execution-machine",
        "continuous-execution-operations",
        "remote-qa-monitoring",
        "issue-closure",
        "skill-routing",
        "skill-classification",
        "knowledge-preflight",
        "pitfall-ledger",
    ):
        assert contract in text, f"missing permanent process contract: {contract}"


def test_red_r2_agents_bridges_to_executable_continuity_controller() -> None:
    text = _read(AGENTS)
    assert "executable-continuity-controller" in text
    assert "assert-finalizable" in text or "assert_finalizable" in text
    assert "tools/continuity_controller.py" in text


def test_red_r3_ai_library_readme_is_navigation_not_stale_rule_copy() -> None:
    text = _read(AI_LIBRARY_README)
    assert "09_WHD_Canonical_Authority_Map.md" in text
    assert "08_WHD技能建立與修改規則.md" in text
    assert "07_Phase6尺寸語意與標準截角母規則.md" in text
    assert "Pre-Edit 備份" not in text


def test_red_r4_engineering_navigation_lists_executable_continuity_skill() -> None:
    text = _read(ENGINEERING_README)
    assert "executable-continuity-controller" in text


def test_red_r5_legacy_continuity_pitfall_is_structured_reference_only() -> None:
    text = _read(LEGACY_CONTINUITY_PITFALL)
    meta = _yaml_frontmatter(text)
    assert "whd_schema: WHD_DOC_META_V1" in meta
    assert "whd_doc_role: REFERENCE" in meta
    assert "whd_contract: continuous-execution-operations" in meta
    assert "tools/continuity_controller.py" in text
    assert ".agents/skills/engineering/executable-continuity-controller/SKILL.md" in text


def test_red_r6_historical_current_named_snapshot_has_structured_historical_metadata() -> None:
    text = _read(HISTORICAL_API_SNAPSHOT)
    meta = _yaml_frontmatter(text)
    assert "whd_schema: WHD_DOC_META_V1" in meta
    assert "whd_doc_role: HISTORICAL" in meta
    assert "whd_contract: api-inventory-snapshot" in meta


def test_red_r7_authority_map_itself_has_structured_current_metadata() -> None:
    text = _read(AUTHORITY_MAP)
    meta = _yaml_frontmatter(text)
    assert "whd_schema: WHD_DOC_META_V1" in meta
    assert "whd_doc_role: CURRENT" in meta
    assert "whd_contract: knowledge-authority-map" in meta
