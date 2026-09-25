from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "issue292-t4-task7-extract.yml"


def test_task7_temporary_extraction_harness_is_not_shipped_after_final_cleanup():
    assert not WORKFLOW.exists()


def test_task7_durable_contract_survives_harness_cleanup():
    contract = ROOT / "tests" / "test_issue292_gui_phase2_t4_part_panels.py"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    assert "test_moved_root_methods_are_absent_or_thin_delegates" in text
    assert "test_gui_meets_reconciled_t4_root_gate" in text
