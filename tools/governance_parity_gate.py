from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


SCHEMA = "WHD_GOVERNANCE_PARITY_V1"
REQUIRED_DOMAINS = {
    "continuity",
    "turn_exit",
    "scheduler_liveness",
    "remote_guard",
    "current_skills",
}
VALID_STATUS = {"EXACT", "COMPATIBLE_EQUIVALENT", "UNKNOWN_DIVERGENCE"}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _fail(reason: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"result": "FAIL", "reason": reason}
    out.update(extra)
    return out


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value))


def _iter_artifacts(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return ()
    return tuple(a for a in artifacts if isinstance(a, Mapping))


def evaluate_manifest(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _fail("INVALID_SCHEMA")

    production = payload.get("production")
    trusted = payload.get("trusted")
    if not isinstance(production, Mapping) or not isinstance(trusted, Mapping):
        return _fail("INVALID_IDENTITY")
    if not _valid_sha(production.get("head_sha")) or not _valid_sha(trusted.get("head_sha")):
        return _fail("INVALID_IDENTITY")
    if not isinstance(production.get("ref"), str) or not production.get("ref"):
        return _fail("INVALID_IDENTITY")
    if not isinstance(trusted.get("ref"), str) or not trusted.get("ref"):
        return _fail("INVALID_IDENTITY")

    artifacts = list(_iter_artifacts(payload))
    domains = {a.get("domain") for a in artifacts}
    missing = sorted(REQUIRED_DOMAINS - domains)
    if missing:
        return _fail("REQUIRED_DOMAIN_MISSING", missing_domains=missing)

    for artifact in artifacts:
        domain = artifact.get("domain")
        path = artifact.get("path")
        prod_blob = artifact.get("production_blob_sha")
        trust_blob = artifact.get("trusted_blob_sha")
        status = artifact.get("status")

        if not isinstance(domain, str) or not domain or not isinstance(path, str) or not path:
            return _fail("INVALID_ARTIFACT_IDENTITY")
        if not _valid_sha(prod_blob) or not _valid_sha(trust_blob):
            return _fail("INVALID_IDENTITY", domain=domain, path=path)
        if status not in VALID_STATUS:
            return _fail("UNKNOWN_DIVERGENCE", domain=domain, path=path)

        if status == "EXACT":
            if prod_blob != trust_blob:
                return _fail("UNKNOWN_DIVERGENCE", domain=domain, path=path)
            continue

        if status == "UNKNOWN_DIVERGENCE":
            return _fail("UNKNOWN_DIVERGENCE", domain=domain, path=path)

        reason = artifact.get("compatibility_reason")
        if not isinstance(reason, str) or not reason.strip():
            return _fail("COMPATIBILITY_REASON_REQUIRED", domain=domain, path=path)

    readback = payload.get("deployment_readback")
    if not isinstance(readback, Mapping) or readback.get("durable") is not True:
        return _fail("DURABLE_READBACK_REQUIRED")
    evidence = readback.get("evidence")
    if not isinstance(evidence, list) or not any(isinstance(x, str) and x.strip() for x in evidence):
        return _fail("DURABLE_READBACK_REQUIRED")

    return {
        "result": "GREEN",
        "reason": "PARITY_PROVEN",
        "required_domains": sorted(REQUIRED_DOMAINS),
        "artifact_count": len(artifacts),
    }


MIRROR_SCHEMA = "WHD_GOVERNANCE_MIRROR_V1"
MIRROR_MANIFEST_SCHEMA = "WHD_GOVERNANCE_MIRROR_MANIFEST_V1"
MIRROR_BRANCHES = frozenset({"main", "cleanup/2d-3d-sync"})


def validate_mirror_manifest(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema") != MIRROR_MANIFEST_SCHEMA:
        return _fail("INVALID_MIRROR_MANIFEST_SCHEMA")
    branches = payload.get("branches")
    if not isinstance(branches, list) or set(branches) != MIRROR_BRANCHES or len(branches) != 2:
        return _fail("INVALID_MIRROR_BRANCHES")
    if payload.get("product_authority") != "cleanup/2d-3d-sync":
        return _fail("INVALID_PRODUCT_AUTHORITY")
    if payload.get("governance_mode") != "BIDIRECTIONAL_MIRROR":
        return _fail("INVALID_GOVERNANCE_MODE")
    paths = payload.get("governance_paths")
    prefixes = payload.get("governance_prefixes", [])
    if not isinstance(paths, list) or not paths or any(not isinstance(x, str) or not x.strip() for x in paths):
        return _fail("INVALID_GOVERNANCE_PATHS")
    if not isinstance(prefixes, list) or any(not isinstance(x, str) or not x.strip() for x in prefixes):
        return _fail("INVALID_GOVERNANCE_PREFIXES")
    if len(set(paths)) != len(paths) or len(set(prefixes)) != len(prefixes):
        return _fail("DUPLICATE_GOVERNANCE_SCOPE")
    return {"result": "GREEN", "reason": "MIRROR_MANIFEST_VALID"}


def is_governance_path(path: str, mirror_manifest: Mapping[str, Any]) -> bool:
    if validate_mirror_manifest(mirror_manifest)["result"] != "GREEN":
        return False
    normalized = str(path or "").strip().replace("\\", "/")
    exact = {str(x).strip() for x in mirror_manifest.get("governance_paths", [])}
    prefixes = tuple(str(x).strip().rstrip("/") + "/" for x in mirror_manifest.get("governance_prefixes", []))
    return normalized in exact or any(normalized.startswith(prefix) for prefix in prefixes)


def evaluate_change_scope(
    changed_paths: Iterable[str],
    mirror_manifest: Mapping[str, Any],
    *,
    target_ref: str,
) -> Dict[str, Any]:
    manifest_result = validate_mirror_manifest(mirror_manifest)
    if manifest_result["result"] != "GREEN":
        return manifest_result
    if target_ref not in MIRROR_BRANCHES:
        return _fail("INVALID_MIRROR_TARGET", target_ref=target_ref)
    normalized = tuple(dict.fromkeys(str(x).strip().replace("\\", "/") for x in changed_paths if str(x).strip()))
    governance = tuple(path for path in normalized if is_governance_path(path, mirror_manifest))
    non_governance = tuple(path for path in normalized if path not in governance)
    if target_ref == "main" and non_governance:
        return _fail(
            "NON_GOVERNANCE_PATH_TO_MAIN",
            path=non_governance[0],
            non_governance_paths=list(non_governance),
        )
    return {
        "result": "GREEN",
        "reason": "GOVERNANCE_CHANGE_SCOPE_VALID",
        "target_ref": target_ref,
        "governance_paths": list(governance),
        "non_governance_paths": list(non_governance),
    }


def evaluate_mirror_transaction(
    payload: Mapping[str, Any],
    mirror_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    manifest_result = validate_mirror_manifest(mirror_manifest)
    if manifest_result["result"] != "GREEN":
        return manifest_result
    if not isinstance(payload, Mapping) or payload.get("schema") != MIRROR_SCHEMA:
        return _fail("INVALID_MIRROR_SCHEMA")

    source_ref = str(payload.get("source_ref") or "")
    target_ref = str(payload.get("target_ref") or "")
    if source_ref == target_ref or {source_ref, target_ref} != MIRROR_BRANCHES:
        return _fail("INVALID_MIRROR_DIRECTION", source_ref=source_ref, target_ref=target_ref)

    raw_paths = payload.get("changed_paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        return _fail("GOVERNANCE_MIRROR_PATHS_REQUIRED")
    changed_paths = tuple(dict.fromkeys(str(x).strip().replace("\\", "/") for x in raw_paths))
    if any(not path for path in changed_paths):
        return _fail("INVALID_GOVERNANCE_PATH_IDENTITY")

    for path in changed_paths:
        if not is_governance_path(path, mirror_manifest):
            reason = "NON_GOVERNANCE_PATH_TO_MAIN" if target_ref == "main" else "NON_GOVERNANCE_MIRROR_PATH"
            return _fail(reason, path=path)

    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return _fail("INVALID_ARTIFACT_IDENTITY")
    artifacts = [item for item in raw_artifacts if isinstance(item, Mapping)]
    if len(artifacts) != len(raw_artifacts):
        return _fail("INVALID_ARTIFACT_IDENTITY")
    artifact_paths = [str(item.get("path") or "") for item in artifacts]
    if len(set(artifact_paths)) != len(artifact_paths) or set(artifact_paths) != set(changed_paths):
        return _fail("MIRROR_ARTIFACT_SCOPE_MISMATCH")

    for artifact in artifacts:
        path = str(artifact.get("path") or "")
        source_blob = artifact.get("source_blob_sha")
        target_blob = artifact.get("target_blob_sha")
        status = artifact.get("status")
        if not _valid_sha(source_blob) or not _valid_sha(target_blob):
            return _fail("INVALID_IDENTITY", path=path)
        if status not in VALID_STATUS:
            return _fail("UNKNOWN_DIVERGENCE", path=path)
        if status == "UNKNOWN_DIVERGENCE":
            return _fail("UNKNOWN_DIVERGENCE", path=path)
        if status == "EXACT":
            if source_blob != target_blob:
                return _fail("UNKNOWN_DIVERGENCE", path=path)
        else:
            reason = artifact.get("compatibility_reason")
            if not isinstance(reason, str) or not reason.strip():
                return _fail("COMPATIBILITY_REASON_REQUIRED", path=path)

    readback = payload.get("deployment_readback")
    if not isinstance(readback, Mapping) or readback.get("durable") is not True:
        return _fail("DURABLE_READBACK_REQUIRED")
    evidence = readback.get("evidence")
    if not isinstance(evidence, list) or not any(isinstance(x, str) and x.strip() for x in evidence):
        return _fail("DURABLE_READBACK_REQUIRED")

    return {
        "result": "GREEN",
        "reason": "GOVERNANCE_MIRROR_PARITY_PROVEN",
        "source_ref": source_ref,
        "target_ref": target_ref,
        "artifact_count": len(artifacts),
    }


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git command failed: {args!r}")
    return proc.stdout.strip()


def _governed_tree_paths(ref: str, mirror_manifest: Mapping[str, Any]) -> set[str]:
    output = _git("ls-tree", "-r", "--name-only", ref)
    return {
        path
        for path in output.splitlines()
        if path and is_governance_path(path, mirror_manifest)
    }


def _blob_at(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and _valid_sha(value) else None


def build_live_mirror_payload(
    source_ref: str,
    target_ref: str,
    mirror_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    governed = set(str(x) for x in mirror_manifest.get("governance_paths", []))
    governed |= _governed_tree_paths(source_ref, mirror_manifest)
    governed |= _governed_tree_paths(target_ref, mirror_manifest)
    artifacts: list[dict[str, Any]] = []
    for path in sorted(governed):
        source_blob = _blob_at(source_ref, path)
        target_blob = _blob_at(target_ref, path)
        exact = bool(source_blob and target_blob and source_blob == target_blob)
        artifacts.append(
            {
                "path": path,
                "source_blob_sha": source_blob or ("0" * 40),
                "target_blob_sha": target_blob or ("0" * 40),
                "status": "EXACT" if exact else "UNKNOWN_DIVERGENCE",
            }
        )
    return {
        "schema": MIRROR_SCHEMA,
        "source_ref": source_ref.replace("refs/remotes/origin/", ""),
        "target_ref": target_ref.replace("refs/remotes/origin/", ""),
        "changed_paths": sorted(governed),
        "artifacts": artifacts,
        "deployment_readback": {
            "durable": True,
            "evidence": [f"git:{source_ref}", f"git:{target_ref}"],
        },
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WHD governance parity / mirror hard gate")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--target-ref")
    parser.add_argument("--source-ref")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--scope-only", action="store_true")
    parser.add_argument("--verify-live-parity", action="store_true")
    args = parser.parse_args(argv)

    if args.manifest is None:
        parser.error("--manifest is required for governance mirror mode")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    if args.scope_only:
        result = evaluate_change_scope(args.changed_file, manifest, target_ref=str(args.target_ref or ""))
    elif args.verify_live_parity:
        if not args.source_ref or not args.target_ref:
            parser.error("--source-ref and --target-ref are required for live parity")
        payload = build_live_mirror_payload(args.source_ref, args.target_ref, manifest)
        result = evaluate_mirror_transaction(payload, manifest)
    else:
        parser.error("choose --scope-only or --verify-live-parity")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("result") == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
