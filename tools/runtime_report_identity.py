"""Machine validator/formatter for user-visible WHD runtime report identity.

This module owns presentation provenance only.  It does not grant execution
permission, acquire leases, change ownership, or mutate Flow v2 state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re


from tools.execution_invocation_exit import InvocationExitError, validate_host_exit_proof
from tools.execution_record import ExecutionRecord, execution_record_from_payload

INTERACTIVE_HANDLERS = frozenset({"工作0", "工作1", "工作2", "工作3"})
SCHEDULER_HANDLERS = frozenset({"排程A", "排程B"})
RUNTIME_KINDS = frozenset({"INTERACTIVE", "SCHEDULER"})
EXPLICIT_UNBOUND = frozenset({"NONE", "UNBOUND"})
REPORT_EVENTS = frozenset({"PROGRESS", "CHECKPOINT", "TERMINAL", "EXIT", "STATUS"})


class RuntimeReportIdentityError(ValueError):
    """Raised when a user-visible report lacks exact runtime provenance."""


@dataclass(frozen=True)
class RuntimeReportIdentity:
    handler: str
    owner: str
    issue: str
    slot: str
    invocation_identity: str
    runtime_kind: str


def _text(field: str, value: object) -> str:
    result = str(value if value is not None else "").strip()
    if not result:
        raise RuntimeReportIdentityError(f"{field} must be nonblank")
    return result


def _normalize_issue(value: object) -> str:
    if isinstance(value, bool):
        raise RuntimeReportIdentityError("issue must be a positive integer or NONE/UNBOUND")
    if isinstance(value, int):
        if value <= 0:
            raise RuntimeReportIdentityError("issue must be positive")
        return str(value)
    text = _text("issue", value)
    if text.startswith("#"):
        text = text[1:]
    if text in EXPLICIT_UNBOUND:
        return text
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise RuntimeReportIdentityError(
            "issue must be a positive integer or explicit NONE/UNBOUND"
        )
    return text


def _normalize_slot(value: object) -> str:
    text = _text("slot", value)
    if text in EXPLICIT_UNBOUND:
        return text
    if not re.fullmatch(r"worker\.slot\.[0-3]", text):
        raise RuntimeReportIdentityError(
            "slot must be worker.slot.0..3 or explicit NONE/UNBOUND"
        )
    return text


def build_runtime_report_identity(
    *,
    handler: object,
    owner: object,
    issue: object,
    slot: object,
    invocation_identity: object,
    runtime_kind: object,
) -> RuntimeReportIdentity:
    """Validate exact identity required by visible progress/checkpoint/exit reports.

    Values must come from the fresh ExecutionRecord/runtime observation projection.
    This function deliberately cannot infer or guess missing fields.
    """

    kind = _text("runtime_kind", runtime_kind).upper()
    if kind not in RUNTIME_KINDS:
        raise RuntimeReportIdentityError(
            f"runtime_kind must be one of {sorted(RUNTIME_KINDS)}"
        )
    report_handler = _text("handler", handler)
    report_owner = _text("owner", owner)
    report_issue = _normalize_issue(issue)
    report_slot = _normalize_slot(slot)
    invocation = _text("invocation_identity", invocation_identity)
    if invocation in {"NONE", "UNBOUND", "UNAVAILABLE"}:
        raise RuntimeReportIdentityError(
            "invocation_identity must be exact; NONE/UNBOUND/UNAVAILABLE are invalid"
        )

    if kind == "INTERACTIVE":
        if report_handler not in INTERACTIVE_HANDLERS:
            raise RuntimeReportIdentityError(
                "interactive handler must be 工作0/工作1/工作2/工作3"
            )
        expected_slot = f"worker.slot.{report_handler[-1]}"
        if report_slot not in {expected_slot, "UNBOUND"}:
            raise RuntimeReportIdentityError(
                f"interactive handler {report_handler} must bind slot {expected_slot}"
            )
    else:
        if report_handler not in SCHEDULER_HANDLERS:
            raise RuntimeReportIdentityError(
                "scheduler handler must be 排程A or 排程B"
            )

    return RuntimeReportIdentity(
        handler=report_handler,
        owner=report_owner,
        issue=report_issue,
        slot=report_slot,
        invocation_identity=invocation,
        runtime_kind=kind,
    )


def assert_runtime_report_event_allowed(
    event: object,
    identity: RuntimeReportIdentity,
    *,
    record: ExecutionRecord | None = None,
    exit_proof: object | None = None,
    now: object | None = None,
) -> bool:
    """Enforce host-return authority at the sole runtime-report machine seam."""

    if not isinstance(identity, RuntimeReportIdentity):
        raise RuntimeReportIdentityError("identity must be RuntimeReportIdentity")
    report_event = _text("event", event).upper()
    if report_event not in REPORT_EVENTS:
        raise RuntimeReportIdentityError(
            f"event must be one of {sorted(REPORT_EVENTS)}"
        )
    if report_event not in {"TERMINAL", "EXIT"}:
        return True

    if not isinstance(record, ExecutionRecord):
        raise RuntimeReportIdentityError(
            f"{report_event} report requires fresh ExecutionRecord"
        )
    if identity.issue in EXPLICIT_UNBOUND or int(identity.issue) != record.issue:
        raise RuntimeReportIdentityError(
            f"{report_event} report issue does not match ExecutionRecord"
        )
    if identity.owner != record.owner_id:
        raise RuntimeReportIdentityError(
            f"{report_event} report owner does not match ExecutionRecord"
        )
    expected_slot = record.slot_id or "NONE"
    if identity.slot != expected_slot:
        raise RuntimeReportIdentityError(
            f"{report_event} report slot does not match ExecutionRecord"
        )
    current_now = _text("now", now)
    if exit_proof is None:
        raise RuntimeReportIdentityError(
            f"{report_event} host-exit proof rejected: missing proof"
        )
    try:
        validated = validate_host_exit_proof(
            exit_proof,
            record,
            invocation_identity=identity.invocation_identity,
            now=current_now,
        )
    except InvocationExitError as exc:
        raise RuntimeReportIdentityError(
            f"{report_event} host-exit proof rejected: {exc}"
        ) from exc
    if report_event == "TERMINAL" and validated.get("decision") != "TASK_TERMINAL":
        raise RuntimeReportIdentityError(
            "TERMINAL report requires TASK_TERMINAL host-exit proof"
        )
    return True


def format_runtime_report_prefix(
    identity: RuntimeReportIdentity,
    *,
    event: object,
    execution_record: ExecutionRecord | None = None,
    host_exit_proof: object | None = None,
    now: object | None = None,
) -> str:
    """Render CURRENT identity only after event-specific exit authorization."""

    if not isinstance(identity, RuntimeReportIdentity):
        raise RuntimeReportIdentityError("identity must be RuntimeReportIdentity")
    assert_runtime_report_event_allowed(
        event,
        identity,
        record=execution_record,
        exit_proof=host_exit_proof,
        now=now,
    )
    return (
        f"【處理者：{identity.handler}｜owner={identity.owner}｜工單：#{identity.issue}"
        f"｜slot={identity.slot}｜invocation_identity={identity.invocation_identity}】"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and render the mandatory WHD user-visible runtime identity prefix"
    )
    parser.add_argument("--event", required=True, choices=tuple(sorted(REPORT_EVENTS)))
    parser.add_argument("--handler", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--invocation-identity", required=True)
    parser.add_argument("--runtime-kind", required=True, choices=tuple(sorted(RUNTIME_KINDS)))
    parser.add_argument("--execution-record-file")
    parser.add_argument("--host-exit-proof-file")
    parser.add_argument("--now")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        identity = build_runtime_report_identity(
            handler=args.handler,
            owner=args.owner,
            issue=args.issue,
            slot=args.slot,
            invocation_identity=args.invocation_identity,
            runtime_kind=args.runtime_kind,
        )
    except RuntimeReportIdentityError as exc:
        print(f"RUNTIME_REPORT_IDENTITY_FAIL_CLOSED: {exc}")
        return 2
    execution_record = None
    host_exit_proof = None
    if args.event in {"TERMINAL", "EXIT"}:
        if not args.execution_record_file or not args.host_exit_proof_file or not args.now:
            print(
                "RUNTIME_REPORT_IDENTITY_FAIL_CLOSED: "
                f"{args.event} requires --execution-record-file "
                "--host-exit-proof-file --now"
            )
            return 2
        try:
            execution_record = execution_record_from_payload(
                json.loads(Path(args.execution_record_file).read_text(encoding="utf-8"))
            )
            host_exit_proof = json.loads(
                Path(args.host_exit_proof_file).read_text(encoding="utf-8")
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"RUNTIME_REPORT_IDENTITY_FAIL_CLOSED: invalid exit evidence: {exc}")
            return 2
    try:
        prefix = format_runtime_report_prefix(
            identity,
            event=args.event,
            execution_record=execution_record,
            host_exit_proof=host_exit_proof,
            now=args.now,
        )
    except RuntimeReportIdentityError as exc:
        print(f"RUNTIME_REPORT_IDENTITY_FAIL_CLOSED: {exc}")
        return 2
    print(prefix)
    print(f"RUNTIME_REPORT_IDENTITY_VALID event={args.event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
