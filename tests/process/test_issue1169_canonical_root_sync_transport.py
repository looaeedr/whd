import pytest

from tools.post_integration_durability import (
    DRIVE_MIRROR_ROOT,
    RootSyncError,
    build_root_sync_receipt,
    sync_canonical_root_to_accepted_head,
)


def _done_record():
    return {
        "issue": 1169,
        "generation": 1,
        "state": "DONE",
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def test_direct_canonical_drive_root_sync_transport_is_retired():
    with pytest.raises(RootSyncError, match="CANONICAL_DRIVE_ROOT_SYNC_RETIRED"):
        sync_canonical_root_to_accepted_head(
            execution_record=_done_record(), accepted_tree_sha="b" * 40
        )


def test_optional_mirror_receipt_proves_exact_accepted_head_and_tree_without_authority():
    receipt = build_root_sync_receipt(
        accepted_sha="a" * 40, accepted_tree_sha="b" * 40,
        root_head_sha="a" * 40, root_tree_sha="b" * 40,
    )
    assert receipt["status"] == "VERIFIED"
    assert receipt["canonical_root"] == "GITHUB_PRODUCTION_X"
    assert receipt["drive_mirror_root"] == DRIVE_MIRROR_ROOT
    assert receipt["authority"] is False


def test_optional_mirror_receipt_rejects_non_exact_readback():
    with pytest.raises(ValueError, match="HEAD does not match"):
        build_root_sync_receipt(
            accepted_sha="a" * 40, accepted_tree_sha="b" * 40,
            root_head_sha="c" * 40, root_tree_sha="b" * 40,
        )
    with pytest.raises(ValueError, match="tree does not match"):
        build_root_sync_receipt(
            accepted_sha="a" * 40, accepted_tree_sha="b" * 40,
            root_head_sha="a" * 40, root_tree_sha="c" * 40,
        )
