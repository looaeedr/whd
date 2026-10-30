# -*- coding: utf-8 -*-
"""W-05 private Windows onedir engine identity, never public manufacturing authority.

The bundle's manifest is generated *after* PyInstaller from exact checked-out
source. Every capabilities call rechecks the actual EXE, registry, baseline
DXF inventory and bundled policy bytes. This is integrity/provenance
consistency, not code-signing: consumers must also trust the CI artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_EXE_NAME = "WHD-Engine.exe"
_MANIFEST_NAME = "WHD_ENGINE_BUILD.json"
_REGISTRY = Path("基準檔/截角資料庫/certified_relief_rules.json")
_POLICY = Path("config.ini")
_MAX_FILE = 100 * 1024 * 1024


class PackageIdentityError(ValueError):
    pass


def _regular_bytes(path: Path, root: Path) -> bytes:
    try:
        resolved_root = root.resolve(strict=True)
        real = path.resolve(strict=True)
        if real != resolved_root and resolved_root not in real.parents:
            raise PackageIdentityError("WHD_PACKAGE_PATH_ESCAPE")
        if not path.is_file() or path.is_symlink() or real != path.absolute():
            raise PackageIdentityError("WHD_PACKAGE_FILE_UNTRUSTED")
        if path.stat().st_size < 1 or path.stat().st_size > _MAX_FILE:
            raise PackageIdentityError("WHD_PACKAGE_FILE_SIZE_INVALID")
        return path.read_bytes()
    except OSError as exc:
        raise PackageIdentityError("WHD_PACKAGE_RESOURCE_UNREADABLE") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _baseline_digest(root: Path) -> str:
    baseline = root / "基準檔"
    if baseline.is_symlink() or not baseline.is_dir():
        raise PackageIdentityError("WHD_PACKAGE_BASELINE_MISSING")
    paths = sorted(baseline.rglob("*.dxf"), key=lambda p: p.relative_to(root).as_posix())
    if not paths or len(paths) > 10000:
        raise PackageIdentityError("WHD_PACKAGE_BASELINE_INVENTORY_INVALID")
    h = hashlib.sha256()
    for path in paths:
        data = _regular_bytes(path, root)
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def _package_facts(root: Path) -> dict[str, str]:
    return {
        "engine_sha256": _sha(_regular_bytes(root / _EXE_NAME, root)),
        "registry_sha256": _sha(_regular_bytes(root / _REGISTRY, root)),
        "baseline_manifest_sha256": _baseline_digest(root),
        "policy_sha256": _sha(_regular_bytes(root / _POLICY, root)),
    }


def _revision(facts: dict[str, str]) -> str:
    return _sha(json.dumps(
        [facts["registry_sha256"], facts["baseline_manifest_sha256"], facts["policy_sha256"]],
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8"))


def write_manifest(root: Path, commit: str) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not _SHA40.fullmatch(commit):
        raise PackageIdentityError("WHD_PACKAGE_COMMIT_INVALID")
    output = root / _MANIFEST_NAME
    if output.exists() or output.is_symlink():
        raise PackageIdentityError("WHD_PACKAGE_MANIFEST_ALREADY_EXISTS")
    facts = _package_facts(root)
    manifest: dict[str, Any] = {
        "schema": "whd-engine-private-build-v1",
        "engine_commit": commit,
        "build_id": f"w05-private-{commit[:12]}-{facts['engine_sha256'][:16]}",
        "resource_revision": _revision(facts),
        **facts,
    }
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    data = _regular_bytes(root / _MANIFEST_NAME, root)
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PackageIdentityError("WHD_PACKAGE_MANIFEST_INVALID") from exc
    if not isinstance(manifest, dict):
        raise PackageIdentityError("WHD_PACKAGE_MANIFEST_INVALID")
    expected = {
        "schema", "engine_commit", "build_id", "resource_revision",
        "engine_sha256", "registry_sha256", "baseline_manifest_sha256", "policy_sha256",
    }
    if set(manifest) != expected or manifest["schema"] != "whd-engine-private-build-v1":
        raise PackageIdentityError("WHD_PACKAGE_MANIFEST_INVALID")
    commit = manifest.get("engine_commit")
    if not isinstance(commit, str) or not _SHA40.fullmatch(commit):
        raise PackageIdentityError("WHD_PACKAGE_MANIFEST_INVALID")
    facts = _package_facts(root)
    expected_build = f"w05-private-{commit[:12]}-{facts['engine_sha256'][:16]}"
    if (
        manifest.get("build_id") != expected_build
        or manifest.get("resource_revision") != _revision(facts)
        or any(manifest.get(key) != value for key, value in facts.items())
    ):
        raise PackageIdentityError("WHD_PACKAGE_HASH_MISMATCH")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    result = write_manifest(args.root, args.sha)
    verify_manifest(args.root)
    print(f"WHD_ENGINE_PRIVATE_PACKAGE_VALIDATED {result['build_id']}")


if __name__ == "__main__":
    main()
