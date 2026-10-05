from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str):
    return json.loads(_read(path))


def test_current_work_root_contract_has_no_drive_or_shared_zero_execution_overlay():
    contract = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert contract["default_work_root"]["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert contract["drive_mirror"]["role"] == "MIRROR_BACKUP_ONLY"
    assert contract["drive_mirror"]["routing_forbidden"] is True
    assert contract["drive_mirror"]["authority"] is False
    assert "canonical_drive_overlay" not in contract
    assert "unpushed" not in contract
    assert "CONDITIONAL_SHARED_ZERO_DRIFT_CHECK" not in contract["required_sequence"]


def test_current_change_test_profile_never_returns_drive_work_root():
    from tools.change_test_profile import build_test_profile

    payload = build_test_profile(task="governance cleanup", changed_files=["AGENTS.md"])
    ws = payload["workspace"]
    assert ws["root_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert ws["production_branch"] == "cleanup/2d-3d-sync"
    assert ws["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert ws["drive_required"] is False
    assert ws["shared_zero_required"] is False
    assert "/Google Drive/WHD" not in json.dumps(ws, ensure_ascii=False)


def test_current_work_root_machine_rejects_drive_read_mode_and_shared_zero_helpers():
    from tools.work_root_gate import (
        READ_MODE_GOOGLE_DRIVE,
        build_work_root_gate_evidence,
        unpushed_zero_path,
        worker_candidate_path,
    )

    contract = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    entries = [".git", ".agents", ".github", "AGENTS.md", "tools", "tests", "ae_engine", "gui_modules"]
    with pytest.raises(ValueError, match="DRIVE_WORK_ROOT_RETIRED"):
        build_work_root_gate_evidence(
            gate_payload=contract,
            read_mode=READ_MODE_GOOGLE_DRIVE,
            execution_mode="INTERACTIVE",
            root_entries=entries,
            workspace_root="/workspace/whd",
        )
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        unpushed_zero_path("body")
    with pytest.raises(ValueError, match="SHARED_ZERO_ROUTING_RETIRED"):
        worker_candidate_path(lane="docs", worker="w", issue=1308)


def test_root_local_current_router_has_no_executable_shared_zero_branch():
    from tools.root_local_first_gate import build_gate_evidence

    with pytest.raises(ValueError, match="LEGACY_SHARED_ZERO_EXECUTION_INPUT_RETIRED"):
        build_gate_evidence(
            execution_mode="INTERACTIVE",
            unpushed_lane_evidence={"schema": "legacy"},
        )


def test_shared_zero_and_workspace_sync_public_execution_apis_are_retired():
    import tools.shared_unpushed_integration as shared
    import tools.workspace_canonical_sync as sync

    with pytest.raises(shared.UnpushedIntegrationError, match="SHARED_ZERO_ROUTING_RETIRED"):
        shared.classify_lane(path="AGENTS.md", ownership="governance")
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="WORKSPACE_CANONICAL_SYNC_RETIRED"):
        sync.status()


def test_post_integration_terminal_does_not_require_drive_or_lane_receipts():
    from tools.post_integration_durability import classify_post_integration_durability

    record = {
        "issue": 1308,
        "generation": 1,
        "state": "DONE",
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }
    result = classify_post_integration_durability(
        execution_record=record,
        root_sync_receipt=None,
        lane_delivery_receipt=None,
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["root_sync_status"] == "NOT_REQUESTED"
    assert result["shared_zero_lane_receipt"] == "NOT_REQUIRED"


def test_current_contracts_and_machine_owners_do_not_reintroduce_legacy_execution_phrases():
    paths = (
        ".agents/contracts/WHD_CHANGE_TEST_PROFILE_V1.json",
        ".agents/contracts/WHD_PATH_RESERVATION_V1.json",
        ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json",
        ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json",
        ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
        "tools/change_test_profile.py",
        "tools/execution_entry_contract.py",
        "tools/work_root_gate.py",
        "tools/root_local_first_gate.py",
        "tools/post_integration_durability.py",
    )
    forbidden = (
        "SHARED_ZERO_FALLBACK",
        "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME",
        "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN",
        "MERGE_TO_0_OR_CONFLICT_CHECKPOINT",
        "ROOT_TESTS_GREEN_OR_REAL_BLOCKER",
        "SHARED_0_LINEAGE_ROOT__SINGLE_WRITER_ONLY_AT_DELIVERY",
    )
    offenders = []
    for path in paths:
        text = _read(path)
        for marker in forbidden:
            if marker in text:
                offenders.append((path, marker))
    assert offenders == []


def test_current_orchestration_pipeline_uses_workspace_phase_names():
    contract = _json(".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json")
    fast = contract["orchestration_fast_path"]
    assert "WORKSPACE_MUTATE" in fast["outer_visible_pipeline"]
    assert "ROOT_MUTATE" not in fast["outer_visible_pipeline"]
    assert fast["single_writer_policy"] == "DELIVERY_SCOPE_SINGLE_WRITER_ONLY"
    assert fast["test_red_outer_action"] == "RETURN_TO_WORKSPACE_REPAIR_IN_SAME_SESSION"
