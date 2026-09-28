"""Canonical user-visible startup provenance/intent contract for WHD execution entries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping


DEFAULT_REPOSITORY = "looaeedr/whd"
SCHEMA = "WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1"
EVIDENCE_SCHEMA = "WHD_EXECUTION_ENTRY_EVIDENCE_V1"
EVIDENCE_MAX_AGE_SECONDS = 300
_FUTURE_SKEW_SECONDS = 30


def build_startup_declaration(*, purpose: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """Render the mandatory declaration that must precede substantive execution."""
    purpose = str(purpose).strip()
    repository = str(repository).strip()
    if not purpose:
        raise ValueError("purpose must be nonblank")
    if not repository:
        raise ValueError("repository must be nonblank")
    return "\n".join(
        (
            SCHEMA,
            f"授權：此工作由使用者明確授權，針對使用者管理的 {repository} 執行。",
            f"目的：{purpose}",
            "範圍：此聲明只記錄 startup provenance/intent；不新增 repository authority，"
            "不取代 claim / Guard / Preflight，也不擴張工具權限或未被使用者要求的工作。",
        )
    )


def prepend_startup_declaration(*, body: str, purpose: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """Prefix a nonblank execution body with the canonical startup declaration."""
    body = str(body).lstrip()
    if not body:
        raise ValueError("body must be nonblank")
    return f"{build_startup_declaration(purpose=purpose, repository=repository)}\n\n{body}"


def _timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid startup evidence {label}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"startup evidence {label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_startup_evidence(
    *,
    purpose: str,
    invocation_identity: str,
    repository: str = DEFAULT_REPOSITORY,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    """Build fresh machine evidence bound to one runtime invocation.

    This evidence does not prove that the host rendered the declaration visibly;
    it makes mutation ingress fail closed unless the current invocation carries
    the canonical declaration and a fresh timestamp.
    """
    invocation_identity = str(invocation_identity).strip()
    if not invocation_identity:
        raise ValueError("invocation_identity must be nonblank")
    now = issued_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("issued_at must be timezone-aware")
    now = now.astimezone(timezone.utc)
    purpose = str(purpose).strip()
    repository = str(repository).strip()
    declaration = build_startup_declaration(purpose=purpose, repository=repository)
    return {
        "schema": EVIDENCE_SCHEMA,
        "repository": repository,
        "invocation_identity": invocation_identity,
        "purpose": purpose,
        "issued_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=EVIDENCE_MAX_AGE_SECONDS)),
        "declaration": declaration,
    }


def validate_startup_evidence(
    evidence: Mapping[str, object] | object,
    *,
    invocation_identity: str,
    repository: str = DEFAULT_REPOSITORY,
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate canonical per-invocation startup evidence for mutation ingress."""
    if not isinstance(evidence, Mapping):
        raise ValueError("startup evidence is required")
    required = {
        "schema",
        "repository",
        "invocation_identity",
        "purpose",
        "issued_at",
        "expires_at",
        "declaration",
    }
    missing = sorted(required - set(evidence))
    if missing:
        raise ValueError(f"startup evidence missing fields: {missing}")
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError("unexpected startup evidence schema")

    observed_repo = str(evidence.get("repository") or "").strip()
    expected_repo = str(repository).strip()
    if observed_repo != expected_repo:
        raise ValueError("startup evidence repository mismatch")

    observed_invocation = str(evidence.get("invocation_identity") or "").strip()
    expected_invocation = str(invocation_identity).strip()
    if not expected_invocation or observed_invocation != expected_invocation:
        raise ValueError("startup evidence invocation mismatch")

    purpose = str(evidence.get("purpose") or "").strip()
    if not purpose:
        raise ValueError("startup evidence purpose must be nonblank")
    expected_declaration = build_startup_declaration(
        purpose=purpose,
        repository=expected_repo,
    )
    if str(evidence.get("declaration") or "") != expected_declaration:
        raise ValueError("startup evidence declaration mismatch")

    issued_at = _timestamp(evidence.get("issued_at"), "issued_at")
    expires_at = _timestamp(evidence.get("expires_at"), "expires_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("startup evidence validation clock must be timezone-aware")
    current = current.astimezone(timezone.utc)

    if issued_at > current + timedelta(seconds=_FUTURE_SKEW_SECONDS):
        raise ValueError("startup evidence issued_at is in the future")
    if expires_at <= issued_at:
        raise ValueError("startup evidence expiry is invalid")
    if (expires_at - issued_at).total_seconds() > EVIDENCE_MAX_AGE_SECONDS:
        raise ValueError("startup evidence TTL exceeds canonical maximum")
    if current > expires_at:
        raise ValueError("startup evidence expired")

    return {str(k): v for k, v in evidence.items()}
