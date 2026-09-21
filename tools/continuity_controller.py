"""Executable continuity checkpoint/resume/finalization/turn-exit authority.

This module is intentionally independent from application geometry and UI code. It
exists to make long-running development/QA workflows fail closed when their durable
state is incomplete, resumable after a runtime cut, impossible to finalize while
non-terminal, and unable to end an assistant turn while autonomous work remains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


CHECKPOINT_VERSION = 1
FINALIZATION_PROOF_VERSION = 1
TURN_EXIT_PROOF_VERSION = 1
_UNSET = object()


class ContinuityState(str, Enum):
    RUNNING = "RUNNING"
    WAITING_REMOTE = "WAITING_REMOTE"
    RECOVERING = "RECOVERING"
    BLOCKED = "BLOCKED"
    TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


class ScheduledResumeAction(str, Enum):
    """Wake-routing decisions derived from canonical continuity state."""

    EXECUTE_NEXT_ACTION = "EXECUTE_NEXT_ACTION"
    POLL_LOCKED_RUN = "POLL_LOCKED_RUN"
    CONTINUE_RECOVERY = "CONTINUE_RECOVERY"
    REPORT_BLOCKER = "REPORT_BLOCKER"
    CLOSING_HANDOFF = "CLOSING_HANDOFF"
    NO_OP = "NO_OP"


class ChainContinuationState(str, Enum):
    """Master/work-order continuation state carried by a terminal child checkpoint."""

    NONE = "NONE"
    NEXT_CHILD_EXECUTABLE = "NEXT_CHILD_EXECUTABLE"
    NEXT_CHILD_BLOCKED = "NEXT_CHILD_BLOCKED"
    CHAIN_COMPLETE = "CHAIN_COMPLETE"
    USER_STOPPED = "USER_STOPPED"


NONTERMINAL_STATES = frozenset(
    {
        ContinuityState.RUNNING,
        ContinuityState.WAITING_REMOTE,
        ContinuityState.RECOVERING,
        ContinuityState.BLOCKED,
    }
)
TERMINAL_STATES = frozenset(
    {
        ContinuityState.TERMINAL_SUCCESS,
        ContinuityState.TERMINAL_FAILURE,
    }
)
TURN_EXIT_BLOCKING_STATES = frozenset(
    {
        ContinuityState.RUNNING,
        ContinuityState.WAITING_REMOTE,
        ContinuityState.RECOVERING,
    }
)


class CheckpointError(RuntimeError):
    """Raised when durable continuity state is malformed or an illegal transition occurs."""


class FinalizationBlocked(CheckpointError):
    """Raised when closure/finalization is attempted without current machine authority."""


class TurnExitBlocked(CheckpointError):
    """Raised when an assistant turn tries to end while autonomous work remains."""


def _require_text(name: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        raise CheckpointError(f"{name} must be nonblank")
    return str(value).strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _validate_positive_int(name: str, value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
        raise CheckpointError(f"{name} must be a positive integer when present")


def _validate_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CheckpointError(f"{name} must be a non-negative integer")


def _normalize_optional_utc_timestamp(value: str | None) -> str | None:
    value = _normalize_optional_text(value)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckpointError("blocked_last_notified_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CheckpointError("blocked_last_notified_at must be timezone-aware")
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class Checkpoint:
    issue: str
    branch: str
    head_sha: str
    state: ContinuityState
    next_action: str | None
    run_id: int | None = None
    job_id: int | None = None
    log_cursor: str | None = None
    blocked_count: int = 0
    blocked_last_notified_at: str | None = None
    evidence: tuple[str, ...] = ()
    master_issue: str | None = None
    chain_state: ChainContinuationState = ChainContinuationState.NONE
    next_issue: str | None = None
    chain_next_action: str | None = None
    chain_reason: str | None = None

    def __post_init__(self) -> None:
        issue = _require_text("issue", self.issue)
        branch = _require_text("branch", self.branch)
        head_sha = _require_text("head_sha", self.head_sha)

        try:
            state = self.state if isinstance(self.state, ContinuityState) else ContinuityState(self.state)
        except (TypeError, ValueError) as exc:
            raise CheckpointError(f"invalid continuity state: {self.state!r}") from exc

        next_action = _normalize_optional_text(self.next_action)
        log_cursor = _normalize_optional_text(self.log_cursor)
        master_issue = _normalize_optional_text(self.master_issue)
        next_issue = _normalize_optional_text(self.next_issue)
        chain_next_action = _normalize_optional_text(self.chain_next_action)
        chain_reason = _normalize_optional_text(self.chain_reason)
        try:
            chain_state = (
                self.chain_state
                if isinstance(self.chain_state, ChainContinuationState)
                else ChainContinuationState(self.chain_state)
            )
        except (TypeError, ValueError) as exc:
            raise CheckpointError(
                f"invalid chain continuation state: {self.chain_state!r}"
            ) from exc
        blocked_last_notified_at = _normalize_optional_utc_timestamp(
            self.blocked_last_notified_at
        )
        _validate_positive_int("run_id", self.run_id)
        _validate_positive_int("job_id", self.job_id)
        _validate_nonnegative_int("blocked_count", self.blocked_count)

        if state is not ContinuityState.BLOCKED and (
            self.blocked_count != 0 or blocked_last_notified_at is not None
        ):
            raise CheckpointError(
                "blocked metadata is only valid while state is BLOCKED"
            )

        if state in NONTERMINAL_STATES and next_action is None:
            raise CheckpointError(f"next_action is required for non-terminal state {state.value}")
        if state in TERMINAL_STATES and next_action is not None:
            raise CheckpointError(f"next_action must be None for terminal state {state.value}")
        if state is ContinuityState.WAITING_REMOTE:
            if self.run_id is None:
                raise CheckpointError("run_id is required for WAITING_REMOTE")
            _require_text("head_sha", head_sha)

        if master_issue is None:
            if chain_state is not ChainContinuationState.NONE or any(
                value is not None
                for value in (next_issue, chain_next_action, chain_reason)
            ):
                raise CheckpointError(
                    "chain continuation metadata requires master_issue"
                )
        else:
            if state not in TERMINAL_STATES:
                raise CheckpointError(
                    "Master-chain continuation metadata is only valid on terminal child checkpoints"
                )
            if chain_state is ChainContinuationState.NONE:
                raise CheckpointError(
                    "chain_state is required when master_issue is present"
                )
            if chain_state is ChainContinuationState.NEXT_CHILD_EXECUTABLE:
                if next_issue is None or chain_next_action is None:
                    raise CheckpointError(
                        "NEXT_CHILD_EXECUTABLE requires next_issue and chain_next_action"
                    )
            elif chain_state is ChainContinuationState.NEXT_CHILD_BLOCKED:
                if chain_reason is None:
                    raise CheckpointError(
                        "NEXT_CHILD_BLOCKED requires chain_reason"
                    )
                if chain_next_action is not None:
                    raise CheckpointError(
                        "NEXT_CHILD_BLOCKED cannot carry chain_next_action"
                    )
            elif chain_state is ChainContinuationState.CHAIN_COMPLETE:
                if next_issue is not None or chain_next_action is not None:
                    raise CheckpointError(
                        "CHAIN_COMPLETE cannot carry next_issue or chain_next_action"
                    )
            elif chain_state is ChainContinuationState.USER_STOPPED:
                if chain_reason is None:
                    raise CheckpointError("USER_STOPPED requires chain_reason")
                if chain_next_action is not None:
                    raise CheckpointError(
                        "USER_STOPPED cannot carry chain_next_action"
                    )

        normalized_evidence: list[str] = []
        for index, item in enumerate(self.evidence):
            normalized_evidence.append(_require_text(f"evidence[{index}]", item))

        object.__setattr__(self, "issue", issue)
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "head_sha", head_sha)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "next_action", next_action)
        object.__setattr__(self, "log_cursor", log_cursor)
        object.__setattr__(self, "master_issue", master_issue)
        object.__setattr__(self, "chain_state", chain_state)
        object.__setattr__(self, "next_issue", next_issue)
        object.__setattr__(self, "chain_next_action", chain_next_action)
        object.__setattr__(self, "chain_reason", chain_reason)
        object.__setattr__(self, "blocked_last_notified_at", blocked_last_notified_at)
        object.__setattr__(self, "evidence", tuple(normalized_evidence))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


def scheduled_resume_action(checkpoint: Checkpoint) -> ScheduledResumeAction:
    """Map canonical checkpoint state to one scheduler wake action.

    This is intentionally a pure routing function. It does not mutate or persist
    the checkpoint and therefore cannot become a second workflow state machine.
    """

    if (
        checkpoint.is_terminal
        and checkpoint.chain_state is ChainContinuationState.NEXT_CHILD_EXECUTABLE
    ):
        return ScheduledResumeAction.EXECUTE_NEXT_ACTION
    if (
        checkpoint.is_terminal
        and checkpoint.chain_state is ChainContinuationState.NEXT_CHILD_BLOCKED
    ):
        return ScheduledResumeAction.REPORT_BLOCKER

    mapping = {
        ContinuityState.RUNNING: ScheduledResumeAction.EXECUTE_NEXT_ACTION,
        ContinuityState.WAITING_REMOTE: ScheduledResumeAction.POLL_LOCKED_RUN,
        ContinuityState.RECOVERING: ScheduledResumeAction.CONTINUE_RECOVERY,
        ContinuityState.BLOCKED: ScheduledResumeAction.REPORT_BLOCKER,
        ContinuityState.TERMINAL_SUCCESS: ScheduledResumeAction.CLOSING_HANDOFF,
        ContinuityState.TERMINAL_FAILURE: ScheduledResumeAction.CLOSING_HANDOFF,
    }
    return mapping[checkpoint.state]


@dataclass(frozen=True)
class FinalizationProof:
    """Machine receipt emitted only after the owned finalization guard passes.

    This receipt is process-integrity evidence, not a cryptographic signature against a
    malicious local writer. Its purpose is to make the canonical closure path reject
    accidental guard bypass, wrong-owner checkpoints, and stale post-guard mutations.
    """

    version: int
    issue: str
    branch: str
    head_sha: str
    checkpoint_fingerprint: str


def _to_payload(checkpoint: Checkpoint) -> dict[str, object]:
    data = asdict(checkpoint)
    data["state"] = checkpoint.state.value
    data["chain_state"] = checkpoint.chain_state.value
    data["evidence"] = list(checkpoint.evidence)
    return {"version": CHECKPOINT_VERSION, **data}


def checkpoint_to_payload(checkpoint: Checkpoint) -> dict[str, object]:
    """Public canonical JSON payload for file or GitHub-backed durable storage."""

    return _to_payload(checkpoint)


def _checkpoint_fingerprint(checkpoint: Checkpoint) -> str:
    canonical = json.dumps(
        _to_payload(checkpoint),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def checkpoint_fingerprint(checkpoint: Checkpoint) -> str:
    """Public stable digest for receipts bound to canonical checkpoint content."""

    return _checkpoint_fingerprint(checkpoint)


def _atomic_write_text(path: Path, payload: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            if not payload.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def save_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    """Persist checkpoint atomically in the target directory."""

    payload = json.dumps(_to_payload(checkpoint), ensure_ascii=False, indent=2, sort_keys=True)
    _atomic_write_text(Path(path), payload)


def checkpoint_from_payload(payload: object) -> Checkpoint:
    """Validate one canonical checkpoint payload from any durable transport."""

    if not isinstance(payload, dict):
        raise CheckpointError("checkpoint payload must be a JSON object")
    version = payload.get("version")
    if version != CHECKPOINT_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint version {version!r}; expected {CHECKPOINT_VERSION}"
        )

    allowed = {
        "version",
        "issue",
        "branch",
        "head_sha",
        "state",
        "next_action",
        "run_id",
        "job_id",
        "log_cursor",
        "blocked_count",
        "blocked_last_notified_at",
        "evidence",
        "master_issue",
        "chain_state",
        "next_issue",
        "chain_next_action",
        "chain_reason",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise CheckpointError(f"unknown checkpoint fields: {sorted(unknown)}")

    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise CheckpointError("evidence must be a list of strings")

    try:
        state = ContinuityState(payload["state"])
        return Checkpoint(
            issue=payload["issue"],
            branch=payload["branch"],
            head_sha=payload["head_sha"],
            state=state,
            next_action=payload.get("next_action"),
            run_id=payload.get("run_id"),
            job_id=payload.get("job_id"),
            log_cursor=payload.get("log_cursor"),
            blocked_count=payload.get("blocked_count", 0),
            blocked_last_notified_at=payload.get("blocked_last_notified_at"),
            evidence=tuple(evidence),
            master_issue=payload.get("master_issue"),
            chain_state=ChainContinuationState(
                payload.get("chain_state", ChainContinuationState.NONE.value)
            ),
            next_issue=payload.get("next_issue"),
            chain_next_action=payload.get("chain_next_action"),
            chain_reason=payload.get("chain_reason"),
        )
    except KeyError as exc:
        raise CheckpointError(f"missing checkpoint field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise CheckpointError("checkpoint contains invalid field values") from exc


def load_checkpoint(path: Path) -> Checkpoint:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"invalid checkpoint JSON: {path}") from exc
    return checkpoint_from_payload(payload)


def transition_checkpoint(
    checkpoint: Checkpoint,
    *,
    state: ContinuityState,
    next_action: str | None = None,
    run_id: int | None | object = _UNSET,
    job_id: int | None | object = _UNSET,
    head_sha: str | None | object = _UNSET,
    log_cursor: str | None | object = _UNSET,
    blocked_count: int | object = _UNSET,
    blocked_last_notified_at: str | None | object = _UNSET,
    evidence: tuple[str, ...] | None = None,
    master_issue: str | None | object = _UNSET,
    chain_state: ChainContinuationState | str | object = _UNSET,
    next_issue: str | None | object = _UNSET,
    chain_next_action: str | None | object = _UNSET,
    chain_reason: str | None | object = _UNSET,
) -> Checkpoint:
    """Return a validated next checkpoint without reusing stale remote ownership."""

    if checkpoint.is_terminal:
        raise CheckpointError(
            f"terminal checkpoint {checkpoint.state.value} cannot transition back to active work"
        )

    entering_new_remote_lock = (
        state is ContinuityState.WAITING_REMOTE
        and checkpoint.state is not ContinuityState.WAITING_REMOTE
    )
    staying_on_remote_lock = (
        state is ContinuityState.WAITING_REMOTE
        and checkpoint.state is ContinuityState.WAITING_REMOTE
    )

    if entering_new_remote_lock and (run_id is _UNSET or run_id is None):
        raise CheckpointError("explicit run_id is required when entering a new WAITING_REMOTE lock")

    if entering_new_remote_lock:
        next_run_id = run_id
        next_job_id = None if job_id is _UNSET else job_id
        next_head_sha = checkpoint.head_sha if head_sha is _UNSET else head_sha
        next_log_cursor = None if log_cursor is _UNSET else log_cursor
    elif staying_on_remote_lock:
        next_run_id = checkpoint.run_id if run_id is _UNSET else run_id
        next_job_id = checkpoint.job_id if job_id is _UNSET else job_id
        next_head_sha = checkpoint.head_sha if head_sha is _UNSET else head_sha
        next_log_cursor = checkpoint.log_cursor if log_cursor is _UNSET else log_cursor
    else:
        next_run_id = checkpoint.run_id if run_id is _UNSET else run_id
        next_job_id = checkpoint.job_id if job_id is _UNSET else job_id
        next_head_sha = checkpoint.head_sha if head_sha is _UNSET else head_sha
        next_log_cursor = checkpoint.log_cursor if log_cursor is _UNSET else log_cursor

    if state is ContinuityState.BLOCKED:
        next_blocked_count = (
            checkpoint.blocked_count if blocked_count is _UNSET else blocked_count
        )
        next_blocked_last_notified_at = (
            checkpoint.blocked_last_notified_at
            if blocked_last_notified_at is _UNSET
            else blocked_last_notified_at
        )
    else:
        next_blocked_count = 0
        next_blocked_last_notified_at = None

    merged_evidence = checkpoint.evidence + (() if evidence is None else tuple(evidence))
    return replace(
        checkpoint,
        state=state,
        next_action=next_action,
        run_id=next_run_id,
        job_id=next_job_id,
        head_sha=next_head_sha,
        log_cursor=next_log_cursor,
        blocked_count=next_blocked_count,
        blocked_last_notified_at=next_blocked_last_notified_at,
        evidence=merged_evidence,
        master_issue=checkpoint.master_issue if master_issue is _UNSET else master_issue,
        chain_state=checkpoint.chain_state if chain_state is _UNSET else chain_state,
        next_issue=checkpoint.next_issue if next_issue is _UNSET else next_issue,
        chain_next_action=(
            checkpoint.chain_next_action
            if chain_next_action is _UNSET
            else chain_next_action
        ),
        chain_reason=checkpoint.chain_reason if chain_reason is _UNSET else chain_reason,
    )


def assert_finalizable(checkpoint: Checkpoint) -> None:
    """State-only predicate retained for controller internals and legacy behavior tests.

    Closure authorization MUST use :func:`authorize_finalization`, which additionally
    binds the terminal state to the expected owning checkpoint identity.
    """

    if not checkpoint.is_terminal:
        raise FinalizationBlocked(
            f"non-terminal checkpoint {checkpoint.state.value} cannot be finalized; "
            f"next_action={checkpoint.next_action!r}"
        )


def _expected_owner(
    *,
    expected_issue: str | None,
    expected_branch: str | None,
    expected_head_sha: str | None,
) -> tuple[str, str, str]:
    fields = {
        "issue": expected_issue,
        "branch": expected_branch,
        "head_sha": expected_head_sha,
    }
    normalized: dict[str, str] = {}
    for name, value in fields.items():
        if value is None or not str(value).strip():
            raise FinalizationBlocked(
                f"owning checkpoint identity is required: missing expected_{name}"
            )
        normalized[name] = str(value).strip()
    return normalized["issue"], normalized["branch"], normalized["head_sha"]


def _assert_owning_checkpoint(
    checkpoint: Checkpoint,
    *,
    expected_issue: str | None,
    expected_branch: str | None,
    expected_head_sha: str | None,
) -> tuple[str, str, str]:
    issue, branch, head_sha = _expected_owner(
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    mismatches: list[str] = []
    if checkpoint.issue != issue:
        mismatches.append(f"issue expected={issue!r} actual={checkpoint.issue!r}")
    if checkpoint.branch != branch:
        mismatches.append(f"branch expected={branch!r} actual={checkpoint.branch!r}")
    if checkpoint.head_sha != head_sha:
        mismatches.append(f"head_sha expected={head_sha!r} actual={checkpoint.head_sha!r}")
    if mismatches:
        raise FinalizationBlocked("owning checkpoint mismatch: " + "; ".join(mismatches))
    return issue, branch, head_sha


def authorize_finalization(
    checkpoint: Checkpoint,
    *,
    expected_issue: str | None,
    expected_branch: str | None,
    expected_head_sha: str | None,
) -> FinalizationProof:
    """Run the canonical closure guard and return proof bound to exact checkpoint bytes."""

    issue, branch, head_sha = _assert_owning_checkpoint(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    assert_finalizable(checkpoint)
    return FinalizationProof(
        version=FINALIZATION_PROOF_VERSION,
        issue=issue,
        branch=branch,
        head_sha=head_sha,
        checkpoint_fingerprint=_checkpoint_fingerprint(checkpoint),
    )


def save_finalization_proof(path: Path, proof: FinalizationProof) -> None:
    payload = json.dumps(asdict(proof), ensure_ascii=False, indent=2, sort_keys=True)
    _atomic_write_text(Path(path), payload)


def load_finalization_proof(path: Path) -> FinalizationProof:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FinalizationBlocked(
            f"guard invocation proof is required but proof file is missing: {path}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalizationBlocked(f"invalid finalization proof: {path}") from exc

    if not isinstance(payload, dict):
        raise FinalizationBlocked("invalid finalization proof: root must be an object")
    expected_fields = {
        "version",
        "issue",
        "branch",
        "head_sha",
        "checkpoint_fingerprint",
    }
    if set(payload) != expected_fields:
        raise FinalizationBlocked(
            "invalid finalization proof fields: "
            f"expected={sorted(expected_fields)!r} actual={sorted(payload)!r}"
        )
    if payload.get("version") != FINALIZATION_PROOF_VERSION:
        raise FinalizationBlocked(
            f"unsupported finalization proof version {payload.get('version')!r}; "
            f"expected {FINALIZATION_PROOF_VERSION}"
        )
    try:
        issue = _require_text("proof issue", payload.get("issue"))
        branch = _require_text("proof branch", payload.get("branch"))
        head_sha = _require_text("proof head_sha", payload.get("head_sha"))
        fingerprint = _require_text(
            "proof checkpoint_fingerprint", payload.get("checkpoint_fingerprint")
        )
    except CheckpointError as exc:
        raise FinalizationBlocked(f"invalid finalization proof: {exc}") from exc
    return FinalizationProof(
        version=FINALIZATION_PROOF_VERSION,
        issue=issue,
        branch=branch,
        head_sha=head_sha,
        checkpoint_fingerprint=fingerprint,
    )


def assert_finalization_proof(
    checkpoint: Checkpoint,
    proof: FinalizationProof | None,
    *,
    expected_issue: str | None,
    expected_branch: str | None,
    expected_head_sha: str | None,
) -> None:
    """Fail closed unless closure has current proof from the owned guard invocation."""

    if proof is None:
        raise FinalizationBlocked(
            "guard invocation proof is required; authorize_finalization must run before closure"
        )

    issue, branch, head_sha = _assert_owning_checkpoint(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    assert_finalizable(checkpoint)

    if proof.version != FINALIZATION_PROOF_VERSION:
        raise FinalizationBlocked("stale finalization proof: unsupported proof version")
    if (proof.issue, proof.branch, proof.head_sha) != (issue, branch, head_sha):
        raise FinalizationBlocked(
            "stale finalization proof: proof owner does not match current owning checkpoint"
        )
    if proof.checkpoint_fingerprint != _checkpoint_fingerprint(checkpoint):
        raise FinalizationBlocked(
            "stale finalization proof: checkpoint changed after guard invocation"
        )


def assert_turn_exitable(
    checkpoint: Checkpoint,
    *,
    expected_master_issue: str | None = None,
) -> None:
    """Reject ending an assistant turn while autonomous work remains executable."""

    expected_master = _normalize_optional_text(expected_master_issue)
    if expected_master is not None and checkpoint.master_issue != expected_master:
        raise TurnExitBlocked(
            "turn exit blocked: Master-chain handoff evidence is missing or stale; "
            f"expected_master_issue={expected_master!r}; "
            f"checkpoint_master_issue={checkpoint.master_issue!r}"
        )

    if checkpoint.state in TURN_EXIT_BLOCKING_STATES:
        raise TurnExitBlocked(
            f"turn exit blocked for checkpoint {checkpoint.state.value}; "
            f"next_action={checkpoint.next_action!r}"
        )

    if (
        checkpoint.is_terminal
        and checkpoint.chain_state is ChainContinuationState.NEXT_CHILD_EXECUTABLE
    ):
        raise TurnExitBlocked(
            "turn exit blocked: child checkpoint is terminal but Master chain remains "
            f"executable; master_issue={checkpoint.master_issue!r}; "
            f"next_issue={checkpoint.next_issue!r}; "
            f"next_action={checkpoint.chain_next_action!r}"
        )



def _checkpoint_digest(path: Path) -> str:
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint file not found: {path}") from exc
    except OSError as exc:
        raise CheckpointError(f"cannot read checkpoint file: {path}") from exc
    return hashlib.sha256(data).hexdigest()


def _assert_checkpoint_owner(
    checkpoint: Checkpoint,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
) -> None:
    expected = (
        _require_text("expected_issue", expected_issue),
        _require_text("expected_branch", expected_branch),
        _require_text("expected_head_sha", expected_head_sha),
    )
    actual = (checkpoint.issue, checkpoint.branch, checkpoint.head_sha)
    if actual != expected:
        raise CheckpointError(
            "checkpoint owner mismatch: "
            f"expected issue={expected[0]!r} branch={expected[1]!r} head_sha={expected[2]!r}; "
            f"got issue={actual[0]!r} branch={actual[1]!r} head_sha={actual[2]!r}"
        )


def assert_checkpoint_owner(
    checkpoint: Checkpoint,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
) -> None:
    """Public exact-owner guard for non-mutating resume/wake entrypoints."""

    _assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )


def _turn_exit_proof_payload(
    checkpoint: Checkpoint,
    *,
    checkpoint_digest: str,
) -> dict[str, object]:
    return {
        "version": TURN_EXIT_PROOF_VERSION,
        "issue": checkpoint.issue,
        "branch": checkpoint.branch,
        "head_sha": checkpoint.head_sha,
        "master_issue": checkpoint.master_issue,
        "checkpoint_digest": checkpoint_digest,
        "guard": "assert_turn_exitable",
    }


def assert_turn_exitable_path(
    path: Path,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
    receipt_path: Path,
    expected_master_issue: str | None = None,
) -> Checkpoint:
    """Load the owning checkpoint, invoke the canonical guard, and mint proof.

    The proof is written only after ``assert_turn_exitable`` returns successfully.
    """

    path = Path(path)
    receipt_path = Path(receipt_path)
    checkpoint = load_checkpoint(path)
    _assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    assert_turn_exitable(
        checkpoint,
        expected_master_issue=expected_master_issue,
    )
    digest = _checkpoint_digest(path)
    proof = json.dumps(
        _turn_exit_proof_payload(checkpoint, checkpoint_digest=digest),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _atomic_write_text(receipt_path, proof)
    return checkpoint


def assert_turn_exit_permitted(
    checkpoint_path: Path,
    receipt_path: Path,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
    expected_master_issue: str | None = None,
) -> Checkpoint:
    """Verify current owning checkpoint has current proof from actual guard invocation."""

    checkpoint_path = Path(checkpoint_path)
    receipt_path = Path(receipt_path)
    checkpoint = load_checkpoint(checkpoint_path)
    _assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    assert_turn_exitable(
        checkpoint,
        expected_master_issue=expected_master_issue,
    )

    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TurnExitBlocked(f"guard invocation proof missing: {receipt_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TurnExitBlocked(f"guard invocation proof invalid: {receipt_path}") from exc

    if not isinstance(payload, dict):
        raise TurnExitBlocked("guard invocation proof invalid: payload must be an object")
    if payload.get("version") != TURN_EXIT_PROOF_VERSION:
        raise TurnExitBlocked("guard invocation proof invalid: unsupported version")
    if payload.get("guard") != "assert_turn_exitable":
        raise TurnExitBlocked("guard invocation proof invalid: canonical guard identity mismatch")

    owner = (payload.get("issue"), payload.get("branch"), payload.get("head_sha"))
    expected_owner = (checkpoint.issue, checkpoint.branch, checkpoint.head_sha)
    if owner != expected_owner:
        raise TurnExitBlocked("guard invocation proof stale: owner mismatch")
    if payload.get("master_issue") != checkpoint.master_issue:
        raise TurnExitBlocked("guard invocation proof stale: Master-chain owner mismatch")

    current_digest = _checkpoint_digest(checkpoint_path)
    if payload.get("checkpoint_digest") != current_digest:
        raise TurnExitBlocked("guard invocation proof stale: checkpoint digest mismatch")

    return checkpoint

def _format_checkpoint(checkpoint: Checkpoint) -> str:
    return json.dumps(_to_payload(checkpoint), ensure_ascii=False, indent=2, sort_keys=True)


def _add_owner_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", required=True, dest="expected_issue")
    parser.add_argument("--branch", required=True, dest="expected_branch")
    parser.add_argument("--head-sha", required=True, dest="expected_head_sha")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executable continuity checkpoint guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show = subparsers.add_parser("show", help="validate and print a checkpoint")
    show.add_argument("path", type=Path)

    finalizable = subparsers.add_parser(
        "assert-finalizable",
        help="state-only check: exit nonzero unless checkpoint is terminal",
    )
    finalizable.add_argument("path", type=Path)

    authorize = subparsers.add_parser(
        "authorize-finalization",
        help="validate exact owning checkpoint and emit machine closure proof",
    )
    authorize.add_argument("path", type=Path)
    _add_owner_arguments(authorize)
    authorize.add_argument("--proof-out", required=True, type=Path)

    verify = subparsers.add_parser(
        "verify-finalization-proof",
        help="fail closed unless current checkpoint has a valid guard invocation proof",
    )
    verify.add_argument("path", type=Path)
    verify.add_argument("proof_path", type=Path)
    _add_owner_arguments(verify)

    turn_exitable = subparsers.add_parser(
        "assert-turn-exitable",
        help="exit nonzero while autonomous non-terminal work must continue in this turn",
    )
    turn_exitable.add_argument("path", type=Path)
    turn_exitable.add_argument(
        "--master-issue",
        dest="expected_master_issue",
        help="expected Master/work-order owner for child-terminal turn-exit enforcement",
    )

    resume = subparsers.add_parser("resume", help="print the exact next action for non-terminal work")
    resume.add_argument("path", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        checkpoint = load_checkpoint(args.path)
        if args.command == "show":
            print(_format_checkpoint(checkpoint))
            return 0
        if args.command == "assert-finalizable":
            assert_finalizable(checkpoint)
            print(f"FINALIZABLE {checkpoint.state.value}")
            return 0
        if args.command == "authorize-finalization":
            proof = authorize_finalization(
                checkpoint,
                expected_issue=args.expected_issue,
                expected_branch=args.expected_branch,
                expected_head_sha=args.expected_head_sha,
            )
            save_finalization_proof(args.proof_out, proof)
            print(
                "FINALIZATION_GUARD_PASS "
                f"issue={proof.issue} branch={proof.branch} head_sha={proof.head_sha} "
                f"proof={args.proof_out}"
            )
            return 0
        if args.command == "verify-finalization-proof":
            proof = load_finalization_proof(args.proof_path)
            assert_finalization_proof(
                checkpoint,
                proof,
                expected_issue=args.expected_issue,
                expected_branch=args.expected_branch,
                expected_head_sha=args.expected_head_sha,
            )
            print(
                "FINALIZATION_PROOF_VALID "
                f"issue={proof.issue} branch={proof.branch} head_sha={proof.head_sha}"
            )
            return 0
        if args.command == "assert-turn-exitable":
            assert_turn_exitable(
                checkpoint,
                expected_master_issue=args.expected_master_issue,
            )
            print(f"TURN_EXITABLE {checkpoint.state.value}")
            return 0
        if args.command == "resume":
            if checkpoint.is_terminal:
                if (
                    checkpoint.chain_state
                    is ChainContinuationState.NEXT_CHILD_EXECUTABLE
                ):
                    print(checkpoint.chain_next_action)
                    return 0
                raise CheckpointError(
                    f"terminal checkpoint {checkpoint.state.value} has no next action to resume"
                )
            print(checkpoint.next_action)
            return 0
        raise CheckpointError(f"unsupported command: {args.command}")
    except TurnExitBlocked as exc:
        print(f"TURN_EXIT_GUARD_ERROR: {exc}")
        return 2
    except FinalizationBlocked as exc:
        print(f"FINALIZATION_GUARD_ERROR: {exc}")
        return 2
    except CheckpointError as exc:
        print(f"CONTINUITY_GUARD_ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
