import pytest
from tools.work_root_gate import (
    DEFAULT_DRIVE_FOLDER_ID, DRIVE_CONTRACT_PATH, EVIDENCE_SCHEMA, GATE_SCHEMA,
    READ_MODE_GOOGLE_DRIVE, UNPUSHED_ROOT, build_work_root_gate_evidence,
    unpushed_zero_path, verify_root_entries, worker_candidate_path,
)

ROOT_ENTRIES = [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules", ".unpushed"]

def gate():
    return {
        "schema": GATE_SCHEMA, "status": "CURRENT",
        "default_work_root": {"provider": "google_drive", "library_path": "/Google Drive/WHD", "drive_folder_id": DEFAULT_DRIVE_FOLDER_ID},
        "required_root_entries": ROOT_ENTRIES,
        "unpushed": {"root": UNPUSHED_ROOT},
    }

def test_new_drive_root_identity_and_full_repo_layout():
    ev = build_work_root_gate_evidence(gate_payload=gate(), read_mode=READ_MODE_GOOGLE_DRIVE, execution_mode="INTERACTIVE", root_entries=ROOT_ENTRIES)
    assert ev["schema"] == EVIDENCE_SCHEMA
    assert ev["source"] == DRIVE_CONTRACT_PATH
    assert ev["drive_folder_id"] == "1XEh4VRM9oXhPhGvGb8UyDNGZs61AC0NN"

def test_legacy_control_root_layout_is_fail_closed():
    with pytest.raises(ValueError, match="LEGACY_CONTROL_ROOT_LAYOUT_FORBIDDEN"):
        verify_root_entries(ROOT_ENTRIES + ["source"])

def test_unpushed_paths_replace_work_active():
    assert unpushed_zero_path("body") == "/Google Drive/WHD/.unpushed/body/0"
    assert unpushed_zero_path("docs") == "/Google Drive/WHD/.unpushed/docs/0"
    assert worker_candidate_path(lane="docs", worker="work0", issue=1200).startswith("/Google Drive/WHD/.unpushed/docs/workers/work0/")
