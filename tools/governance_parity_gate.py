from __future__ import annotations

import re
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
