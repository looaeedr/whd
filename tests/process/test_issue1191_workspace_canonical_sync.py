import pytest

import tools.workspace_canonical_sync as sync


@pytest.mark.parametrize("name", ("sync_in", "status", "prepare_outbound", "verify_outbound"))
def test_current_workspace_canonical_sync_api_is_retired(name):
    fn = getattr(sync, name)
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="WORKSPACE_CANONICAL_SYNC_RETIRED"):
        if name == "sync_in":
            fn({})
        elif name == "status":
            fn()
        elif name == "prepare_outbound":
            fn(lane="docs", paths=["AGENTS.md"])
        else:
            fn({}, {})


def test_historical_aliases_remain_explicit_for_audit_only():
    assert callable(sync.historical_sync_in)
    assert callable(sync.historical_status)
    assert callable(sync.historical_prepare_outbound)
    assert callable(sync.historical_verify_outbound)
    assert sync.RETIRED_ERROR == "WORKSPACE_CANONICAL_SYNC_RETIRED_USE_EXECUTOR_LOCAL_WORKSPACE"
