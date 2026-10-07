"""Explicit-authority ingress for WHD Flow v2 READY execution records.


Open Issues are not work authority.  This module only creates a READY candidate
from a typed dispatch authority supplied by an upstream trusted/user/chain
boundary.  The resulting record is unclaimed; schedulers still need ACQUIRE.
"""


from __future__ import annotations


from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Mapping


from tools.execution_action_contract import ActionContractError, validate_execution_action
from tools.execution_record import (
    ActionSpec,
    ChainState,
    ClosureState,
    ExecutionRecord,
    QAState,
    execution_record_fingerprint,
)


INGRESS_SCHEMA = "WHD_EXECUTION_DISPATCH_INGRESS_V1"
DEFAULT_INTERACTIVE_SLOT_ID = "worker.slot.0"
ALLOWED_EXECUTION_INTENTS = frozenset({"EXECUTE_TICKET", "EXECUTE_CHAIN", "SCHEDULER_LANE"})
AUTHORITY_KINDS = frozenset({"USER_EXPLICIT", "CHAIN_SUCCESSOR", "WORK_SLOT_ASSIGNMENT"})

CANONICAL_DISPATCH_TRANSPORT = "GITHUB_CANONICAL"
LOCAL_MACHINE_DISPATCH_TRANSPORTS = frozenset(
    {
        "REMOTE_DESKTOP_COMMANDER",
        "RC",
        "LOCAL_SHELL",
        "LOCAL_WORKSPACE",
        "LOCAL_REPO",
        "LOCAL_WORKTREE",
        "/WORKSPACE/WHD",
        "WORKSPACE/WHD",
    }
)




class DispatchIngressError(ValueError):
    """Raised when a READY record would be created without exact authority."""



def validate_dispatch_transport(value: object) -> str:
    """Require GitHub canonical transport for /派工 and READY control-plane work."""

    raw = str(value or "").strip()
    normalized = raw.upper().replace("-", "_").replace(" ", "_").rstrip("/")
    if normalized in LOCAL_MACHINE_DISPATCH_TRANSPORTS:
        raise DispatchIngressError(
            "DISPATCH_LOCAL_MACHINE_FORBIDDEN: "
            "/派工 READY ingress cannot use Remote Desktop/local shell/local workspace; "
            "explicit /接手 RC is implementation-only"
        )
    if normalized != CANONICAL_DISPATCH_TRANSPORT:
        raise DispatchIngressError(
            "DISPATCH_LOCAL_MACHINE_PROHIBITION_HARD_GATE_V1 requires "
            f"dispatch_transport={CANONICAL_DISPATCH_TRANSPORT}"
        )
    return CANONICAL_DISPATCH_TRANSPORT




def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    result = str(value or "").strip()
    if not result:
        if optional:
            return None
        raise DispatchIngressError(f"{name} must be nonblank")
    return result




def _issue(value: object, name: str, *, optional: bool = False) -> int | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool):
        raise DispatchIngressError(f"{name} must be a positive issue number")
    try:
        result = int(str(value).lstrip("#"))
    except (TypeError, ValueError) as exc:
        raise DispatchIngressError(f"{name} must be a positive issue number") from exc
    if result <= 0:
        raise DispatchIngressError(f"{name} must be a positive issue number")
    return result




@dataclass(frozen=True)
class DispatchIngressRequest:
    issue: int
    execution_intent: str
    authority_kind: str
    authority_ref: str
    source_branch: str
    source_sha: str
    work_branch: str
    target_branch: str
    target_sha: str
    post_acquire: ActionSpec | None = None
    parent_issue: int | None = None
    slot_id: str | None = None
    created_at: str | None = None
    dispatch_transport: str = CANONICAL_DISPATCH_TRANSPORT




@dataclass(frozen=True)
class DispatchIngressPlan:
    request_fingerprint: str
    authority_fingerprint: str
    record_fingerprint: str
    record: ExecutionRecord




def _request_payload(request: DispatchIngressRequest) -> dict[str, object]:
    return {"schema": INGRESS_SCHEMA, "version": 1, **asdict(request)}




def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()




