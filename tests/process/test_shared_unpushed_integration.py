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
    ],
)
def test_current_shared_zero_execution_apis_are_retired(name, args, kwargs):
    with pytest.raises(legacy.UnpushedIntegrationError, match="SHARED_ZERO_ROUTING_RETIRED"):
        getattr(legacy, name)(*args, **kwargs)


def test_historical_aliases_are_explicit_and_non_current():
    assert callable(legacy.historical_build_lane_evidence)
    assert callable(legacy.historical_build_delivery_fileset_lock)
    assert callable(legacy.historical_finalize_delivered_paths)
    assert legacy.RETIRED_ERROR == "SHARED_ZERO_ROUTING_RETIRED_USE_WORKSPACE_DEFAULT"
