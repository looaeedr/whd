"""Canonical per-Issue execution state for the WHD control plane.

V2 is the semantic authority. Legacy claim/checkpoint JSON remain readable only
through :func:`execution_record_from_legacy` during migration. Callers should
consume one validated ``ExecutionRecord`` and must not reconstruct execution
meaning from prose or independently interpret claim/checkpoint payloads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping


SCHEMA = "WHD_EXECUTION_RECORD_V2"
VERSION = 2
CANONICAL_STATES = frozenset({"READY", "ACTIVE", "VERIFYING", "INTEGRATING", "BLOCKED", "DONE"})
BLOCKER_KINDS = frozenset(
    {"EXTERNAL_DEPENDENCY", "MISSING_CAPABILITY", "AUTHORITY_DENIED", "PLATFORM_FAILURE"}
)
TRANSACTION_STATUSES = frozenset(
    {"PREPARED", "AUTHORIZED", "APPLIED", "RECONCILED", "FAILED"}
)
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_FP_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ExecutionRecordError(ValueError):
    """Raised when durable payloads cannot describe one valid execution record."""


def _text(value: object, field_name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    result = str(value or "").strip()
    if not result:
        if optional:
            return None
        raise ExecutionRecordError(f"{field_name} must be nonblank")
    return result


def _issue(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ExecutionRecordError(f"{field_name} must be a positive issue number")
    try:
        result = int(str(value).lstrip("#"))
    except (TypeError, ValueError) as exc:
        raise ExecutionRecordError(f"{field_name} must be a positive issue number") from exc
    if result <= 0:
        raise ExecutionRecordError(f"{field_name} must be a positive issue number")
    return result


def _optional_issue(value: object, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    return _issue(value, field_name)


def _legacy_slot_id(value: object) -> str | None:
    """Normalize legacy slot sentinels into the V2 optional slot identity."""
    slot = _text(value, "slot_id", optional=True)
    if slot in (None, "UNBOUND", "NONE"):
        return None
    return slot


def _positive_int(value: object, field_name: str, *, optional: bool = False) -> int | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExecutionRecordError(f"{field_name} must be a positive integer")
    return value


def _sha(value: object, field_name: str, *, optional: bool = False) -> str | None:
    text = _text(value, field_name, optional=optional)
    if text is None:
        return None
    if not _SHA_RE.fullmatch(text):
        raise ExecutionRecordError(f"{field_name} must be a 40-character git SHA")
    return text.lower()


def _fingerprint(value: object, field_name: str, *, optional: bool = False) -> str | None:
    text = _text(value, field_name, optional=optional)
    if text is None:
        return None
    if not _FP_RE.fullmatch(text):
        raise ExecutionRecordError(f"{field_name} must be a 64-character SHA256 fingerprint")
    return text.lower()


def _timestamp(value: object, field_name: str, *, optional: bool = False) -> str | None:
    text = _text(value, field_name, optional=optional)
    if text is None:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutionRecordError(f"{field_name} must be an ISO-8601 timestamp") from exc
    return text


def _mapping(value: object, field_name: str, *, optional: bool = False) -> dict[str, object] | None:
    if value is None and optional:
        return None
    if not isinstance(value, Mapping):
        raise ExecutionRecordError(f"{field_name} must be an object")
    result = {str(key): item for key, item in value.items()}
    try:
        # Round-trip to ensure the durable payload is JSON-safe and detached from caller mutation.
        return json.loads(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise ExecutionRecordError(f"{field_name} must be JSON-serializable") from exc


def _history(value: object) -> tuple[dict[str, object], ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ExecutionRecordError("recovery_history must be an array")
    rows: list[dict[str, object]] = []
    for index, item in enumerate(value):
        row = _mapping(item, f"recovery_history[{index}]")
        assert row is not None
        rows.append(row)
    return tuple(rows)


@dataclass(frozen=True)
class ActionSpec:
    kind: str
    args: dict[str, object] = field(default_factory=dict)
    display: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _text(self.kind, "next_action kind"))
        args = _mapping(self.args, "next_action args")
        assert args is not None
        object.__setattr__(self, "args", args)
        object.__setattr__(self, "display", str(self.display or "").strip())


@dataclass(frozen=True)
class LeaseState:
    token: str
    invocation_identity: str
    expires_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "token", _text(self.token, "lease token"))
        object.__setattr__(
            self,
            "invocation_identity",
            _text(self.invocation_identity, "lease invocation_identity"),
        )
        object.__setattr__(self, "expires_at", _timestamp(self.expires_at, "lease expires_at"))


@dataclass(frozen=True)
class RunState:
    id: int
    head_sha: str
    purpose: str
    status: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _positive_int(self.id, "active_run id"))
        object.__setattr__(self, "head_sha", _sha(self.head_sha, "active_run head_sha"))
        object.__setattr__(self, "purpose", _text(self.purpose, "active_run purpose"))
        object.__setattr__(self, "status", _text(self.status, "active_run status", optional=True))


@dataclass(frozen=True)
class TransactionState:
    id: str
    kind: str
    status: str
    expected_fingerprint: str
    invocation_identity: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "transaction id"))
        object.__setattr__(self, "kind", _text(self.kind, "transaction kind"))
        status = _text(self.status, "transaction status")
        if status not in TRANSACTION_STATUSES:
            raise ExecutionRecordError(
                f"transaction status must be one of {sorted(TRANSACTION_STATUSES)}"
            )
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "expected_fingerprint",
            _fingerprint(self.expected_fingerprint, "transaction expected_fingerprint"),
        )
        object.__setattr__(
            self,
            "invocation_identity",
            _text(self.invocation_identity, "transaction invocation_identity", optional=True),
        )


@dataclass(frozen=True)
class QAState:
    last_accepted_run: int | None = None
    accepted_head_sha: str | None = None

    def __post_init__(self) -> None:
        run = _positive_int(self.last_accepted_run, "qa last_accepted_run", optional=True)
        head = _sha(self.accepted_head_sha, "qa accepted_head_sha", optional=True)
        if (run is None) != (head is None):
            raise ExecutionRecordError(
                "qa last_accepted_run and accepted_head_sha must be both present or both absent"
            )
        object.__setattr__(self, "last_accepted_run", run)
        object.__setattr__(self, "accepted_head_sha", head)


@dataclass(frozen=True)
class BlockerState:
    kind: str
    evidence: str
    recheck_after: str | None = None

    def __post_init__(self) -> None:
        kind = _text(self.kind, "blocker kind")
        if kind not in BLOCKER_KINDS:
            raise ExecutionRecordError(f"blocker kind must be one of {sorted(BLOCKER_KINDS)}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "evidence", _text(self.evidence, "blocker evidence"))
        object.__setattr__(
            self,
            "recheck_after",
            _timestamp(self.recheck_after, "blocker recheck_after", optional=True),
        )


@dataclass(frozen=True)
class ClosureState:
    merged_sha: str | None = None
    issue_closed: bool = False
    released_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.issue_closed, bool):
            raise ExecutionRecordError("closure issue_closed must be boolean")
        merged_sha = _sha(self.merged_sha, "closure merged_sha", optional=True)
        released_at = _timestamp(self.released_at, "closure released_at", optional=True)
        if released_at is not None and not self.issue_closed:
            raise ExecutionRecordError("closure released_at requires issue_closed=true")
        object.__setattr__(self, "merged_sha", merged_sha)
        object.__setattr__(self, "released_at", released_at)


@dataclass(frozen=True)
class ChainState:
    parent_issue: int | None = None
    next_issue: int | None = None
    next_action: ActionSpec | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_issue", _optional_issue(self.parent_issue, "chain parent_issue"))
        object.__setattr__(self, "next_issue", _optional_issue(self.next_issue, "chain next_issue"))
        if self.next_action is not None and not isinstance(self.next_action, ActionSpec):
            raise ExecutionRecordError("chain next_action must be an ActionSpec")
        if self.next_action is not None and self.next_issue is None:
            raise ExecutionRecordError("chain next_action requires next_issue")


@dataclass(frozen=True)
class ExecutionRecord:
    issue: int
    execution_intent: str
    owner_kind: str
    owner_id: str
    lane_id: str | None
    slot_id: str | None
    source_branch: str
    source_sha: str
    work_branch: str
    head_sha: str
    target_branch: str
    target_sha: str
    state: str
    semantic_state: str
    next_action: ActionSpec | None
    lease: LeaseState | None = None
    active_run: RunState | None = None
    transaction: TransactionState | None = None
    qa: QAState = field(default_factory=QAState)
    blocker: BlockerState | None = None
    closure: ClosureState = field(default_factory=ClosureState)
    chain: ChainState = field(default_factory=ChainState)
    recovery_history: tuple[dict[str, object], ...] = ()
    generation: int = 1
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "issue", _issue(self.issue, "issue"))
        object.__setattr__(self, "execution_intent", _text(self.execution_intent, "execution_intent"))
        object.__setattr__(self, "owner_kind", _text(self.owner_kind, "owner_kind"))
        object.__setattr__(self, "owner_id", _text(self.owner_id, "owner_id"))
        object.__setattr__(self, "lane_id", _text(self.lane_id, "lane_id", optional=True))
        object.__setattr__(self, "slot_id", _text(self.slot_id, "slot_id", optional=True))
        object.__setattr__(self, "source_branch", _text(self.source_branch, "source_branch"))
        object.__setattr__(self, "source_sha", _sha(self.source_sha, "source_sha"))
        object.__setattr__(self, "work_branch", _text(self.work_branch, "work_branch"))
        object.__setattr__(self, "head_sha", _sha(self.head_sha, "head_sha"))
        object.__setattr__(self, "target_branch", _text(self.target_branch, "target_branch"))
        object.__setattr__(self, "target_sha", _sha(self.target_sha, "target_sha"))
        state = _text(self.state, "state")
        if state not in CANONICAL_STATES:
            raise ExecutionRecordError(f"state must be one of {sorted(CANONICAL_STATES)}")
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "semantic_state", _text(self.semantic_state, "semantic_state"))
        if self.next_action is not None and not isinstance(self.next_action, ActionSpec):
            raise ExecutionRecordError("next_action must be an ActionSpec")
        if self.lease is not None and not isinstance(self.lease, LeaseState):
            raise ExecutionRecordError("lease must be a LeaseState")
        if self.active_run is not None and not isinstance(self.active_run, RunState):
            raise ExecutionRecordError("active_run must be a RunState")
        if self.transaction is not None and not isinstance(self.transaction, TransactionState):
            raise ExecutionRecordError("transaction must be a TransactionState")
        if not isinstance(self.qa, QAState):
            raise ExecutionRecordError("qa must be a QAState")
        if self.blocker is not None and not isinstance(self.blocker, BlockerState):
            raise ExecutionRecordError("blocker must be a BlockerState")
        if not isinstance(self.closure, ClosureState):
            raise ExecutionRecordError("closure must be a ClosureState")
        if not isinstance(self.chain, ChainState):
            raise ExecutionRecordError("chain must be a ChainState")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation <= 0:
            raise ExecutionRecordError("generation must be a positive integer")
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at, "updated_at", optional=True))
        object.__setattr__(self, "recovery_history", _history(self.recovery_history))

        if state == "DONE":
            if self.next_action is not None:
                raise ExecutionRecordError("DONE record must have next_action=null")
            if self.lease is not None:
                raise ExecutionRecordError("DONE record must not hold a lease")
            if not self.closure.issue_closed or self.closure.released_at is None:
                raise ExecutionRecordError("DONE record requires closed and released closure")
        elif self.next_action is None and state not in {"VERIFYING", "INTEGRATING"}:
            raise ExecutionRecordError(f"{state} record requires a next_action")

        if state == "BLOCKED" and self.blocker is None:
            raise ExecutionRecordError("BLOCKED record requires blocker evidence")
        if state != "BLOCKED" and self.blocker is not None:
            raise ExecutionRecordError("blocker may only be present when state=BLOCKED")
        if self.active_run is not None and self.active_run.head_sha != self.head_sha:
            raise ExecutionRecordError("active_run head must match record head_sha")

    @property
    def owner(self) -> str:
        """Compatibility alias for the original #844 projection API."""
        return self.owner_id

    @property
    def branch(self) -> str:
        """Compatibility alias for the original #844 projection API."""
        return self.work_branch

    @property
    def parent_issue(self) -> int | None:
        """Compatibility alias for callers not yet migrated to ``chain``."""
        return self.chain.parent_issue