def plan_dispatch_ingress(request: DispatchIngressRequest) -> DispatchIngressPlan:
    if not isinstance(request, DispatchIngressRequest):
        raise DispatchIngressError("request must be a DispatchIngressRequest")
    issue = _issue(request.issue, "issue")
    assert issue is not None
    dispatch_transport = validate_dispatch_transport(request.dispatch_transport)
    execution_intent = _text(request.execution_intent, "execution_intent")
    if execution_intent not in ALLOWED_EXECUTION_INTENTS:
        raise DispatchIngressError(
            f"execution_intent must be one of {sorted(ALLOWED_EXECUTION_INTENTS)}"
        )
    authority_kind = _text(request.authority_kind, "authority_kind")
    if authority_kind not in AUTHORITY_KINDS:
        raise DispatchIngressError(
            f"authority_kind must be one of {sorted(AUTHORITY_KINDS)}"
        )
    authority_ref = _text(request.authority_ref, "authority_ref")
    parent_issue = _issue(request.parent_issue, "parent_issue", optional=True)
    slot_id = _text(request.slot_id, "slot_id", optional=True)
    post_acquire = request.post_acquire
    if post_acquire is not None:
        if not isinstance(post_acquire, ActionSpec):
            raise DispatchIngressError("post_acquire must be an ActionSpec")
        if execution_intent != "SCHEDULER_LANE":
            raise DispatchIngressError("post_acquire is only supported for SCHEDULER_LANE ingress")
        if post_acquire.kind == "ACQUIRE":
            raise DispatchIngressError("post_acquire cannot recursively ACQUIRE")
        try:
            validate_execution_action(post_acquire)
        except ActionContractError as exc:
            raise DispatchIngressError(f"invalid post_acquire action: {exc}") from exc


    # DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1
    if (
        authority_kind == "USER_EXPLICIT"
        and execution_intent == "EXECUTE_TICKET"
        and slot_id is None
    ):
        slot_id = DEFAULT_INTERACTIVE_SLOT_ID


    if authority_kind == "CHAIN_SUCCESSOR" and parent_issue is None:
        raise DispatchIngressError("CHAIN_SUCCESSOR requires parent_issue")
    if authority_kind == "WORK_SLOT_ASSIGNMENT" and slot_id is None:
        raise DispatchIngressError("WORK_SLOT_ASSIGNMENT requires slot_id")


    request_payload = _request_payload(request)
    request_payload["effective_slot_id"] = slot_id
    request_fp = _digest(request_payload)
    authority_fp = _digest(
        {
            "authority_kind": authority_kind,
            "authority_ref": authority_ref,
            "issue": issue,
            "parent_issue": parent_issue,
            "slot_id": slot_id,
        }
    )


    acquire_args: dict[str, object] = {}
    if post_acquire is not None:
        acquire_args["post_acquire"] = {
            "kind": post_acquire.kind,
            "args": dict(post_acquire.args),
            "display": post_acquire.display,
        }


    record = ExecutionRecord(
        issue=issue,
        execution_intent=execution_intent,
        owner_kind="UNCLAIMED",
        owner_id="NONE",
        lane_id=None,
        slot_id=slot_id,
        source_branch=_text(request.source_branch, "source_branch"),
        source_sha=_text(request.source_sha, "source_sha"),
        work_branch=_text(request.work_branch, "work_branch"),
        head_sha=_text(request.source_sha, "source_sha"),
        target_branch=_text(request.target_branch, "target_branch"),
        target_sha=_text(request.target_sha, "target_sha"),
        state="READY",
        semantic_state="READY",
        next_action=ActionSpec(kind="ACQUIRE", args=acquire_args, display=f"Acquire Issue #{issue}"),
        lease=None,
        active_run=None,
        transaction=None,
        qa=QAState(),
        blocker=None,
        closure=ClosureState(),
        chain=ChainState(parent_issue=parent_issue),
        recovery_history=(
            {
                "kind": "INGRESS_AUTHORITY",
                "authority_kind": authority_kind,
                "authority_ref": authority_ref,
                "authority_fingerprint": authority_fp,
                "dispatch_transport": dispatch_transport,
            },
        ),
        generation=1,
        updated_at=request.created_at,
    )
    return DispatchIngressPlan(
        request_fingerprint=request_fp,
        authority_fingerprint=authority_fp,
        record_fingerprint=execution_record_fingerprint(record),
        record=record,
    )