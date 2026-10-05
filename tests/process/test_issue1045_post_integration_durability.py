import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json"


def _record(*, state="DONE", lease=None, reservation="RELEASED", next_action=None):
    return {
        "issue": 1045,
        "generation": 3,
        "state": state,
        "target_sha": "a" * 40,
        "lease": lease,
        "next_action": next_action,
        "mutation_scope": {"reservation_state": reservation},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def _mirror_receipt():
    from tools.post_integration_durability import build_root_sync_receipt
    return build_root_sync_receipt(
        accepted_sha="a" * 40,
        accepted_tree_sha="b" * 40,
        root_head_sha="a" * 40,
        root_tree_sha="b" * 40,
    )


def test_contract_keeps_terminal_authority_in_flow_v2_not_drive():
    from tools.post_integration_durability import validate_contract
    payload = validate_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))
    assert payload["execution_state_owner"] == "WHD_EXECUTION_RECORD_V2"
    assert payload["canonical_root"] == "GITHUB_PRODUCTION_X"
    assert payload["production_branch"] == "cleanup/2d-3d-sync"
    assert payload["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert payload["shared_unpushed_root"] is None
    assert payload["root_sync_transport"] == "RETIRED_DIRECT_ROOT_SYNC_USE_MIRROR_PIPELINE"
    assert payload["root_sync_policy"]["mode"] == "OPTIONAL_MIRROR_MAINTENANCE"
    assert payload["legacy_lane_cleanup"]["terminal_gate"] is False
    assert payload["legacy_lane_cleanup"]["closure_authority"] is False


def test_terminal_execution_completes_without_drive_or_lane_receipts():
    from tools.post_integration_durability import classify_post_integration_durability
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=None, lane_delivery_receipt=None
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["next_action"] is None
    assert result["root_sync_status"] == "NOT_REQUESTED"
    assert result["legacy_lane_cleanup"] == "NOT_REQUIRED"


def test_optional_mirror_receipt_is_nonblocking_metadata():
    from tools.post_integration_durability import classify_post_integration_durability
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=_mirror_receipt(), lane_delivery_receipt=None
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["root_sync_status"] == "VERIFIED_NON_BLOCKING"


def test_invalid_mirror_receipt_does_not_reopen_terminal_issue():
    from tools.post_integration_durability import classify_post_integration_durability
    bad = dict(_mirror_receipt(), root_head_sha="d" * 40)
    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=bad, lane_delivery_receipt=None
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["root_sync_status"] == "INVALID_NON_BLOCKING"
    assert result["next_action"] is None


def test_legacy_lane_receipt_is_ignored_for_current_completion():
    from tools.post_integration_durability import classify_post_integration_durability
    result = classify_post_integration_durability(
        execution_record=_record(),
        root_sync_receipt=None,
        lane_delivery_receipt={"schema": "old"},
        legacy_lane_cleanup_requested=True,
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["legacy_lane_cleanup"] == "HISTORICAL_IGNORED"


def test_nonterminal_or_live_record_never_completes():
    from tools.post_integration_durability import classify_post_integration_durability
    for record in (
        _record(state="ACTIVE"),
        _record(lease={"owner": "worker.slot.0"}),
        _record(reservation="ACTIVE"),
        _record(next_action={"kind": "MERGE"}),
    ):
        result = classify_post_integration_durability(
            execution_record=record, root_sync_receipt=None, lane_delivery_receipt=None
        )
        assert result["state"] == "NOT_TERMINAL"
        assert result["next_action"] == "WAIT_EXECUTION_DONE"


def test_direct_drive_root_sync_entrypoint_is_retired():
    from tools.post_integration_durability import RootSyncError, sync_canonical_root_to_accepted_head
    with pytest.raises(RootSyncError, match="CANONICAL_DRIVE_ROOT_SYNC_RETIRED"):
        sync_canonical_root_to_accepted_head(
            execution_record=_record(), accepted_tree_sha="b" * 40
        )


def test_lane_receipt_builders_are_retired():
    from tools.post_integration_durability import build_lane_delivery_receipt
    with pytest.raises(ValueError, match="SHARED_ZERO_LANE_RECEIPT_RETIRED"):
        build_lane_delivery_receipt()
