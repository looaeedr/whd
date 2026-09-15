from pathlib import Path

import pytest

from tools.knowledge_governance import _authority_rows, parse_doc_metadata


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
DIMENSION_CONTRACT = "phase6-dimension-semantics"
DIMENSION_OWNER = "個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md"

pytestmark = pytest.mark.governance


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _metadata(rel: str):
    return parse_doc_metadata(_text(rel), path=rel)


def _window(text: str, needle: str, radius: int = 700) -> str:
    pos = text.find(needle)
    assert pos >= 0, f"missing semantic marker: {needle}"
    return text[max(0, pos - radius): pos + len(needle) + radius]


def _current_owner(contract: str) -> str:
    rows = [
        row
        for row in _authority_rows(ROOT)
        if row.get("contract") == contract and row.get("role") == "CURRENT"
    ]
    assert len(rows) == 1, (contract, rows)
    return rows[0]["path"]


def test_reference_ledgers_do_not_claim_current_dimension_semantics_authority() -> None:
    expected = {
        "AI_HANDOFF.md": ("REFERENCE", "handoff-ledger"),
        "CONTEXT.md": ("REFERENCE", "project-reference"),
        "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md": (
            "REFERENCE",
            "pitfall-ledger",
        ),
    }
    for rel, (role, contract) in expected.items():
        metadata = _metadata(rel)
        assert metadata.role == role, rel
        assert metadata.contract == contract, rel
        assert metadata.canonical is None, rel
        assert metadata.schema == "WHD_DOC_META_V1", rel
        assert metadata.contract != DIMENSION_CONTRACT, rel


def test_phase6_dimension_semantics_has_one_declared_current_owner() -> None:
    authority_metadata = _metadata(AUTHORITY_MAP)
    assert authority_metadata.role == "CURRENT"
    assert authority_metadata.schema == "WHD_DOC_META_V1"

    owner = _current_owner(DIMENSION_CONTRACT)
    assert owner == DIMENSION_OWNER
    assert (ROOT / owner).is_file()

    owner_metadata = _metadata(owner)
    assert owner_metadata.role == "CURRENT"
    assert owner_metadata.contract == DIMENSION_CONTRACT
    assert owner_metadata.canonical is None
    assert owner_metadata.schema == "WHD_DOC_META_V1"


def test_current_overlay_v3_semantics_are_verified_at_canonical_owner_only() -> None:
    text = _text(_current_owner(DIMENSION_CONTRACT))
    current = _window(text, "ENDCAP_TOP_OVERLAY_STANDARD_V1@3")
    assert "40×39 + 15×2" in current
    assert "formed FW" in current and "shadow" in current
    assert "不得作正式 CUTTING oracle" in current


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
    text = _text(_current_owner(DIMENSION_CONTRACT))
    window = _window(text, "40×23 + 16×4", radius=900)
    assert "fixture" in window.lower()
    assert "INSERT_OVERLAY" in window
    assert "只能標為" in window


def test_receiving_and_vault_depth_compensation_are_explicitly_distinct() -> None:
    text = _text(_current_owner(DIMENSION_CONTRACT))
    assert "Receiving EndCap D core = `D - 2T`" in text
    assert "Vault EndCap D core = `D - 3T`" in text


def test_current_terms_keep_overlay_preset_and_wrap_as_distinct_layers() -> None:
    text = _text(_current_owner(DIMENSION_CONTRACT))
    assert "OVERLAY = 貼外" in text
    assert "包覆貼外 = 高階 preset" in text
    assert "WRAP = 下方局部包覆 Joint" in text
    assert "包覆貼外 ≠ OVERLAY ≠ WRAP" in text


def test_pitfall_ledger_remains_reference_evidence_not_dimension_authority() -> None:
    rel = "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md"
    metadata = _metadata(rel)
    assert metadata.role == "REFERENCE"
    assert metadata.contract == "pitfall-ledger"
    assert _current_owner(DIMENSION_CONTRACT) != rel
