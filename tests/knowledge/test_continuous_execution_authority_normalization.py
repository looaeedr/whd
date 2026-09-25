from pathlib import Path

from tools.knowledge_governance import _authority_rows, parse_doc_metadata


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md"
OPERATIONS_SKILL = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
LEGACY_PITFALL = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"

MACHINE_CONTRACT = "continuous-execution-machine"
OPERATIONS_CONTRACT = "continuous-execution-operations"
MACHINE_OWNER = "tools/continuity_controller.py"
OPERATIONS_OWNER = ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
LEGACY_REFERENCE = "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"
REMOTE_QA_OWNER = ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"


def _rows_for(contract: str):
    return [row for row in _authority_rows(ROOT) if row["contract"] == contract]


def test_continuous_execution_machine_has_one_current_owner():
    rows = _rows_for(MACHINE_CONTRACT)
    current = sorted(row["path"] for row in rows if row["role"] == "CURRENT")
    assert current == [MACHINE_OWNER]


def test_continuous_execution_operations_has_one_current_owner_and_legacy_reference():
    rows = _rows_for(OPERATIONS_CONTRACT)
    current = sorted(row["path"] for row in rows if row["role"] == "CURRENT")
    references = sorted(row["path"] for row in rows if row["role"] == "REFERENCE")
    assert current == [OPERATIONS_OWNER]
    assert LEGACY_REFERENCE in references


def test_operations_skill_carries_current_metadata():
    metadata = parse_doc_metadata(
        OPERATIONS_SKILL.read_text(encoding="utf-8"),
        path=OPERATIONS_OWNER,
    )
    assert metadata.role == "CURRENT"
    assert metadata.contract == OPERATIONS_CONTRACT
    assert metadata.canonical is None


def test_legacy_pitfall_is_reference_and_explicitly_defers_machine_enforcement():
    text = LEGACY_PITFALL.read_text(encoding="utf-8")
    metadata = parse_doc_metadata(text, path=LEGACY_REFERENCE)
    assert metadata.role == "REFERENCE"
    assert metadata.contract == OPERATIONS_CONTRACT
    assert metadata.canonical is None
    assert MACHINE_OWNER in text
    assert OPERATIONS_OWNER in text
    assert "documentation compatibility evidence" in text
    assert "not executable enforcement" in text


def test_legacy_pitfall_does_not_assign_polling_cadence_to_continuity_controller():
    text = LEGACY_PITFALL.read_text(encoding="utf-8")
    assert REMOTE_QA_OWNER in text
    assert "polling cadence" in text
    assert "30 秒 polling 是 controller 責任" not in text
