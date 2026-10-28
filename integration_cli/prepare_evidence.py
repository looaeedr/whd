# -*- coding: utf-8 -*-
"""W-03 evidence-only resource snapshot. Not a prepare/Frame/token implementation.

Uses content bytes (not mtimes, paths alone or version strings) to detect
changes to an explicitly selected WHD Registry/baseline snapshot. Callers must
obtain baseline paths and resolved Factory Policy from manufacturing_api.
This module cannot authorize machining or issue target frames/tokens.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_SNAPSHOT_REVISION = "WHD_PREPARE_RESOURCE_EVIDENCE_V1"


class PrepareEvidenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _pure_json(value: Any, *, path: str = "value") -> Any:
    """Reject impossible/nonfinite or ambiguous inputs, even with valid JSON shape."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", f"{path} is nonfinite")
        return value
    if isinstance(value, (list, tuple)):
        return [_pure_json(v, path=f"{path}[]") for v in value]
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", f"{path} has nonstring keys")
        return {k: _pure_json(v, path=f"{path}.{k}") for k, v in value.items()}
    raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", f"{path} is not a JSON value")


def _snapshot_bytes(path: Path) -> tuple[str, int]:
    if not path.is_file() or path.is_symlink():
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "resource is not a regular file")
    first = path.stat()
    if not stat.S_ISREG(first.st_mode) or first.st_size == 0:
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "resource must be a nonempty regular file")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (first.st_dev, first.st_ino):
                raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "resource changed before read")
            size = 0
            while block := stream.read(1024 * 1024):
                size += len(block)
                digest.update(block)
            last_open = os.fstat(stream.fileno())
        last_path = path.stat()
    except OSError as exc:
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "resource cannot be read") from exc
    if (first.st_size != size or size == 0 or
        (first.st_dev, first.st_ino, first.st_mtime_ns, first.st_size) !=
        (last_path.st_dev, last_path.st_ino, last_path.st_mtime_ns, last_path.st_size) or
        (opened.st_size, opened.st_mtime_ns) != (last_open.st_size, last_open.st_mtime_ns)):
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "resource changed during read")
    return digest.hexdigest(), size


def _resource_entry(root: Path, relative: str) -> dict[str, Any]:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "expected repository-relative path")
    if "\\" in relative or ":" in relative or path.as_posix() != relative:
        raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "resource path is not portable relative POSIX")
    cursor = root
    for component in path.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "resource path contains a symlink")
    resolved = cursor.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "resource escapes trusted root")
    sha, size = _snapshot_bytes(cursor)
    return {"path":relative,"sha256":sha,"size":size}


def _strict_hash(value: str, *, name: str, commit: bool = False) -> None:
    matcher = _HEX40 if commit else _HEX64
    if not isinstance(value, str) or not matcher.fullmatch(value):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", f"invalid {name}")


def evidence_digest(payload: Mapping[str, Any]) -> str:
    """Deterministic internal evidence digest; NOT RFC 8785 request_digest."""
    normalized = _pure_json(payload)
    data = json.dumps(normalized, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build_resource_evidence(
    *, resource_root: Path, registry_path: str, baseline_paths: Sequence[str],
    resolved_policy: Mapping[str, Any], locked_inputs: Mapping[str, Any],
    engine_commit: str, engine_sha256: str, build_id: str,
    coordinate_contract_revision: str = "1",
) -> dict[str, Any]:
    """Construct attested *inputs* for a future W-03 prepare transaction.

    Only existing, nonempty, readable files and explicit, caller-resolved
    factory policy are accepted. The call does not guess a baseline path,
    set a manufacturing capability or issue any token/Frame.
    """
    _strict_hash(engine_commit, name="engine commit", commit=True)
    _strict_hash(engine_sha256, name="engine source digest")
    if not isinstance(build_id, str) or not build_id.strip() or len(build_id) > 256:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "missing build identity")
    if coordinate_contract_revision != "1":
        raise PrepareEvidenceError("WHD_PROTOCOL_INCOMPATIBLE", "unsupported frame contract")
    if not isinstance(resource_root, Path) or resource_root.is_symlink() or not resource_root.is_dir():
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "trusted WHD resource root is unavailable")
    root = resource_root.resolve(strict=True)
    if not isinstance(registry_path, str) or not registry_path:
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "Registry not specified")
    if not isinstance(baseline_paths, (list, tuple)) or not baseline_paths:
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "verified baseline selection missing")
    if not isinstance(resolved_policy, Mapping) or not resolved_policy:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "WHD resolved policy required")
    if not isinstance(locked_inputs, Mapping) or not locked_inputs:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "locked physical inputs required")
    if len(set(baseline_paths)) != len(baseline_paths) or registry_path in baseline_paths:
        raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "duplicate resource identity")
    registry = _resource_entry(root, registry_path)
    baselines = [_resource_entry(root, p) for p in sorted(baseline_paths)]
    payload = {
        "revision": _SNAPSHOT_REVISION,
        "engine_commit": engine_commit,
        "engine_sha256": engine_sha256,
        "build_id": build_id,
        "coordinate_contract_revision": coordinate_contract_revision,
        "registry": registry,
        "baselines": baselines,
        "policy": _pure_json(resolved_policy, path="resolved_policy"),
        "locked_inputs": _pure_json(locked_inputs, path="locked_inputs"),
    }
    return {"snapshot":payload, "environment_fingerprint":evidence_digest(payload)}


def assert_snapshot_current(expected: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    """Fail before any export if the exact attested environment has changed."""
    for evidence in (expected, current):
        if not isinstance(evidence, Mapping) or not isinstance(evidence.get("snapshot"), Mapping):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "missing trusted prepare snapshot")
        value = evidence.get("environment_fingerprint")
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "invalid prepared environment digest")
        if not hmac.compare_digest(value, evidence_digest(evidence["snapshot"])):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepared evidence was modified")
    if not hmac.compare_digest(expected["environment_fingerprint"], current["environment_fingerprint"]):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "Registry, baseline, policy, build or dimensions changed")
