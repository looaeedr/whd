"""WHD Flow v2 trusted atomic control-transaction transport contract.

The transport carries one exact :class:`ControlTransactionPlan` to a trusted
executor and returns only a terminal receipt.  A request is not mutation
authority by itself, and this module deliberately has no ``GREEN``, ``PENDING``
or ``AUTHORIZED`` receipt state.  ``APPLIED`` is valid only after the effect has
been observed and the post-effect ExecutionRecord is already reconciled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from tools.control_transaction import ControlTransactionPlan, TRANSACTION_KINDS
from tools.execution_record import ExecutionRecord, execution_record_fingerprint

REQUEST_SCHEMA = "WHD_CONTROL_TRANSACTION_REQUEST_V2"
RECEIPT_SCHEMA = "WHD_CONTROL_TRANSACTION_TERMINAL_RECEIPT_V2"
TERMINAL_RESULTS = frozenset({"APPLIED", "CONFLICT", "FAILED"})
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class TransportError(RuntimeError):
    """Raised when transaction transport identity is malformed or stale."""


def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip()
    if not text:
        if optional:
            return None
        raise TransportError(f"{name} must be nonblank")
    return text


def _sha(value: object, name: str) -> str:
    text = _text(value, name)
    assert text is not None
    if not _SHA_RE.fullmatch(text):
        raise TransportError(f"{name} must be a 40-character git SHA")
    return text.lower()


def _digest(value: object, name: str) -> str:
    text = _text(value, name)
    assert text is not None
    if not _DIGEST_RE.fullmatch(text):
        raise TransportError(f"{name} must be a 64-character SHA256 digest")
    return text.lower()


def _canonical_digest(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ControlTransactionTransportRequest:
    transaction_id: str
    kind: str
    issue: int
    expected_generation: int
    expected_record_fingerprint: str
    expected_work_branch: str
    expected_head_sha: str
    expected_target_sha: str
    invocation_identity: str | None
    candidate_effect_digest: str


@dataclass(frozen=True)
class ControlTransactionTerminalReceipt:
    request_fingerprint: str
    transaction_id: str
    kind: str
    issue: int
    result: str
    reason: str
    candidate_effect_digest: str
    observed_work_branch: str
    observed_head_sha: str
    observed_target_sha: str
    readback_digest: str
    pre_generation: int
    pre_record_fingerprint: str
    post_generation: int | None = None
    post_record_fingerprint: str | None = None


def build_transport_request(
    plan: ControlTransactionPlan,
    *,
    candidate_effect_digest: str,
) -> ControlTransactionTransportRequest:
    if not isinstance(plan, ControlTransactionPlan):
        raise TransportError("plan must be a ControlTransactionPlan")
    if plan.kind not in TRANSACTION_KINDS:
        raise TransportError(f"unsupported transaction kind {plan.kind!r}")
    if isinstance(plan.issue, bool) or not isinstance(plan.issue, int) or plan.issue <= 0:
        raise TransportError("issue must be a positive integer")
    if isinstance(plan.expected_generation, bool) or not isinstance(plan.expected_generation, int) or plan.expected_generation <= 0:
        raise TransportError("expected_generation must be a positive integer")
    return ControlTransactionTransportRequest(
        transaction_id=_text(plan.transaction_id, "transaction_id"),
        kind=_text(plan.kind, "kind"),
        issue=plan.issue,
        expected_generation=plan.expected_generation,
        expected_record_fingerprint=_digest(
            plan.expected_fingerprint, "expected_record_fingerprint"
        ),
        expected_work_branch=_text(plan.expected_work_branch, "expected_work_branch"),
        expected_head_sha=_sha(plan.expected_head_sha, "expected_head_sha"),
        expected_target_sha=_sha(plan.expected_target_sha, "expected_target_sha"),
        invocation_identity=_text(
            plan.invocation_identity, "invocation_identity", optional=True
        ),
        candidate_effect_digest=_digest(
            candidate_effect_digest, "candidate_effect_digest"
        ),
    )


def transport_request_to_payload(
    request: ControlTransactionTransportRequest,
) -> dict[str, object]:
    if not isinstance(request, ControlTransactionTransportRequest):
        raise TransportError("request must be a ControlTransactionTransportRequest")
    return {"schema": REQUEST_SCHEMA, "version": 2, **asdict(request)}


def transport_request_fingerprint(request: ControlTransactionTransportRequest) -> str:
    return _canonical_digest(transport_request_to_payload(request))


def transport_request_from_payload(payload: object) -> ControlTransactionTransportRequest:
    if not isinstance(payload, dict):
        raise TransportError("request payload must be an object")
    if payload.get("schema") != REQUEST_SCHEMA:
        raise TransportError(f"request schema must be {REQUEST_SCHEMA}")
    if payload.get("version") != 2:
        raise TransportError("request version must be 2")
    issue = payload.get("issue")
    generation = payload.get("expected_generation")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise TransportError("issue must be a positive integer")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
        raise TransportError("expected_generation must be a positive integer")
    kind = _text(payload.get("kind"), "kind")
    if kind not in TRANSACTION_KINDS:
        raise TransportError(f"unsupported transaction kind {kind!r}")
    return ControlTransactionTransportRequest(
        transaction_id=_text(payload.get("transaction_id"), "transaction_id"),
        kind=kind,
        issue=issue,
        expected_generation=generation,
        expected_record_fingerprint=_digest(
            payload.get("expected_record_fingerprint"), "expected_record_fingerprint"
        ),
        expected_work_branch=_text(
            payload.get("expected_work_branch"), "expected_work_branch"
        ),
        expected_head_sha=_sha(payload.get("expected_head_sha"), "expected_head_sha"),
        expected_target_sha=_sha(
            payload.get("expected_target_sha"), "expected_target_sha"
        ),
        invocation_identity=_text(
            payload.get("invocation_identity"), "invocation_identity", optional=True
        ),
        candidate_effect_digest=_digest(
            payload.get("candidate_effect_digest"), "candidate_effect_digest"
        ),
    )


def validate_transport_request(
    request: ControlTransactionTransportRequest,
    record: ExecutionRecord,
) -> bool:
    if not isinstance(request, ControlTransactionTransportRequest):
        raise TransportError("request must be a ControlTransactionTransportRequest")
    if not isinstance(record, ExecutionRecord):
        raise TransportError("record must be an ExecutionRecord")
    if record.issue != request.issue:
        raise TransportError(
            f"issue drift: expected {request.issue}, observed {record.issue}"
        )
    if record.generation != request.expected_generation:
        raise TransportError(
            "generation drift: "
            f"expected {request.expected_generation}, observed {record.generation}"
        )
    fingerprint = execution_record_fingerprint(record)
    if fingerprint != request.expected_record_fingerprint:
        raise TransportError(
            "record fingerprint drift: "
            f"expected {request.expected_record_fingerprint}, observed {fingerprint}"
        )
    if record.work_branch != request.expected_work_branch:
        raise TransportError(
            "work branch drift: "
            f"expected {request.expected_work_branch}, observed {record.work_branch}"
        )
    if record.head_sha != request.expected_head_sha:
        raise TransportError(
            f"head drift: expected {request.expected_head_sha}, observed {record.head_sha}"
        )
    if record.target_sha != request.expected_target_sha:
        raise TransportError(
            "target drift: "
            f"expected {request.expected_target_sha}, observed {record.target_sha}"
        )
    return True


def build_terminal_receipt(
    *,
    request: ControlTransactionTransportRequest,
    result: str,
    reason: str,
    observed_work_branch: str,
    observed_head_sha: str,
    observed_target_sha: str,
    readback_digest: str,
    post_record: ExecutionRecord | None = None,
) -> ControlTransactionTerminalReceipt:
    if not isinstance(request, ControlTransactionTransportRequest):
        raise TransportError("request must be a ControlTransactionTransportRequest")
    terminal_result = _text(result, "terminal result")
    assert terminal_result is not None
    if terminal_result not in TERMINAL_RESULTS:
        raise TransportError(
            f"terminal result must be one of {sorted(TERMINAL_RESULTS)}"
        )

    post_generation: int | None = None
    post_fingerprint: str | None = None
    if terminal_result == "APPLIED":
        if not isinstance(post_record, ExecutionRecord):
            raise TransportError("APPLIED receipt requires reconciled post_record")
        tx = post_record.transaction
        if (
            tx is None
            or tx.id != request.transaction_id
            or tx.kind != request.kind
            or tx.status != "RECONCILED"
            or tx.expected_fingerprint != request.expected_record_fingerprint
        ):
            raise TransportError(
                "post_record transaction must be exact and RECONCILED"
            )
        if post_record.issue != request.issue:
            raise TransportError("post_record issue does not match request")
        if post_record.generation != request.expected_generation + 1:
            raise TransportError(
                "post_record generation must advance exactly once"
            )
        post_generation = post_record.generation
        post_fingerprint = execution_record_fingerprint(post_record)
    elif post_record is not None:
        raise TransportError(
            f"{terminal_result} receipt cannot carry post_record authority"
        )

    receipt = ControlTransactionTerminalReceipt(
        request_fingerprint=transport_request_fingerprint(request),
        transaction_id=request.transaction_id,
        kind=request.kind,
        issue=request.issue,
        result=terminal_result,
        reason=_text(reason, "reason"),
        candidate_effect_digest=request.candidate_effect_digest,
        observed_work_branch=_text(observed_work_branch, "observed_work_branch"),
        observed_head_sha=_sha(observed_head_sha, "observed_head_sha"),
        observed_target_sha=_sha(observed_target_sha, "observed_target_sha"),
        readback_digest=_digest(readback_digest, "readback_digest"),
        pre_generation=request.expected_generation,
        pre_record_fingerprint=request.expected_record_fingerprint,
        post_generation=post_generation,
        post_record_fingerprint=post_fingerprint,
    )
    # The builder validates its own output to keep construction and verification
    # on exactly the same fail-closed path.
    validate_terminal_receipt(receipt, request, post_record=post_record)
    return receipt


def terminal_receipt_to_payload(
    receipt: ControlTransactionTerminalReceipt,
) -> dict[str, object]:
    if not isinstance(receipt, ControlTransactionTerminalReceipt):
        raise TransportError("receipt must be a ControlTransactionTerminalReceipt")
    return {"schema": RECEIPT_SCHEMA, "version": 2, **asdict(receipt)}


def validate_terminal_receipt(
    receipt: ControlTransactionTerminalReceipt,
    request: ControlTransactionTransportRequest,
    *,
    post_record: ExecutionRecord | None = None,
) -> bool:
    if not isinstance(receipt, ControlTransactionTerminalReceipt):
        raise TransportError("receipt must be a ControlTransactionTerminalReceipt")
    if not isinstance(request, ControlTransactionTransportRequest):
        raise TransportError("request must be a ControlTransactionTransportRequest")
    expected_request_fp = transport_request_fingerprint(request)
    if receipt.request_fingerprint != expected_request_fp:
        raise TransportError(
            "request fingerprint mismatch: receipt cannot be rebound"
        )
    if (
        receipt.transaction_id != request.transaction_id
        or receipt.kind != request.kind
        or receipt.issue != request.issue
    ):
        raise TransportError("receipt transaction identity does not match request")
    if receipt.result not in TERMINAL_RESULTS:
        raise TransportError("receipt result is not terminal")
    if receipt.candidate_effect_digest != request.candidate_effect_digest:
        raise TransportError("receipt candidate effect digest does not match request")
    if receipt.pre_generation != request.expected_generation:
        raise TransportError("receipt pre_generation does not match request")
    if receipt.pre_record_fingerprint != request.expected_record_fingerprint:
        raise TransportError("receipt pre-record fingerprint does not match request")

    if receipt.result == "APPLIED":
        if not isinstance(post_record, ExecutionRecord):
            raise TransportError("APPLIED receipt validation requires post_record")
        tx = post_record.transaction
        if (
            tx is None
            or tx.id != request.transaction_id
            or tx.kind != request.kind
            or tx.status != "RECONCILED"
            or tx.expected_fingerprint != request.expected_record_fingerprint
        ):
            raise TransportError(
                "post_record transaction must be exact and RECONCILED"
            )
        if receipt.post_generation != post_record.generation:
            raise TransportError("receipt post_generation does not match post_record")
        if receipt.post_generation != request.expected_generation + 1:
            raise TransportError("receipt post_generation must advance exactly once")
        post_fp = execution_record_fingerprint(post_record)
        if receipt.post_record_fingerprint != post_fp:
            raise TransportError(
                "receipt post-record fingerprint does not match post_record"
            )
        if receipt.observed_work_branch != post_record.work_branch:
            raise TransportError("receipt work-branch readback does not match post_record")
        if receipt.observed_head_sha != post_record.head_sha:
            raise TransportError("receipt head readback does not match post_record")
        if receipt.observed_target_sha != post_record.target_sha:
            raise TransportError("receipt target readback does not match post_record")
    else:
        if receipt.post_generation is not None or receipt.post_record_fingerprint is not None:
            raise TransportError(
                f"{receipt.result} receipt cannot carry post-record authority"
            )
        if post_record is not None:
            raise TransportError(
                f"{receipt.result} receipt validation cannot accept post_record"
            )
    return True
