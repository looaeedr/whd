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


def test_historical_lane_evidence_parser_is_explicit_and_read_only():
    evidence = {
        "schema": legacy.LANE_EVIDENCE_SCHEMA,
        "lane": "docs",
        "issue": 77,
        "source_sha": "a" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "generation": 3,
        "write_paths": ["AGENTS.md"],
        "delete_paths": [],
        "manifest_digest": "b" * 64,
        "state": "FROZEN",
    }
    parsed = legacy.historical_validate_lane_evidence(evidence)
    assert parsed == evidence


def test_historical_parser_does_not_expose_current_routing_builder():
    assert callable(legacy.historical_validate_lane_evidence)
    assert legacy.RETIRED_ERROR == "SHARED_ZERO_ROUTING_RETIRED_USE_WORKSPACE_DEFAULT"
    with pytest.raises(legacy.UnpushedIntegrationError, match="SHARED_ZERO_ROUTING_RETIRED"):
        legacy.build_delivery_fileset_lock(
            lane="docs",
            generation=1,
            manifest_digest="a" * 64,
            source_zero_identity="old",
            invocation_identity="old",
            write_hashes={"AGENTS.md": "b" * 64},
        )
