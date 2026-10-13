"""Documentation status must distinguish the implemented three-shard pipeline from historical design approval."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-revision-notes.md"
PARENT = ROOT / "docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md"


def test_ci_sharding_revision_notes_current_status_and_historical_record():
    text = DOC.read_text(encoding="utf-8")
    parent = PARENT.read_text(encoding="utf-8")
    header = text.split("## R1", 1)[0]
    assert "whd_doc_role: CURRENT" in header
    assert "Status: CURRENT normative revision contract" in header
    assert "Original status record (2026-09-16)" in header
    assert "implementation not yet authorized" in header
    assert "implementation readback" in header
    assert "three product regression shards" in header
    assert "tools/test_shard_execution.py" in header
    assert "every revision requirement (R1–R5)" in header
    assert "2026-10-11" in parent
    for section in ("## R1", "## R2", "## R3", "## R4", "## R5"):
        assert section in text
