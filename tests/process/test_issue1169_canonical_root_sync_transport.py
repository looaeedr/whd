import pytest

from tools import post_integration_durability as durability


def _record(*, state="DONE", reservation="RELEASED", issue_closed=True):
    return {
        "issue": 1169,
        "generation": 1,
        "state": state,
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": reservation},
        "closure": {"issue_closed": issue_closed, "merged_sha": "a" * 40},
    }


def test_direct_canonical_drive_root_sync_transport_is_retired():
    with pytest.raises(durability.RootSyncError, match="CANONICAL_DRIVE_ROOT_SYNC_RETIRED"):
        durability.sync_canonical_root_to_accepted_head(
            execution_record=_record(),
            accepted_tree_sha="b" * 40,
        )


def test_retired_sync_still_requires_terminal_record_before_rejection():
    with pytest.raises(ValueError, match="DONE"):
        durability.sync_canonical_root_to_accepted_head(
            execution_record=_record(state="ACTIVE"),
            accepted_tree_sha="b" * 40,
        )


def test_optional_mirror_receipt_is_non_authoritative_and_exact():
    receipt = durability.build_root_sync_receipt(
        accepted_sha="a" * 40,
        accepted_tree_sha="b" * 40,
        root_head_sha="a" * 40,
        root_tree_sha="b" * 40,
    )
    assert receipt["status"] == "VERIFIED_NON_BLOCKING"
    assert receipt["authority"] is False
    assert receipt["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert durability.validate_root_sync_receipt(
        receipt, expected_merged_sha="a" * 40
    ) == receipt


def test_mirror_receipt_rejects_wrong_head_or_tree():
    with pytest.raises(ValueError, match="HEAD"):
        durability.build_root_sync_receipt(
            accepted_sha="a" * 40,
            accepted_tree_sha="b" * 40,
            root_head_sha="d" * 40,
            root_tree_sha="b" * 40,
        )
    with pytest.raises(ValueError, match="tree"):
        durability.build_root_sync_receipt(
            accepted_sha="a" * 40,
            accepted_tree_sha="b" * 40,
            root_head_sha="a" * 40,
            root_tree_sha="d" * 40,
        )
