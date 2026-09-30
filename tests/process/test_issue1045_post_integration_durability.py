import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json"


def _record(*, state="DONE", lease=None, reservation="RELEASED", next_action=None):
    return {
        "issue": 1045,
        "generation": 3,
        "state": state,
        "lease": lease,
        "next_action": next_action,
        "mutation_scope": {"reservation_state": reservation},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def _export():
    return {
        "schema": "WHD_DRIVE_SOURCE_EXPORT_V1",
        "source_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "snapshot_name": "whd-cleanup-2d-3d-sync-aaaaaaaaaaaaaaaa.zip",
        "snapshot_sha256": "c" * 64,
        "artifact_name": f"whd-drive-source-{'a' * 40}",
        "github_run_id": "123",
    }


def _artifact():
    return {
        "id": 456,
        "name": f"whd-drive-source-{'a' * 40}",
        "digest": "sha256:" + "d" * 64,
        "workflow_run": {"id": 123, "head_sha": "a" * 40},
    }


def _drive():
    return {
        "file_id": "drive-file-1",
        "name": "whd-cleanup-2d-3d-sync-aaaaaaaaaaaaaaaa.zip",
        "sha256": "c" * 64,
        "size": 12345,
    }


def _complete_manifest():
    return {
        "source_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "durable_snapshot_base_sha": "a" * 40,
        "durable_snapshot_base_tree_sha": "b" * 40,
        "durable_snapshot_file_id": "drive-file-1",
        "durable_snapshot_name": "whd-cleanup-2d-3d-sync-aaaaaaaaaaaaaaaa.zip",
        "durable_snapshot_status": "CURRENT_EXACT_HEAD",
        "export_writeback_status": "COMPLETE",
        "post_integration_export_run_id": 123,
        "post_integration_export_artifact_id": 456,
        "post_integration_export_artifact_digest": "sha256:" + "d" * 64,
        "durable_snapshot_sha256": "c" * 64,
        "durable_snapshot_readback": "VERIFIED",
        "root_local_gate_json_path": "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json",
        "root_local_gate_json_file_id": "1qOMBtDwNGK5yxq_iyfISKYYDkBITXFuV",
    }


def test_contract_keeps_execution_authority_in_flow_v2():
    from tools.post_integration_durability import validate_contract
    payload = validate_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))
    assert payload["execution_state_owner"] == "WHD_EXECUTION_RECORD_V2"
    assert payload["owner"] == "tools/post_integration_durability.py"
    assert payload["required_order"][-1] == "DURABLE_CLEANUP_COMPLETE"


def test_export_receipt_binds_run_artifact_snapshot_and_drive_readback():
    from tools.post_integration_durability import build_manifest_complete_patch, build_snapshot_writeback_receipt
    receipt = build_snapshot_writeback_receipt(export_manifest=_export(), artifact=_artifact(), drive_snapshot=_drive())
    assert receipt["status"] == "VERIFIED"
    assert receipt["artifact_id"] == 456
    assert receipt["drive_file_id"] == "drive-file-1"
    patch = build_manifest_complete_patch(receipt)
    assert patch["export_writeback_status"] == "COMPLETE"
    assert patch["durable_snapshot_status"] == "CURRENT_EXACT_HEAD"
    assert patch["durable_snapshot_readback"] == "VERIFIED"
    assert patch["root_local_gate_json_path"] == "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
    assert patch["root_local_gate_json_file_id"] == "1qOMBtDwNGK5yxq_iyfISKYYDkBITXFuV"


def test_drive_digest_mismatch_fails_closed_before_manifest_complete():
    from tools.post_integration_durability import build_snapshot_writeback_receipt
    bad = dict(_drive(), sha256="e" * 64)
    with pytest.raises(ValueError, match="Drive snapshot digest mismatch"):
        build_snapshot_writeback_receipt(export_manifest=_export(), artifact=_artifact(), drive_snapshot=bad)


def test_workspace_archive_requires_full_done_tuple():
    from tools.post_integration_durability import validate_workspace_archive_eligibility
    assert validate_workspace_archive_eligibility(_record())["eligible"] is True
    with pytest.raises(ValueError, match="lease=null"):
        validate_workspace_archive_eligibility(_record(lease={"owner": "worker.slot.0"}))
    with pytest.raises(ValueError, match="RELEASED"):
        validate_workspace_archive_eligibility(_record(reservation="ACTIVE"))
    with pytest.raises(ValueError, match="next_action=null"):
        validate_workspace_archive_eligibility(_record(next_action={"action": "MERGE"}))


def test_cleanup_tail_never_treats_done_as_enough():
    from tools.post_integration_durability import classify_post_integration_durability
    pending = dict(_complete_manifest(), export_writeback_status="PENDING_POST_INTEGRATION_EXPORT")
    result = classify_post_integration_durability(execution_record=_record(), source_manifest=pending, workspace_location="ACTIVE")
    assert result["next_action"] == "CONSUME_SOURCE_EXPORT"
    result = classify_post_integration_durability(execution_record=_record(), source_manifest=_complete_manifest(), workspace_location="ACTIVE")
    assert result["next_action"] == "ARCHIVE_WORKSPACE_TO_DONE"
    result = classify_post_integration_durability(execution_record=_record(), source_manifest=_complete_manifest(), workspace_location="DONE")
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["next_action"] is None


def test_nonterminal_or_live_work_is_never_auto_archived():
    from tools.post_integration_durability import classify_post_integration_durability
    result = classify_post_integration_durability(execution_record=_record(state="ACTIVE"), source_manifest=_complete_manifest(), workspace_location="ACTIVE")
    assert result["state"] == "NOT_TERMINAL"
    assert result["next_action"] == "WAIT_EXECUTION_DONE"


def test_export_workflow_emits_self_contained_exact_head_digest_identity():
    text = (ROOT / ".github/workflows/drive-source-snapshot-export.yml").read_text(encoding="utf-8")
    assert '"snapshot_sha256": snapshot_sha256' in text
    assert '"artifact_name": artifact_name' in text
    assert '"github_run_id": os.environ.get("GITHUB_RUN_ID")' in text


def test_root_local_skill_requires_cleanup_tail_and_authority_map_points_to_machine_owner():
    skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(encoding="utf-8")
    assert "POST_INTEGRATION_DURABILITY_HARD_GATE_V1" in skill
    assert "Flow v2 `DONE` 只代表 execution / merge / issue closure / reservation 已 terminal" in skill
    assert "DURABLE_CLEANUP_COMPLETE" in skill
    authority = (ROOT / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    assert "contract=post-integration-durability role=CURRENT path=tools/post_integration_durability.py" in authority
