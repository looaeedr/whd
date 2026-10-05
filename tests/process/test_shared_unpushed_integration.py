import pytest

import tools.shared_unpushed_integration as legacy


@pytest.mark.parametrize(
    "name,args,kwargs",
    [
        ("classify_lane", (), {"path": "AGENTS.md", "ownership": "governance"}),
        ("build_lane_evidence", (), {
            "lane": "docs", "issue": 1, "source_sha": "a" * 40,
            "target_branch": "cleanup/2d-3d-sync", "generation": 1,
            "write_paths": ["AGENTS.md"],
        }),
        ("next_generation", (), {"latest_generation": 1, "has_conflict": False}),
        ("build_conflict_checkpoint", (), {
            "lane": "docs", "path": "AGENTS.md", "base_generation": 1,
            "latest_generation": 2, "base_hash": "base", "latest_hash": "latest",
            "worker_hash": "worker", "conflict_hunks": ["x"], "worker": "w", "issue": "1",
        }),
    ],
)
def test_current_shared_zero_execution_apis_are_retired(name, args, kwargs):
    with pytest.raises(legacy.UnpushedIntegrationError, match="SHARED_ZERO_ROUTING_RETIRED"):
        getattr(legacy, name)(*args, **kwargs)


def test_explicit_historical_parser_can_read_old_lane_evidence():
    item = legacy.historical_build_lane_evidence(
        lane="docs",
        issue=77,
        source_sha="a" * 40,
        target_branch="cleanup/2d-3d-sync",
        generation=3,
        write_paths=["AGENTS.md"],
        manifest_digest="b" * 64,
    )
    assert item["schema"] == legacy.LANE_EVIDENCE_SCHEMA
    assert item["lane"] == "docs"
    assert item["state"] == "ACTIVE"


def test_explicit_historical_conflict_parser_remains_fail_closed_for_audit():
    cp = legacy.historical_build_conflict_checkpoint(
        lane="docs",
        path="AGENTS.md",
        base_generation=1,
        latest_generation=2,
        base_hash="base",
        latest_hash="latest",
        worker_hash="worker",
        conflict_hunks=["both touched line"],
        worker="work0",
        issue="77",
    )
    with pytest.raises(legacy.UnpushedIntegrationError, match="explicit user conflict decision"):
        legacy.historical_assert_conflict_checkpoint_blocks_action(cp, action="HISTORICAL_REPLAY")


def test_historical_helper_names_are_explicitly_prefixed():
    assert callable(legacy.historical_build_lane_evidence)
    assert callable(legacy.historical_build_delivery_fileset_lock)
    assert callable(legacy.historical_finalize_delivered_paths)
    assert legacy.RETIRED_ERROR == "SHARED_ZERO_ROUTING_RETIRED_USE_WORKSPACE_DEFAULT"
