import pytest

import tools.post_integration_durability as durability


def _record(state="DONE"):
    return {
        "issue": 1169,
        "generation": 2,
        "state": state,
        "target_sha": "a" * 40,
        "lease": None,
        "next_action": None,
        "mutation_scope": {"reservation_state": "RELEASED"},
        "closure": {"issue_closed": True, "merged_sha": "a" * 40},
    }


def test_legacy_canonical_root_sync_transport_is_retired():
    with pytest.raises(
        durability.RootSyncError,
        match="CANONICAL_DRIVE_ROOT_SYNC_RETIRED_USE_MIRROR_PIPELINE",
    ):
        durability.sync_canonical_root_to_accepted_head(
            execution_record=_record(),
            accepted_tree_sha="b" * 40,
        )


def test_retired_sync_still_requires_terminal_record_before_rejection():
    with pytest.raises(ValueError, match="requires DONE"):
        durability.sync_canonical_root_to_accepted_head(
            execution_record=_record(state="ACTIVE"),
            accepted_tree_sha="b" * 40,
        )


def test_optional_mirror_receipt_is_non_authoritative():
    receipt = durability.build_root_sync_receipt(
        accepted_sha="a" * 40,
        accepted_tree_sha="b" * 40,
        root_head_sha="a" * 40,
        root_tree_sha="b" * 40,
    )
    assert receipt["status"] == "VERIFIED"
    assert receipt["canonical_root"] == "GITHUB_PRODUCTION_X"
    assert receipt["drive_mirror_root"] == "/Google Drive/WHD/WHD_MIRROR/CURRENT"
    assert receipt["authority"] is False
