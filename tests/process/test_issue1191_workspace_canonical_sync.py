from __future__ import annotations

import hashlib

import pytest

import tools.workspace_canonical_sync as sync


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest():
    text = "hello\n"
    return {
        "schema": sync.SYNC_MANIFEST_SCHEMA,
        "canonical_root_identity": "HISTORICAL_SHARED_ZERO_DATA",
        "canonical_generation_or_manifest_digest": "gen-1",
        "entries": [{
            "path": "docs/a.md",
            "operation": "write",
            "content": text,
            "size": len(text.encode("utf-8")),
            "sha256": _sha(text),
        }],
    }


@pytest.mark.parametrize("name", ("sync_in", "status", "prepare_outbound", "verify_outbound"))
def test_current_workspace_canonical_sync_api_is_retired(name):
    fn = getattr(sync, name)
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="WORKSPACE_CANONICAL_SYNC_RETIRED"):
        if name == "sync_in":
            fn(_manifest())
        elif name == "status":
            fn()
        elif name == "prepare_outbound":
            fn(lane="docs", paths=["docs/a.md"])
        else:
            fn({}, {})


def test_historical_parser_is_explicit_and_non_authoritative(tmp_path):
    receipt = sync.historical_sync_in(_manifest(), workspace_root=tmp_path)
    state = sync.historical_status(workspace_root=tmp_path, manifest=_manifest())
    assert receipt["authority"] is False
    assert receipt["canonical_root_identity"] == "HISTORICAL_SHARED_ZERO_DATA"
    assert state["sync_state"] == "GREEN"


def test_historical_outbound_no_longer_claims_current_shared_zero_state(tmp_path):
    sync.historical_sync_in(_manifest(), workspace_root=tmp_path)
    relay = sync.historical_prepare_outbound(
        lane="docs", paths=["docs/a.md"], workspace_root=tmp_path
    )
    assert relay["authority"] is False
    assert relay["historical_shared_zero_identity"] == "HISTORICAL_SHARED_ZERO_DATA/docs"
    readback = {
        "schema": sync.OUTBOUND_RECEIPT_SCHEMA,
        "lane": "docs",
        "operations": relay["operations"],
    }
    verified = sync.historical_verify_outbound(relay, readback)
    assert verified["state"] == "HISTORICAL_READBACK_VERIFIED"
    assert verified["authority"] is False
    assert "CANONICAL_SHARED_0_UPDATED" not in str(verified)