def _action_from_payload(value: object, field_name: str, *, optional: bool = True) -> ActionSpec | None:
    if value is None and optional:
        return None
    if isinstance(value, ActionSpec):
        return value
    payload = _mapping(value, field_name)
    assert payload is not None
    return ActionSpec(
        kind=_text(payload.get("kind"), f"{field_name} kind"),
        args=_mapping(payload.get("args", {}), f"{field_name} args") or {},
        display=str(payload.get("display") or "").strip(),
    )


def _lease_from_payload(value: object) -> LeaseState | None:
    if value is None:
        return None
    payload = _mapping(value, "lease")
    assert payload is not None
    return LeaseState(
        token=_text(payload.get("token"), "lease token"),
        invocation_identity=_text(payload.get("invocation_identity"), "lease invocation_identity"),
        expires_at=_text(payload.get("expires_at"), "lease expires_at"),
    )


def _run_from_payload(value: object) -> RunState | None:
    if value is None:
        return None
    payload = _mapping(value, "active_run")
    assert payload is not None
    return RunState(
        id=_positive_int(payload.get("id"), "active_run id"),
        head_sha=_text(payload.get("head_sha"), "active_run head_sha"),
        purpose=_text(payload.get("purpose"), "active_run purpose"),
        status=_text(payload.get("status"), "active_run status", optional=True),
    )


