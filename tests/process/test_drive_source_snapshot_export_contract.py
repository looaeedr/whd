from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_drive_source_snapshot_workflow_is_retired():
    assert not (ROOT / ".github/workflows/drive-source-snapshot-export.yml").exists()


def test_current_durability_is_root_sync_and_lane_finalization():
    text = (ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json").read_text(encoding="utf-8")
    assert "CANONICAL_ROOT_SYNCED_TO_MERGED_HEAD" in text
    assert "LANE_0_ROLLED_FORWARD_OR_EMPTY" in text
    assert "SOURCE_SNAPSHOT" in text  # explicitly forbidden, not authoritative
