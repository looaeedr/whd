"""Historical data/recovery sync helper; NEVER a CURRENT execution entry.

Production Git is repository-content authority. Executor-local repo workspaces
own authoring/test execution. This legacy data helper has no startup, routing,
delivery, FINALIZE or closure authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Mapping


SYNC_MANIFEST_SCHEMA = "WHD_WORKSPACE_CANONICAL_SYNC_MANIFEST_V1"
MIRROR_RECEIPT_SCHEMA = "WHD_WORKSPACE_CANONICAL_MIRROR_RECEIPT_V1"
OUTBOUND_RELAY_SCHEMA = "WHD_WORKSPACE_CANONICAL_OUTBOUND_RELAY_V1"
OUTBOUND_RECEIPT_SCHEMA = "WHD_WORKSPACE_CANONICAL_OUTBOUND_RECEIPT_V1"
DEFAULT_RECEIPT = ".workspace-canonical-sync-receipt.json"
RECONCILE_REQUIRED = "WORKSPACE_CANONICAL_RECONCILE_REQUIRED"\nRETIRED_ERROR = "WORKSPACE_CANONICAL_SYNC_RETIRED_USE_EXECUTOR_LOCAL_WORKSPACE"


class WorkspaceCanonicalSyncError(ValueError):
    """Raised when workspace/canonical identity cannot be proven."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WorkspaceCanonicalSyncError(f"{label} must be an object")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _rel_path(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or text in {".", ".."}:
        raise WorkspaceCanonicalSyncError("path must be repository-relative")
    parts = [part for part in text.split("/") if part]
    if any(part == ".." for part in parts):
        raise WorkspaceCanonicalSyncError("path traversal is forbidden")
    return "/".join(parts)


def _hex(value: object, *, label: str, length: int = 64) -> str:
    text = str(value or "").strip().lower()
    if len(text) != length or any(ch not in "0123456789abcdef" for ch in text):
        raise WorkspaceCanonicalSyncError(f"{label} must be {length}-hex")
    return text