def _transaction_from_payload(value: object) -> TransactionState | None:
    if value is None:
        return None
    payload = _mapping(value, "transaction")
    assert payload is not None
    return TransactionState(
        id=_text(payload.get("id"), "transaction id"),
        kind=_text(payload.get("kind"), "transaction kind"),
        status=_text(payload.get("status"), "transaction status"),
        expected_fingerprint=_text(
            payload.get("expected_fingerprint"), "transaction expected_fingerprint"
        ),
        invocation_identity=_text(
            payload.get("invocation_identity"), "transaction invocation_identity", optional=True
        ),
    )


def _qa_from_payload(value: object) -> QAState:
    payload = _mapping(value if value is not None else {}, "qa")
    assert payload is not None
    return QAState(
        last_accepted_run=_positive_int(
            payload.get("last_accepted_run"), "qa last_accepted_run", optional=True
        ),
        accepted_head_sha=_text(
            payload.get("accepted_head_sha"), "qa accepted_head_sha", optional=True
        ),
    )


def _blocker_from_payload(value: object) -> BlockerState | None:
    if value is None:
        return None
    payload = _mapping(value, "blocker")
    assert payload is not None
    return BlockerState(
        kind=_text(payload.get("kind"), "blocker kind"),
        evidence=_text(payload.get("evidence"), "blocker evidence"),
        recheck_after=_text(payload.get("recheck_after"), "blocker recheck_after", optional=True),
    )


