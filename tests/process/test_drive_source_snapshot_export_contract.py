from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/drive-source-snapshot-export.yml"
SKILL = ROOT / ".agents/skills/engineering/root-local-first/SKILL.md"


def test_cleanup_push_produces_exact_head_drive_export_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "cleanup/2d-3d-sync" in text
    assert "git archive --format=zip" in text
    assert "WHD_DRIVE_SOURCE_EXPORT_V1" in text
    assert "source_sha" in text and "tree_sha" in text
    assert "actions/upload-artifact@v4" in text
    assert "${{ github.sha }}" in text


def test_export_workflow_does_not_claim_direct_drive_write_authority():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "drive_writeback_owner" in text
    assert "interactive root-local-first finalization" in text
    assert "googleapis.com/drive" not in text
    assert "rclone" not in text.lower()


def test_root_local_first_requires_post_integration_drive_refresh():
    text = SKILL.read_text(encoding="utf-8")
    assert "accepted integration" in text
    assert "CONSUME_SOURCE_EXPORT" in text
    assert "ARCHIVE_WORKSPACE_TO_DONE" in text
    assert "DURABLE_CLEANUP_COMPLETE" in text
    assert "Current Source Manifest" in text
