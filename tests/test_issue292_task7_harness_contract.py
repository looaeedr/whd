from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "issue292-t4-task7-extract.yml"


def test_task7_harness_does_not_mask_pytest_failures():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pytest -q tests/test_issue292_gui_phase2_t4_part_panels.py || true" not in text
    assert "test_moved_root_methods_are_absent_or_thin_delegates" in text
    assert "test_gui_meets_reconciled_t4_root_gate" in text


def test_task7_harness_keeps_diff_check_and_idempotent_commit_path():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git diff --cached --check" in text
    assert "git diff --cached --quiet" in text