def _closure_from_payload(value: object) -> ClosureState:
    payload = _mapping(value if value is not None else {}, "closure")
    assert payload is not None
    return ClosureState(
        merged_sha=_text(payload.get("merged_sha"), "closure merged_sha", optional=True),
        issue_closed=payload.get("issue_closed", False),
        released_at=_text(payload.get("released_at"), "closure released_at", optional=True),
    )


def _chain_from_payload(value: object) -> ChainState:
    payload = _mapping(value if value is not None else {}, "chain")
    assert payload is not None
    return ChainState(
        parent_issue=_optional_issue(payload.get("parent_issue"), "chain parent_issue"),
        next_issue=_optional_issue(payload.get("next_issue"), "chain next_issue"),
        next_action=_action_from_payload(payload.get("next_action"), "chain next_action"),
    )


def execution_record_from_payload(payload: Mapping[str, object]) -> ExecutionRecord:
    """Load and validate a native V2 execution-record payload."""
    if not isinstance(payload, Mapping):
        raise ExecutionRecordError("execution record payload must be an object")
    if payload.get("schema") != SCHEMA or payload.get("version") != VERSION:
        raise ExecutionRecordError(f"execution record must use {SCHEMA} version {VERSION}")

    return ExecutionRecord(
        issue=_issue(payload.get("issue"), "issue"),
        execution_intent=_text(payload.get("execution_intent"), "execution_intent"),
        owner_kind=_text(payload.get("owner_kind"), "owner_kind"),
        owner_id=_text(payload.get("owner_id"), "owner_id"),
        lane_id=_text(payload.get("lane_id"), "lane_id", optional=True),
        slot_id=_text(payload.get("slot_id"), "slot_id", optional=True),
        source_branch=_text(payload.get("source_branch"), "source_branch"),
        source_sha=_text(payload.get("source_sha"), "source_sha"),
        work_branch=_text(payload.get("work_branch"), "work_branch"),
        head_sha=_text(payload.get("head_sha"), "head_sha"),
        target_branch=_text(payload.get("target_branch"), "target_branch"),
        target_sha=_text(payload.get("target_sha"), "target_sha"),
        state=_text(payload.get("state"), "state"),
        semantic_state=_text(payload.get("semantic_state"), "semantic_state"),
        next_action=_action_from_payload(payload.get("next_action"), "next_action"),
        lease=_lease_from_payload(payload.get("lease")),
        active_run=_run_from_payload(payload.get("active_run")),
        transaction=_transaction_from_payload(payload.get("transaction")),
        qa=_qa_from_payload(payload.get("qa")),
        blocker=_blocker_from_payload(payload.get("blocker")),
        closure=_closure_from_payload(payload.get("closure")),
        chain=_chain_from_payload(payload.get("chain")),
        recovery_history=_history(payload.get("recovery_history")),
        generation=_positive_int(payload.get("generation"), "generation"),
        updated_at=_text(payload.get("updated_at"), "updated_at", optional=True),
    )


