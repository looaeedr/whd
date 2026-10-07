"""Machine gate for physical host-return enforcement and dispatch completion claims.

Repository Flow v2 can classify whether a return is legal, but it cannot assume
that every host/UI surface actually routes its final/return seam through that
classifier.  This module makes that distinction explicit and fail-closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tools.execution_invocation_exit import (
    SUBSTANTIVE_TRANSACTION_KINDS,
)
from tools.execution_record import ExecutionRecord


HOST_RETURN_SEAM_ATTESTATION_SCHEMA = "WHD_HOST_RETURN_SEAM_ENFORCEMENT_V1"
HOST_RETURN_HARD_ENFORCED = "HARD_ENFORCED"
HOST_RETURN_SEAM_UNENFORCED = "HOST_RETURN_SEAM_UNENFORCED"

# RECONCILE is intentionally not enough for a user-visible "/派工完成" claim:
# it is control-plane repair. HANDOFF/BLOCK/YIELD are legal invocation handoff
# outcomes; DONE is handled separately.
DISPATCH_FIRST_SUBSTANTIVE_KINDS = frozenset(
    kind
    for kind in SUBSTANTIVE_TRANSACTION_KINDS
    if kind not in {"RECONCILE", "HANDOFF", "BLOCK"}
)


class HostReturnSurfaceGateError(ValueError):
    """Raised when a host surface or dispatch completion claim is unproven."""


@dataclass(frozen=True)
class DispatchCompletionDecision:
    status: str
    may_claim_complete: bool
    reason: str
    issue: int
    generation: int
    transaction_kind: str | None
    next_action_kind: str | None


def _text(value: object, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise HostReturnSurfaceGateError(f"{field} must be nonblank")
    return result


def validate_host_return_seam_attestation(
    attestation: object,
    *,
    surface_id: str,
) -> dict[str, object]:
    """Require proof that the physical host final/return seam is verifier-bound."""

    if not isinstance(attestation, Mapping):
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: missing host return seam attestation"
        )
    item = {str(key): value for key, value in attestation.items()}
    if item.get("schema") != HOST_RETURN_SEAM_ATTESTATION_SCHEMA:
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: attestation schema mismatch"
        )
    if _text(item.get("surface_id"), "surface_id") != _text(surface_id, "surface_id"):
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: surface identity mismatch"
        )
    if item.get("return_hook_enforced") is not True:
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: physical return hook is not enforced"
        )
    if item.get("plain_final_bypass_blocked") is not True:
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: plain final-response bypass remains possible"
        )
    if item.get("exit_verifier") != "tools.execution_invocation_exit.validate_host_exit_proof":
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: exit verifier mismatch"
        )
    if item.get("report_formatter") != "tools.runtime_report_identity.format_runtime_report_prefix":
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: runtime report formatter mismatch"
        )
    if item.get("trusted_source") != "host_runtime":
        raise HostReturnSurfaceGateError(
            "HOST_RETURN_SEAM_UNENFORCED: attestation is not host-runtime evidence"
        )
    return item


def classify_host_surface_enforcement(
    attestation: object,
    *,
    surface_id: str,
) -> str:
    try:
        validate_host_return_seam_attestation(
            attestation,
            surface_id=surface_id,
        )
    except HostReturnSurfaceGateError:
        return HOST_RETURN_SEAM_UNENFORCED
    return HOST_RETURN_HARD_ENFORCED


def classify_dispatch_completion(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
) -> DispatchCompletionDecision:
    """Classify whether /派工 has progressed beyond READY/ACQUIRE-only plumbing."""

    if not isinstance(record, ExecutionRecord):
        raise HostReturnSurfaceGateError("record must be an ExecutionRecord")
    invocation = _text(invocation_identity, "invocation_identity")
    tx = record.transaction
    tx_kind = tx.kind if tx is not None else None
    next_kind = record.next_action.kind if record.next_action is not None else None

    if record.state == "DONE":
        return DispatchCompletionDecision(
            status="DISPATCH_COMPLETE_TERMINAL",
            may_claim_complete=True,
            reason="native record is DONE",
            issue=record.issue,
            generation=record.generation,
            transaction_kind=tx_kind,
            next_action_kind=next_kind,
        )

    if (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.invocation_identity == invocation
        and tx.kind == "YIELD"
        and record.lease is None
    ):
        return DispatchCompletionDecision(
            status="DISPATCH_COMPLETE_YIELDED",
            may_claim_complete=True,
            reason="invocation durably yielded after work",
            issue=record.issue,
            generation=record.generation,
            transaction_kind=tx_kind,
            next_action_kind=next_kind,
        )

    if (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.invocation_identity == invocation
        and tx.kind == "BLOCK"
        and record.state == "BLOCKED"
    ):
        return DispatchCompletionDecision(
            status="DISPATCH_COMPLETE_BLOCKED_HANDOFF",
            may_claim_complete=True,
            reason="genuine blocker was durably recorded",
            issue=record.issue,
            generation=record.generation,
            transaction_kind=tx_kind,
            next_action_kind=next_kind,
        )

    if (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.invocation_identity == invocation
        and tx.kind == "HANDOFF"
    ):
        return DispatchCompletionDecision(
            status="DISPATCH_COMPLETE_HANDOFF",
            may_claim_complete=True,
            reason="ownership was durably handed off",
            issue=record.issue,
            generation=record.generation,
            transaction_kind=tx_kind,
            next_action_kind=next_kind,
        )

    if (
        tx is not None
        and tx.status == "RECONCILED"
        and tx.invocation_identity == invocation
        and tx.kind in DISPATCH_FIRST_SUBSTANTIVE_KINDS
    ):
        return DispatchCompletionDecision(
            status="DISPATCH_SUBSTANTIVE_PROGRESS",
            may_claim_complete=True,
            reason="same invocation completed a substantive transaction",
            issue=record.issue,
            generation=record.generation,
            transaction_kind=tx_kind,
            next_action_kind=next_kind,
        )

    return DispatchCompletionDecision(
        status="DISPATCH_INCOMPLETE",
        may_claim_complete=False,
        reason=(
            "READY/ACQUIRE/control-plane-only progress is not dispatch completion; "
            "consume the exact next_action"
        ),
        issue=record.issue,
        generation=record.generation,
        transaction_kind=tx_kind,
        next_action_kind=next_kind,
    )


def assert_dispatch_completion(
    record: ExecutionRecord,
    *,
    invocation_identity: str,
) -> DispatchCompletionDecision:
    decision = classify_dispatch_completion(
        record,
        invocation_identity=invocation_identity,
    )
    if not decision.may_claim_complete:
        raise HostReturnSurfaceGateError(
            "DISPATCH_INCOMPLETE "
            f"issue={decision.issue} generation={decision.generation} "
            f"transaction={decision.transaction_kind or 'NONE'} "
            f"next_action={decision.next_action_kind or 'NONE'}"
        )
    return decision
