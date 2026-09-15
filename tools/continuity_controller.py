"""Executable continuity checkpoint/resume/finalization/turn-exit authority.

This module is intentionally independent from application geometry and UI code. It
exists to make long-running development/QA workflows fail closed when their durable
state is incomplete, resumable after a runtime cut, impossible to finalize while
non-terminal, and unable to end an assistant turn while autonomous work remains.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable


CHECKPOINT_VERSION = 1
_UNSET = object()


class ContinuityState(str, Enum):
    RUNNING = "RUNNING"
    WAITING_REMOTE = "WAITING_REMOTE"
    RECOVERING = "RECOVERING"
    BLOCKED = "BLOCKED"
    TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


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
    """Raised when closure/finalization is attempted before a terminal state."""


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
    evidence: tuple[str, ...] = ()

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
        _validate_positive_int("run_id", self.run_id)
        _validate_positive_int("job_id", self.job_id)

        if state in NONTERMINAL_STATES and next_action is None:
            raise CheckpointError(f"next_action is required for non-terminal state {state.value}")
        if state in TERMINAL_STATES and next_action is not None:
            raise CheckpointError(f"next_action must be None for terminal state {state.value}")
        if state is ContinuityState.WAITING_REMOTE:
            if self.run_id is None:
                raise CheckpointError("run_id is required for WAITING_REMOTE")
            _require_text("head_sha", head_sha)

        normalized_evidence: list[str] = []
        for index, item in enumerate(self.evidence):
            normalized_evidence.append(_require_text(f"evidence[{index}]", item))

        object.__setattr__(self, "issue", issue)
        object.__setattr__(self, "branch", branch)
        object.__setattr__(self, "head_sha", head_sha)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "next_action", next_action)
        object.__setattr__(self, "log_cursor", log_cursor)
        object.__setattr__(self, "evidence", tuple(normalized_evidence))

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


def _to_payload(checkpoint: Checkpoint) -> dict[str, object]:
    data = asdict(checkpoint)
    data["state"] = checkpoint.state.value
    data["evidence"] = list(checkpoint.evidence)
    return {"version": CHECKPOINT_VERSION, **data}


def save_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    """Persist checkpoint atomically in the target directory.

    The temporary file is flushed and fsynced before os.replace so a runtime cut cannot
    leave a half-written JSON file at the authoritative path.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_to_payload(checkpoint), ensure_ascii=False, indent=2, sort_keys=True)

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


def load_checkpoint(path: Path) -> Checkpoint:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"invalid checkpoint JSON: {path}") from exc

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
        "evidence",
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
            evidence=tuple(evidence),
        )
    except KeyError as exc:
        raise CheckpointError(f"missing checkpoint field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise CheckpointError("checkpoint contains invalid field values") from exc


def transition_checkpoint(
    checkpoint: Checkpoint,
    *,
    state: ContinuityState,
    next_action: str | None = None,
    run_id: int | None | object = _UNSET,
    job_id: int | None | object = _UNSET,
    head_sha: str | None | object = _UNSET,
    log_cursor: str | None | object = _UNSET,
    evidence: tuple[str, ...] | None = None,
) -> Checkpoint:
    """Return a validated next checkpoint without reusing stale remote ownership.

    Omitted remote fields are distinct from explicit ``None``. While remaining inside
    one WAITING_REMOTE lock, omitted owner/cursor fields inherit that same lock. When
    entering WAITING_REMOTE from any other state, ``run_id`` must be supplied explicitly
    and stale job/cursor data is cleared unless the caller supplies replacements.
    Other transitions preserve prior remote identity as provenance when fields are omitted.
    """

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

    merged_evidence = checkpoint.evidence + (() if evidence is None else tuple(evidence))
    return replace(
        checkpoint,
        state=state,
        next_action=next_action,
        run_id=next_run_id,
        job_id=next_job_id,
        head_sha=next_head_sha,
        log_cursor=next_log_cursor,
        evidence=merged_evidence,
    )


def assert_finalizable(checkpoint: Checkpoint) -> None:
    if not checkpoint.is_terminal:
        raise FinalizationBlocked(
            f"non-terminal checkpoint {checkpoint.state.value} cannot be finalized; "
            f"next_action={checkpoint.next_action!r}"
        )


def assert_turn_exitable(checkpoint: Checkpoint) -> None:
    """Reject ending an assistant turn while autonomous work remains executable.

    BLOCKED is deliberately turn-exitable because it represents a genuine external
    authority/capability wait, but it remains non-finalizable. Terminal states are both
    turn-exitable and finalizable. RUNNING, WAITING_REMOTE, and RECOVERING must keep the
    current execution loop moving to ``next_action`` instead of handing scheduling back
    to the user.
    """

    if checkpoint.state in TURN_EXIT_BLOCKING_STATES:
        raise TurnExitBlocked(
            f"turn exit blocked for checkpoint {checkpoint.state.value}; "
            f"next_action={checkpoint.next_action!r}"
        )


def _format_checkpoint(checkpoint: Checkpoint) -> str:
    return json.dumps(_to_payload(checkpoint), ensure_ascii=False, indent=2, sort_keys=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executable continuity checkpoint guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show = subparsers.add_parser("show", help="validate and print a checkpoint")
    show.add_argument("path", type=Path)

    finalizable = subparsers.add_parser(
        "assert-finalizable", help="exit nonzero unless checkpoint is terminal"
    )
    finalizable.add_argument("path", type=Path)

    turn_exitable = subparsers.add_parser(
        "assert-turn-exitable",
        help="exit nonzero while autonomous non-terminal work must continue in this turn",
    )
    turn_exitable.add_argument("path", type=Path)

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
        if args.command == "assert-turn-exitable":
            assert_turn_exitable(checkpoint)
            print(f"TURN_EXITABLE {checkpoint.state.value}")
            return 0
        if args.command == "resume":
            if checkpoint.is_terminal:
                raise CheckpointError(
                    f"terminal checkpoint {checkpoint.state.value} has no next action to resume"
                )
            print(checkpoint.next_action)
            return 0
        raise CheckpointError(f"unsupported command: {args.command}")
    except TurnExitBlocked as exc:
        print(f"TURN_EXIT_GUARD_ERROR: {exc}")
        return 2
    except CheckpointError as exc:
        print(f"CONTINUITY_GUARD_ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