def _legacy_owner_kind(executor_source: object) -> str:
    source = str(executor_source or "").strip().lower()
    if source == "scheduler":
        return "SCHEDULER"
    if source in {"chatgpt_interactive", "interactive"}:
        return "INTERACTIVE"
    if source == "local":
        return "LOCAL"
    return "LEGACY"


def _legacy_state(checkpoint_state: str, *, closure: ClosureState) -> str:
    state = checkpoint_state.upper()
    if closure.issue_closed and closure.released_at is not None:
        return "DONE"
    if state in {"WAITING_REMOTE", "REMOTE_QA", "VERIFYING", "QA_RUNNING"}:
        return "VERIFYING"
    if state in {
        "CLOSING",
        "CLEANUP",
        "DRIFT_AUDIT",
        "FINALIZATION_PENDING",
        "ISSUE_CLOSE_PENDING",
        "RELEASE_HANDOFF_PENDING",
        "TERMINAL_SUCCESS",
    }:
        return "INTEGRATING"
    if state in {"BLOCKED", "WAITING_EXTERNAL"}:
        return "BLOCKED"
    if state == "READY":
        return "READY"
    return "ACTIVE"


def _legacy_lease(claim: Mapping[str, object]) -> LeaseState | None:
    token = _text(claim.get("lease_token"), "lease token", optional=True)
    expires = _text(claim.get("lease_expires_at"), "lease expires_at", optional=True)

    # Legacy scheduler claims already carried invocation provenance before Flow v2
    # introduced leases.  An invocation_identity by itself is therefore not lease
    # evidence and must not synthesize a half-lease during migration.
    if token is None and expires is None:
        return None

    invocation = _text(
        claim.get("invocation_identity"), "lease invocation_identity", optional=True
    )
    if token is None or invocation is None or expires is None:
        raise ExecutionRecordError("legacy lease requires token, invocation_identity and expires_at")
    return LeaseState(token=token, invocation_identity=invocation, expires_at=expires)


def _legacy_run(
    checkpoint: Mapping[str, object], *, head_sha: str
) -> RunState | None:
    run_id = _positive_int(checkpoint.get("run_id"), "active_run id", optional=True)
    if run_id is None:
        return None
    run_head = _text(
        checkpoint.get("active_run_head_sha"), "active_run head_sha", optional=True
    ) or head_sha
    purpose = _text(
        checkpoint.get("active_run_purpose"), "active_run purpose", optional=True
    ) or "LEGACY_REMOTE_RUN"
    status = _text(checkpoint.get("run_status"), "active_run status", optional=True)
    return RunState(id=run_id, head_sha=run_head, purpose=purpose, status=status)