def _manifest_digest(entries: Iterable[Mapping[str, object]]) -> str:
    normalized = []
    for entry in entries:
        row = dict(entry)
        row["path"] = _rel_path(row.get("path"))
        normalized.append(row)
    body = json.dumps(sorted(normalized, key=lambda item: item["path"]), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _entries(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    if manifest.get("schema") != SYNC_MANIFEST_SCHEMA:
        raise WorkspaceCanonicalSyncError("unexpected sync manifest schema")
    raw = manifest.get("entries")
    if not isinstance(raw, list):
        raise WorkspaceCanonicalSyncError("manifest entries must be a list")
    seen: set[str] = set()
    entries: list[dict[str, object]] = []
    for raw_entry in raw:
        entry = dict(_mapping(raw_entry, "manifest entry"))
        path = _rel_path(entry.get("path"))
        if path in seen:
            raise WorkspaceCanonicalSyncError(f"duplicate path: {path}")
        seen.add(path)
        op = str(entry.get("operation") or "write").strip().lower()
        if op not in {"write", "delete"}:
            raise WorkspaceCanonicalSyncError(f"unsupported operation for {path}: {op}")
        entry["path"] = path
        entry["operation"] = op
        if op == "write":
            _hex(entry.get("sha256"), label=f"{path} sha256")
            size = int(entry.get("size") if entry.get("size") is not None else -1)
            if size < 0:
                raise WorkspaceCanonicalSyncError(f"{path} size must be non-negative")
            entry["size"] = size
        entries.append(entry)
    return entries


def _receipt_path(workspace_root: Path) -> Path:
    return workspace_root / DEFAULT_RECEIPT


def load_mirror_receipt(workspace_root: str | Path) -> dict[str, object] | None:
    path = _receipt_path(Path(workspace_root))
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != MIRROR_RECEIPT_SCHEMA:
        raise WorkspaceCanonicalSyncError("mirror receipt schema mismatch")
    return payload


def _write_receipt(workspace_root: Path, receipt: Mapping[str, object]) -> None:
    _receipt_path(workspace_root).write_text(
        json.dumps(dict(receipt), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _entry_source_bytes(entry: Mapping[str, object], source_root: Path | None) -> bytes:
    if "content" in entry:
        return str(entry["content"]).encode("utf-8")
    source_path = entry.get("source_path")
    if source_root is None or not source_path:
        raise WorkspaceCanonicalSyncError(f"{entry['path']} write requires content or source_path")
    path = source_root / _rel_path(source_path)
    return path.read_bytes()


def validate_sync_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    entries = _entries(manifest)
    digest = str(manifest.get("canonical_generation_or_manifest_digest") or "").strip()
    if not digest:
        digest = _manifest_digest(entries)
    canonical = str(manifest.get("canonical_root_identity") or "HISTORICAL_SHARED_ZERO_DATA").strip()
    if not canonical:
        raise WorkspaceCanonicalSyncError("canonical_root_identity must be nonblank")
    return {
        "schema": SYNC_MANIFEST_SCHEMA,
        "canonical_root_identity": canonical,
        "canonical_generation_or_manifest_digest": digest,
        "entries": entries,
    }


def sync_in(
    manifest: Mapping[str, object],
    *,
    workspace_root: str | Path = "/workspace/whd",
    source_root: str | Path | None = None,
) -> dict[str, object]:
    """Incrementally apply canonical manifest entries to the workspace mirror."""

    workspace = Path(workspace_root)
    workspace.mkdir(parents=True, exist_ok=True)
    source = Path(source_root) if source_root is not None else None
    validated = validate_sync_manifest(manifest)
    entries = list(validated["entries"])  # type: ignore[index]
    previous = load_mirror_receipt(workspace)
    if (
        previous
        and previous.get("canonical_generation_or_manifest_digest")
        == validated["canonical_generation_or_manifest_digest"]
    ):
        all_match = True
        for entry in entries:
            target = workspace / str(entry["path"])
            if entry["operation"] == "delete":
                all_match = all_match and not target.exists()
            else:
                all_match = all_match and target.exists() and file_sha256(target) == str(entry["sha256"])
        if all_match:
            return {**previous, "sync_state": "REUSED"}

    applied: list[dict[str, object]] = []
    for entry in entries:
        target = workspace / str(entry["path"])
        before_expected = str(entry.get("previous_sha256") or "").strip().lower()
        if target.exists() and before_expected:
            current = file_sha256(target)
            if current != before_expected:
                raise WorkspaceCanonicalSyncError(RECONCILE_REQUIRED)
        if entry["operation"] == "delete":
            if target.exists():
                target.unlink()
            applied.append({"path": entry["path"], "operation": "delete"})
            continue
        data = _entry_source_bytes(entry, source)
        observed_hash = _sha256_bytes(data)
        if observed_hash != str(entry["sha256"]):
            raise WorkspaceCanonicalSyncError(f"hash mismatch for {entry['path']}")
        if len(data) != int(entry["size"]):
            raise WorkspaceCanonicalSyncError(f"size mismatch for {entry['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if file_sha256(target) != observed_hash:
            raise WorkspaceCanonicalSyncError(f"readback hash mismatch for {entry['path']}")
        applied.append({
            "path": entry["path"],
            "operation": "write",
            "size": len(data),
            "sha256": observed_hash,
        })

    receipt = {
        "schema": MIRROR_RECEIPT_SCHEMA,
        "authority": False,
        "workspace_root": str(workspace),
        "canonical_root_identity": validated["canonical_root_identity"],
        "canonical_generation_or_manifest_digest": validated["canonical_generation_or_manifest_digest"],
        "mirror_generation_or_manifest_digest": validated["canonical_generation_or_manifest_digest"],
        "sync_state": "GREEN",
        "entries": applied,
    }
    _write_receipt(workspace, receipt)
    return receipt


def status(
    *,
    workspace_root: str | Path = "/workspace/whd",
    manifest: Mapping[str, object] | None = None,
) -> dict[str, object]:
    workspace = Path(workspace_root)
    receipt = load_mirror_receipt(workspace)
    dirty_paths: list[str] = []
    drifted_paths: list[str] = []
    if receipt:
        for entry in receipt.get("entries", []):
            item = _mapping(entry, "receipt entry")
            rel = _rel_path(item.get("path"))
            target = workspace / rel
            if item.get("operation") == "delete":
                if target.exists():
                    dirty_paths.append(rel)
            elif not target.exists() or file_sha256(target) != str(item.get("sha256")):
                dirty_paths.append(rel)
    if manifest is not None:
        for entry in _entries(manifest):
            target = workspace / str(entry["path"])
            if entry["operation"] == "delete":
                if target.exists():
                    drifted_paths.append(str(entry["path"]))
            elif not target.exists() or file_sha256(target) != str(entry["sha256"]):
                drifted_paths.append(str(entry["path"]))
    return {
        "workspace_root": str(workspace),
        "canonical_root_identity": (receipt or {}).get("canonical_root_identity"),
        "canonical_generation_or_manifest_digest": (manifest or receipt or {}).get("canonical_generation_or_manifest_digest"),
        "mirror_generation_or_manifest_digest": (receipt or {}).get("mirror_generation_or_manifest_digest"),
        "dirty_paths": sorted(dirty_paths),
        "drifted_paths": sorted(drifted_paths),
        "sync_state": "GREEN" if not dirty_paths and not drifted_paths and receipt else "DRIFTED",
    }


def _lane_prefix(lane: str) -> str:
    lane = lane.strip().lower()
    if lane not in {"docs", "body"}:
        raise WorkspaceCanonicalSyncError("lane must be docs or body")
    return f"HISTORICAL_SHARED_ZERO_DATA/{lane}"


def prepare_outbound(
    *,
    lane: str,
    paths: Iterable[str],
    workspace_root: str | Path = "/workspace/whd",
    base_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    workspace = Path(workspace_root)
    receipt = dict(base_receipt or load_mirror_receipt(workspace) or {})
    if receipt.get("schema") != MIRROR_RECEIPT_SCHEMA:
        raise WorkspaceCanonicalSyncError("prepare-outbound requires a mirror receipt")
    seen: set[str] = set()
    operations: list[dict[str, object]] = []
    base_hashes = {
        str(_mapping(entry, "receipt entry")["path"]): str(_mapping(entry, "receipt entry").get("sha256") or "")
        for entry in receipt.get("entries", [])
    }
    for raw in paths:
        rel = _rel_path(raw)
        if rel in seen:
            raise WorkspaceCanonicalSyncError(f"duplicate path: {rel}")
        seen.add(rel)
        target = workspace / rel
        before = base_hashes.get(rel, "")
        if target.exists():
            after = file_sha256(target)
            op = "write"
            size = target.stat().st_size
        else:
            after = ""
            op = "delete"
            size = 0
        operations.append({
            "path": rel,
            "operation": op,
            "before_sha256": before,
            "after_sha256": after,
            "size": size,
        })
    if not operations:
        raise WorkspaceCanonicalSyncError("outbound relay requires at least one path")
    return {
        "schema": OUTBOUND_RELAY_SCHEMA,
        "authority": False,
        "lane": lane.strip().lower(),
        "historical_shared_zero_identity": _lane_prefix(lane),
        "base_canonical_generation_or_manifest_digest": receipt["canonical_generation_or_manifest_digest"],
        "workspace_root": str(workspace),
        "operations": operations,
    }


def verify_outbound(relay: Mapping[str, object], readback: Mapping[str, object]) -> dict[str, object]:
    if relay.get("schema") != OUTBOUND_RELAY_SCHEMA:
        raise WorkspaceCanonicalSyncError("unexpected outbound relay schema")
    if readback.get("schema") != OUTBOUND_RECEIPT_SCHEMA:
        raise WorkspaceCanonicalSyncError("unexpected outbound receipt schema")
    if readback.get("lane") != relay.get("lane"):
        raise WorkspaceCanonicalSyncError("outbound receipt lane mismatch")
    expected = {
        str(_mapping(op, "relay operation")["path"]): _mapping(op, "relay operation")
        for op in relay.get("operations", [])
    }
    observed = {
        str(_mapping(op, "readback operation")["path"]): _mapping(op, "readback operation")
        for op in readback.get("operations", [])
    }
    if set(expected) != set(observed):
        raise WorkspaceCanonicalSyncError("outbound readback path set mismatch")
    for path, exp in expected.items():
        obs = observed[path]
        if exp.get("operation") != obs.get("operation") or exp.get("after_sha256") != obs.get("after_sha256"):
            raise WorkspaceCanonicalSyncError(f"outbound readback hash mismatch for {path}")
    return {**dict(readback), "status": "HISTORICAL_VERIFIED", "state": "HISTORICAL_READBACK_VERIFIED", "authority": False}


# Explicit historical aliases for audit/migration only.
historical_sync_in = sync_in
historical_status = status
historical_prepare_outbound = prepare_outbound
historical_verify_outbound = verify_outbound


def _retired_current_api(*args, **kwargs):
    raise WorkspaceCanonicalSyncError(RETIRED_ERROR)


sync_in = _retired_current_api
status = _retired_current_api
prepare_outbound = _retired_current_api
verify_outbound = _retired_current_api


def _load_json(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkspaceCanonicalSyncError("JSON payload must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync-in", "status"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest")
        cmd.add_argument("--workspace-root", default="/workspace/whd")
        cmd.add_argument("--source-root")
    out = sub.add_parser("prepare-outbound")
    out.add_argument("--lane", required=True)
    out.add_argument("--path", action="append", required=True)
    out.add_argument("--workspace-root", default="/workspace/whd")
    verify = sub.add_parser("verify-outbound")
    verify.add_argument("--relay", required=True)
    verify.add_argument("--readback", required=True)
    args = parser.parse_args(argv)

    if args.command == "sync-in":
        result = sync_in(_load_json(args.manifest), workspace_root=args.workspace_root, source_root=args.source_root)
    elif args.command == "status":
        manifest = _load_json(args.manifest) if args.manifest else None
        result = status(workspace_root=args.workspace_root, manifest=manifest)
    elif args.command == "prepare-outbound":
        result = prepare_outbound(lane=args.lane, paths=args.path, workspace_root=args.workspace_root)
    else:
        result = verify_outbound(_load_json(args.relay), _load_json(args.readback))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
