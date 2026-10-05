from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.workspace_canonical_sync as sync


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest(*entries, digest="gen-1"):
    return {
        "schema": sync.SYNC_MANIFEST_SCHEMA,
        "canonical_root_identity": "/Google Drive/WHD",
        "canonical_generation_or_manifest_digest": digest,
        "entries": list(entries),
    }


def _write_entry(path: str, text: str, previous: str | None = None):
    entry = {
        "path": path,
        "operation": "write",
        "content": text,
        "size": len(text.encode("utf-8")),
        "sha256": _sha(text),
    }
    if previous is not None:
        entry["previous_sha256"] = previous
    return entry


def _delete_entry(path: str, previous: str | None = None):
    entry = {"path": path, "operation": "delete"}
    if previous is not None:
        entry["previous_sha256"] = previous
    return entry


def test_clean_mirror_incremental_sync_and_status_green(tmp_path):
    manifest = _manifest(_write_entry("docs/a.md", "hello\n"))

    receipt = sync.sync_in(manifest, workspace_root=tmp_path)
    state = sync.status(workspace_root=tmp_path, manifest=manifest)

    assert (tmp_path / "docs/a.md").read_text(encoding="utf-8") == "hello\n"
    assert receipt["schema"] == sync.MIRROR_RECEIPT_SCHEMA
    assert receipt["authority"] is False
    assert state["sync_state"] == "GREEN"
    assert state["dirty_paths"] == []


def test_identical_generation_reuses_existing_mirror(tmp_path):
    manifest = _manifest(_write_entry("docs/a.md", "hello\n"))
    sync.sync_in(manifest, workspace_root=tmp_path)

    reused = sync.sync_in(manifest, workspace_root=tmp_path)

    assert reused["sync_state"] == "REUSED"


def test_write_and_delete_apply(tmp_path):
    old = _sha("old\n")
    (tmp_path / "delete-me.txt").write_text("old\n", encoding="utf-8")
    manifest = _manifest(
        _write_entry("new.txt", "new\n"),
        _delete_entry("delete-me.txt", previous=old),
        digest="gen-2",
    )

    sync.sync_in(manifest, workspace_root=tmp_path)

    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / "delete-me.txt").exists()


def test_path_traversal_and_duplicate_paths_reject(tmp_path):
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="path traversal"):
        sync.sync_in(_manifest(_write_entry("../escape", "x")), workspace_root=tmp_path)

    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="duplicate path"):
        sync.sync_in(
            _manifest(_write_entry("a.txt", "x"), _write_entry("a.txt", "x")),
            workspace_root=tmp_path,
        )


def test_size_and_hash_mismatch_reject(tmp_path):
    bad_hash = _manifest({
        "path": "a.txt",
        "operation": "write",
        "content": "x",
        "size": 1,
        "sha256": "0" * 64,
    })
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="hash mismatch"):
        sync.sync_in(bad_hash, workspace_root=tmp_path)

    bad_size = _manifest({
        "path": "a.txt",
        "operation": "write",
        "content": "x",
        "size": 2,
        "sha256": _sha("x"),
    })
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="size mismatch"):
        sync.sync_in(bad_size, workspace_root=tmp_path)


def test_dirty_path_overwrite_rejects_with_reconcile_required(tmp_path):
    clean = _sha("clean\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("dirty\n", encoding="utf-8")
    manifest = _manifest(_write_entry("docs/a.md", "canonical\n", previous=clean))

    with pytest.raises(sync.WorkspaceCanonicalSyncError, match=sync.RECONCILE_REQUIRED):
        sync.sync_in(manifest, workspace_root=tmp_path)


def test_prepare_outbound_is_lane_bound_and_not_authority(tmp_path):
    manifest = _manifest(_write_entry("docs/a.md", "base\n"))
    sync.sync_in(manifest, workspace_root=tmp_path)
    (tmp_path / "docs/a.md").write_text("changed\n", encoding="utf-8")

    relay = sync.prepare_outbound(lane="docs", paths=["docs/a.md"], workspace_root=tmp_path)

    assert relay["schema"] == sync.OUTBOUND_RELAY_SCHEMA
    assert relay["authority"] is False
    assert relay["canonical_shared_zero"] == "/Google Drive/WHD/.unpushed/docs/0"
    assert relay["operations"][0]["before_sha256"] == _sha("base\n")
    assert relay["operations"][0]["after_sha256"] == _sha("changed\n")


def test_prepare_outbound_rejects_stale_missing_receipt_and_duplicate_paths(tmp_path):
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="requires a mirror receipt"):
        sync.prepare_outbound(lane="docs", paths=["a.md"], workspace_root=tmp_path)

    sync.sync_in(_manifest(_write_entry("a.md", "x")), workspace_root=tmp_path)
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="duplicate path"):
        sync.prepare_outbound(lane="docs", paths=["a.md", "a.md"], workspace_root=tmp_path)


def test_verify_outbound_requires_drive_readback_hash_match(tmp_path):
    sync.sync_in(_manifest(_write_entry("docs/a.md", "base\n")), workspace_root=tmp_path)
    (tmp_path / "docs/a.md").write_text("changed\n", encoding="utf-8")
    relay = sync.prepare_outbound(lane="docs", paths=["docs/a.md"], workspace_root=tmp_path)
    readback = {
        "schema": sync.OUTBOUND_RECEIPT_SCHEMA,
        "lane": "docs",
        "operations": relay["operations"],
    }

    verified = sync.verify_outbound(relay, readback)

    assert verified["status"] == "GREEN"
    assert verified["state"] == "CANONICAL_SHARED_0_UPDATED"

    bad = json.loads(json.dumps(readback))
    bad["operations"][0]["after_sha256"] = "0" * 64
    with pytest.raises(sync.WorkspaceCanonicalSyncError, match="readback hash mismatch"):
        sync.verify_outbound(relay, bad)