def _legacy_transaction(checkpoint: Mapping[str, object]) -> TransactionState | None:
    operation = checkpoint.get("operation")
    if operation in (None, ""):
        return None
    if not isinstance(operation, Mapping):
        raise ExecutionRecordError("legacy operation must be an object")
    return TransactionState(
        id=_text(operation.get("id"), "transaction id"),
        kind=_text(operation.get("kind"), "transaction kind"),
        status=_text(operation.get("status"), "transaction status"),
        expected_fingerprint=_text(
            operation.get("expected_fingerprint"), "transaction expected_fingerprint"
        ),
        invocation_identity=_text(
            operation.get("invocation_identity"), "transaction invocation_identity", optional=True
        ),
    )


def execution_record_from_legacy(
    claim: Mapping[str, object],
    checkpoint: Mapping[str, object],
) -> ExecutionRecord:
    """Project one legacy claim/checkpoint pair into a validated V2 record.

    The adapter preserves legacy text only as ``ActionSpec(kind='LEGACY_TEXT')``;
    it never parses prose to infer machine intent.
    """
    if not isinstance(claim, Mapping) or not isinstance(checkpoint, Mapping):
        raise ExecutionRecordError("legacy claim and checkpoint must be mappings")

    claim_issue = _issue(claim.get("issue"), "claim issue")
    checkpoint_issue = _issue(checkpoint.get("issue"), "checkpoint issue")
    if claim_issue != checkpoint_issue:
        raise ExecutionRecordError(
            f"issue identity mismatch: claim={claim_issue} checkpoint={checkpoint_issue}"
        )

    claim_branch = _text(claim.get("work_branch"), "claim branch")
    checkpoint_branch = _text(checkpoint.get("branch"), "checkpoint branch")
    if claim_branch != checkpoint_branch:
        raise ExecutionRecordError(
            f"branch identity mismatch: claim={claim_branch!r} checkpoint={checkpoint_branch!r}"
        )

    claim_head = _sha(claim.get("head_sha"), "claim head")
    checkpoint_head = _sha(checkpoint.get("head_sha"), "checkpoint head")
    if claim_head != checkpoint_head:
        raise ExecutionRecordError(
            f"head identity mismatch: claim={claim_head!r} checkpoint={checkpoint_head!r}"
        )

    claim_next = _text(claim.get("next_action"), "claim next_action", optional=True)
    checkpoint_next = _text(
        checkpoint.get("next_action"), "checkpoint next_action", optional=True
    )
    if claim_next != checkpoint_next:
        raise ExecutionRecordError(
            "next_action semantic mismatch: "
            f"claim={claim_next!r} checkpoint={checkpoint_next!r}"
        )

    claim_parent = _optional_issue(claim.get("master_issue"), "claim parent issue")
    checkpoint_parent = _optional_issue(
        checkpoint.get("master_issue"), "checkpoint parent issue"
    )
    if claim_parent is not None and checkpoint_parent is not None and claim_parent != checkpoint_parent:
        raise ExecutionRecordError(
            f"parent issue mismatch: claim={claim_parent} checkpoint={checkpoint_parent}"
        )
    parent_issue = claim_parent if claim_parent is not None else checkpoint_parent

    target_branch = _text(claim.get("production_target"), "target branch")
    target_sha = _sha(claim.get("production_sha"), "target sha")
    source_branch = _text(claim.get("source_branch"), "source_branch", optional=True) or target_branch
    source_sha = _sha(claim.get("base_sha"), "source_sha", optional=True) or target_sha
    semantic_state = _text(checkpoint.get("state"), "checkpoint semantic state")

    issue_closed = bool(checkpoint.get("issue_closed", False))
    released_at = _text(checkpoint.get("released_at"), "closure released_at", optional=True)
    merged_sha = _text(checkpoint.get("merged_sha"), "closure merged_sha", optional=True)
    closure = ClosureState(
        merged_sha=merged_sha,
        issue_closed=issue_closed,
        released_at=released_at,
    )

    next_issue = _optional_issue(checkpoint.get("next_issue"), "chain next_issue")
    chain_next_text = _text(
        checkpoint.get("chain_next_action"), "chain next_action", optional=True
    )
    chain_next = (
        ActionSpec(kind="LEGACY_TEXT", args={}, display=chain_next_text)
        if chain_next_text is not None
        else None
    )

    current_action = (
        ActionSpec(kind="LEGACY_TEXT", args={}, display=checkpoint_next)
        if checkpoint_next is not None
        else None
    )

    accepted_run = _positive_int(
        checkpoint.get("last_accepted_run_id"), "qa last_accepted_run", optional=True
    )
    accepted_head = _text(
        checkpoint.get("last_accepted_head_sha"), "qa accepted_head_sha", optional=True
    )
    qa = QAState(last_accepted_run=accepted_run, accepted_head_sha=accepted_head)

    executor_source = claim.get("executor_source")
    owner = _text(claim.get("worker"), "claim owner")
    lane_id = _text(claim.get("scheduler_lane"), "lane_id", optional=True)
    if lane_id is None and str(executor_source or "").strip().lower() == "scheduler":
        lane_id = owner

    state = _legacy_state(semantic_state, closure=closure)
    blocker = None
    if state == "BLOCKED":
        blocker_kind = _text(
            checkpoint.get("blocker_kind"), "blocker kind", optional=True
        ) or "EXTERNAL_DEPENDENCY"
        blocker_evidence = _text(
            checkpoint.get("blocker"), "blocker evidence", optional=True
        ) or "legacy blocked state"
        blocker = BlockerState(
            kind=blocker_kind,
            evidence=blocker_evidence,
            recheck_after=_text(
                checkpoint.get("recheck_after"), "blocker recheck_after", optional=True
            ),
        )

    # Legacy terminal-success means the work may be ready for finalization, not
    # that the Issue is already closed/released. V2 only enters DONE when those
    # facts are explicit in durable evidence.
    if state == "DONE" and not (closure.issue_closed and closure.released_at):
        state = "INTEGRATING"

    return ExecutionRecord(
        issue=claim_issue,
        execution_intent=_text(
            claim.get("execution_intent"), "execution_intent", optional=True
        )
        or "LEGACY_UNSPECIFIED",
        owner_kind=_legacy_owner_kind(executor_source),
        owner_id=owner,
        lane_id=lane_id,
        slot_id=_legacy_slot_id(claim.get("slot_id")),
        source_branch=source_branch,
        source_sha=source_sha,
        work_branch=claim_branch,
        head_sha=claim_head,
        target_branch=target_branch,
        target_sha=target_sha,
        state=state,
        semantic_state=semantic_state,
        next_action=current_action,
        lease=_legacy_lease(claim),
        active_run=_legacy_run(checkpoint, head_sha=claim_head),
        transaction=_legacy_transaction(checkpoint),
        qa=qa,
        blocker=blocker,
        closure=closure,
        chain=ChainState(
            parent_issue=parent_issue,
            next_issue=next_issue,
            next_action=chain_next,
        ),
        recovery_history=_history(checkpoint.get("recovery_history")),
        generation=1,
        updated_at=_text(
            checkpoint.get("updated_at") or claim.get("last_update"),
            "updated_at",
            optional=True,
        ),
    )


def execution_record_to_payload(record: ExecutionRecord) -> dict[str, object]:
    """Serialize a validated record using deterministic V2 field names."""
    if not isinstance(record, ExecutionRecord):
        raise ExecutionRecordError("record must be an ExecutionRecord")
    data = asdict(record)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generation": data.pop("generation"),
        **data,
    }


def execution_record_fingerprint(record: ExecutionRecord) -> str:
    """Return the stable optimistic-concurrency fingerprint for ``record``."""
    canonical = json.dumps(
        execution_record_to_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_execution_record(path: str | Path) -> ExecutionRecord:
    """Load a native V2 record from disk and validate all invariants."""
    record_path = Path(path)
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionRecordError(f"cannot load execution record: {record_path}") from exc
    if not isinstance(payload, Mapping):
        raise ExecutionRecordError("execution record file must contain a JSON object")
    return execution_record_from_payload(payload)
