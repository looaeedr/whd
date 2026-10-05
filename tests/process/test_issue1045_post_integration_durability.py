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


def test_contract_keeps_terminal_authority_in_git_and_flow_v2():
    from tools.post_integration_durability import validate_contract

    payload = validate_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))
    assert payload["execution_state_owner"] == "WHD_EXECUTION_RECORD_V2"
    assert payload["canonical_root"] == "GITHUB_PRODUCTION_X"
    assert payload["production_branch"] == "cleanup/2d-3d-sync"
    assert payload["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert payload["root_sync_transport"] == "RETIRED_USE_MIRROR_PIPELINE"
    assert payload["root_sync_ingress"]["status"] == "RETIRED"
    assert payload["legacy_lane_cleanup"]["status"] == "RETIRED"
    assert payload["required_order"] == [
        "FLOW_V2_DONE", "MERGE_READBACK_VERIFIED", "DURABLE_CLEANUP_COMPLETE"
    ]


def test_terminal_completion_does_not_require_drive_or_lane_receipts():
    from tools.post_integration_durability import classify_post_integration_durability

    result = classify_post_integration_durability(
        execution_record=_record(), root_sync_receipt=None, lane_delivery_receipt=None
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["next_action"] is None
    assert result["root_sync_status"] == "NOT_REQUESTED"
    assert result["shared_zero_lane_receipt"] == "NOT_REQUIRED"


def test_optional_mirror_receipt_is_nonblocking():
    from tools.post_integration_durability import classify_post_integration_durability

    result = classify_post_integration_durability(
        execution_record=_record(),
        root_sync_receipt=_mirror_receipt(),
        lane_delivery_receipt=None,
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["root_sync_status"] == "VERIFIED_NON_BLOCKING"


def test_invalid_mirror_receipt_is_nonblocking_drift():
    from tools.post_integration_durability import classify_post_integration_durability

    invalid = dict(_mirror_receipt(), root_head_sha="d" * 40)
    result = classify_post_integration_durability(
        execution_record=_record(),
        root_sync_receipt=invalid,
        lane_delivery_receipt=None,
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["root_sync_status"] == "INVALID_NON_BLOCKING"
    assert result["next_action"] is None


def test_direct_drive_root_sync_and_lane_cleanup_apis_are_retired():
    from tools.post_integration_durability import (
        RETIRED_LANE_ERROR,
        RETIRED_ROOT_SYNC_ERROR,
        RootSyncError,
        build_lane_delivery_receipt,
        sync_canonical_root_to_accepted_head,
    )

    with pytest.raises(RootSyncError, match=RETIRED_ROOT_SYNC_ERROR):
        sync_canonical_root_to_accepted_head(
            execution_record=_record(),
            accepted_tree_sha="b" * 40,
        )
    with pytest.raises(ValueError, match=RETIRED_LANE_ERROR):
        build_lane_delivery_receipt(
            lane="docs",
            issue=1045,
            generation=7,
            merged_sha="a" * 40,
            manifest_digest="c" * 64,
            delivered_paths=["AGENTS.md"],
            lane_state_after="EMPTY",
        )


def test_historical_lane_receipt_is_ignored_for_current_completion():
    from tools.post_integration_durability import (
        classify_post_integration_durability,
        historical_build_lane_delivery_receipt,
    )

    old = historical_build_lane_delivery_receipt(
        lane="docs",
        issue=1045,
        generation=7,
        merged_sha="a" * 40,
        manifest_digest="c" * 64,
        delivered_paths=["AGENTS.md"],
        lane_state_after="EMPTY",
    )
    result = classify_post_integration_durability(
        execution_record=_record(),
        root_sync_receipt=None,
        lane_delivery_receipt=old,
        legacy_lane_cleanup_requested=True,
    )
    assert result["state"] == "DURABLE_CLEANUP_COMPLETE"
    assert result["shared_zero_lane_receipt"] == "HISTORICAL_IGNORED"


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
