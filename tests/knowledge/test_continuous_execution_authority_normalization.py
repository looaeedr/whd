from pathlib import Path

from tools.knowledge_governance import _authority_rows, parse_doc_metadata

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
FLOW_REL = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
FLOW = ROOT / FLOW_REL
COMPAT_REL = ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
COMPAT = ROOT / COMPAT_REL
LEGACY_MACHINE = "tools/continuity_controller.py"
LEGACY_REFERENCE = "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"


def _rows_for(contract: str):
    return [row for row in _authority_rows(ROOT) if row["contract"] == contract]


def test_flow_v2_is_the_current_execution_contract_owner() -> None:
    rows = _rows_for("flow-v2-execution")
    current = [row["path"] for row in rows if row["role"] == "CURRENT"]
    assert current == [FLOW_REL]


def test_legacy_continuity_machine_is_historical_only() -> None:
    rows = _rows_for("continuous-execution-machine")
    assert any(row["role"] == "HISTORICAL" and row["path"] == LEGACY_MACHINE for row in rows)
    assert not any(row["role"] == "CURRENT" and row["path"] == LEGACY_MACHINE for row in rows)


def test_continuity_entry_skill_is_mirror_not_parallel_current_owner() -> None:
    rows = _rows_for("continuous-execution-operations")
    mirror = [row for row in rows if row["role"] == "MIRROR"]
    assert mirror == [{
        "contract": "continuous-execution-operations",
        "role": "MIRROR",
        "path": COMPAT_REL,
        "canonical": FLOW_REL,
    }]

    metadata = parse_doc_metadata(COMPAT.read_text(encoding="utf-8"), path=COMPAT_REL)
    assert metadata.role == "MIRROR"
    assert metadata.canonical == FLOW_REL


def test_legacy_pitfall_is_reference_and_defers_to_flow_v2() -> None:
    text = (ROOT / LEGACY_REFERENCE).read_text(encoding="utf-8")
    metadata = parse_doc_metadata(text, path=LEGACY_REFERENCE)
    assert metadata.role == "REFERENCE"
    assert "FLOW V2 CURRENT SEMANTICS ONLY" in text
    assert "WHD_EXECUTION_RECORD_V2" in text
    assert "tools/execution_invocation_exit.py" in text
