from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]

def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def _json(path: str):
    return json.loads(_read(path))

def test_current_contracts_do_not_restore_drive_or_shared_zero_routing():
    work_root = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    root = _json(".agents/contracts/WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json")
    reservation = _json(".agents/contracts/WHD_PATH_RESERVATION_V1.json")
    durability = _json(".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json")
    assert "canonical_drive_overlay" not in work_root
    assert "unpushed" not in work_root
    assert "shared_zero_fallback_root" not in root["root_path_resolution_hard_gate"]
    assert "shared_zero_fallback_trigger" not in root["default_repository_content_flow"]
    assert "shared_zero_fallback_machine" not in root["default_repository_content_flow"]
    assert root["shared_unpushed_integration"]["status"] == "HISTORICAL"
    assert root["shared_unpushed_integration"]["routing_forbidden"] is True
    assert reservation["workspace_policy"] == "EXECUTOR_LOCAL_WORKSPACE_ONLY__DRIVE_SHARED_ZERO_RETIRED"
    assert durability["canonical_root"] == "GITHUB_PRODUCTION_X"
    assert durability["drive_role"] == "MIRROR_BACKUP_ONLY"

def test_retired_machine_apis_fail_closed():
    import tools.shared_unpushed_integration as shared
    import tools.workspace_canonical_sync as sync
    from tools.work_root_gate import unpushed_zero_path
    with pytest.raises(ValueError, match='SHARED_ZERO_ROUTING_RETIRED'):
        unpushed_zero_path("body")
    with pytest.raises(shared.UnpushedIntegrationError, match='SHARED_ZERO_ROUTING_RETIRED'):
        shared.classify_lane(path="AGENTS.md", ownership="governance")
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match='WORKSPACE_CANONICAL_SYNC_RETIRED'):
        sync.status()

def test_current_machine_text_has_no_legacy_execution_markers():
    paths = (
        ".agents/contracts/WHD_PATH_RESERVATION_V1.json",
        ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json",
        ".agents/contracts/WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json",
        ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json",
        "tools/post_integration_durability.py",
        "tools/root_local_first_gate.py",
        "tools/work_root_gate.py",
    )
    forbidden = (
        "SHARED_ZERO_FALLBACK",
        "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME",
        "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN",
        "MERGE_TO_0_OR_CONFLICT_CHECKPOINT",
        "ROOT_TESTS_GREEN_OR_REAL_BLOCKER",
        "SHARED_0_LINEAGE_ROOT__SINGLE_WRITER_ONLY_AT_DELIVERY",
        "CANONICAL_SHARED_0_UPDATED",
    )
    offenders = []
    for path in paths:
        text = _read(path)
        for marker in forbidden:
            if marker in text:
                offenders.append((path, marker))
    assert offenders == []

def test_terminal_completion_never_requires_drive_or_lane_receipts():
    from tools.post_integration_durability import classify_post_integration_durability
    record = {
        "issue": 1308, "generation": 1, "state": "DONE",
        "target_sha": "a" * 40, "lease": None, "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }
    result = classify_post_integration_durability(
        execution_record=record, root_sync_receipt=None, lane_delivery_receipt=None
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["next_action"] is None
    assert result["root_sync_status"] == "NOT_REQUESTED"
