"""Issue-bound PR admission against the native Flow v2 ExecutionRecord.

The coord/execution-v2 record is the only delivery authority. PR text, comments,
Phase6 receipts, and checked-in preflight files cannot claim a work slot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Mapping

RECORD_SCHEMA = "WHD_EXECUTION_RECORD_V2"
ISSUE_BRANCH = re.compile(r"^work/issue-(\d+)(?:-|$)", re.IGNORECASE)
ISSUE_CLOSING = re.compile(
    r"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+"
    r"(?:(?:[\w.-]+/[\w.-]+))?#(\d+)\b", re.IGNORECASE
)

class DeliveryEntryError(ValueError):
    """The issue-bound delivery PR has no valid native admission."""


def _field(value: object) -> str:
    return str(value or "").strip()


def issue_from_pr(pr: Mapping[str, object]) -> int | None:
    head = pr.get("head")
    if not isinstance(head, Mapping):
        raise DeliveryEntryError("PR_HEAD_MISSING")
    branch = _field(head.get("ref"))
    branch_match = ISSUE_BRANCH.fullmatch(branch) or ISSUE_BRANCH.match(branch)
    candidates = {int(branch_match.group(1))} if branch_match else set()
    for field in ("body", "title"):
        candidates.update(int(n) for n in ISSUE_CLOSING.findall(_field(pr.get(field))))
    if len(candidates) > 1:
        raise DeliveryEntryError("ISSUE_BOUND_PR_AMBIGUOUS_ISSUES")
    return next(iter(candidates)) if candidates else None


def _parse_utc(value: object, label: str) -> datetime:
    try:
        dt = datetime.fromisoformat(_field(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DeliveryEntryError(f"{label}_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise DeliveryEntryError(f"{label}_NOT_TIMEZONE_AWARE")
    return dt.astimezone(timezone.utc)


def validate_pr_entry(
    pr: Mapping[str, object],
    record: Mapping[str, object] | None,
    *,
    repository: str,
    now: datetime | None = None,
) -> dict[str, object]:
    issue = issue_from_pr(pr)
    if issue is None:
        return {"status": "SKIPPED", "reason": "NON_ISSUE_BOUND_PR"}
    if not isinstance(record, Mapping):
        raise DeliveryEntryError(f"NATIVE_EXECUTION_RECORD_REQUIRED issue={issue}")
    if record.get("schema") != RECORD_SCHEMA or record.get("issue") != issue:
        raise DeliveryEntryError("NATIVE_EXECUTION_RECORD_IDENTITY_MISMATCH")
    if record.get("state") not in {"ACTIVE", "VERIFYING", "INTEGRATING"}:
        raise DeliveryEntryError("NATIVE_ACQUIRE_REQUIRED")
    owner = _field(record.get("owner_id"))
    lane = _field(record.get("lane_id"))
    kind = _field(record.get("owner_kind"))
    if not owner or owner == "NONE" or not lane or not kind or kind == "NONE":
        raise DeliveryEntryError("NATIVE_OWNER_MISSING")
    if kind == "SCHEDULER" and owner != lane:
        raise DeliveryEntryError("NATIVE_OWNER_LANE_MISMATCH")
    if not _field(record.get("slot_id")):
        raise DeliveryEntryError("NATIVE_SLOT_MISSING")
    lease = record.get("lease")
    if not isinstance(lease, Mapping) or not _field(lease.get("token")):
        raise DeliveryEntryError("NATIVE_LEASE_MISSING")
    invocation = _field(lease.get("invocation_identity"))
    if not invocation:
        raise DeliveryEntryError("NATIVE_INVOCATION_MISSING")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise DeliveryEntryError("VALIDATION_CLOCK_NOT_TIMEZONE_AWARE")
    if _parse_utc(lease.get("expires_at"), "NATIVE_LEASE_EXPIRY") <= clock:
        raise DeliveryEntryError("NATIVE_LEASE_EXPIRED")
    head = pr["head"]
    base = pr.get("base")
    if not isinstance(base, Mapping):
        raise DeliveryEntryError("PR_BASE_MISSING")
    head_repo = head.get("repo")
    if not isinstance(head_repo, Mapping) or _field(head_repo.get("full_name")) != repository:
        raise DeliveryEntryError("PR_HEAD_REPOSITORY_MISMATCH")
    if _field(record.get("work_branch")) != _field(head.get("ref")):
        raise DeliveryEntryError("NATIVE_WORK_BRANCH_MISMATCH")
    if _field(record.get("head_sha")) != _field(head.get("sha")):
        raise DeliveryEntryError("NATIVE_HEAD_SHA_MISMATCH")
    if _field(record.get("target_branch")) != _field(base.get("ref")):
        raise DeliveryEntryError("NATIVE_TARGET_BRANCH_MISMATCH")
    scope = record.get("mutation_scope")
    if not isinstance(scope, Mapping) or scope.get("reservation_state") != "ACTIVE":
        raise DeliveryEntryError("NATIVE_DELIVERY_RESERVATION_REQUIRED")
    if _field(scope.get("target_branch")) != _field(record.get("target_branch")):
        raise DeliveryEntryError("NATIVE_RESERVATION_TARGET_MISMATCH")
    transaction = record.get("transaction")
    if not isinstance(transaction, Mapping) or transaction.get("status") != "RECONCILED":
        raise DeliveryEntryError("NATIVE_TRANSACTION_RECEIPT_REQUIRED")
    if _field(transaction.get("invocation_identity")) != invocation:
        raise DeliveryEntryError("NATIVE_TRANSACTION_INVOCATION_MISMATCH")
    return {"status": "GREEN", "issue": issue, "reason": "NATIVE_ISSUE_BOUND_PR_ADMISSION_VALID"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--records-root", type=Path, required=True)
    parser.add_argument("--repository", default="looaeedr/whd")
    args = parser.parse_args()
    try:
        event = json.loads(args.event_file.read_text(encoding="utf-8"))
        pr = event.get("pull_request")
        if pr is None:
            print(json.dumps({"status": "SKIPPED", "reason": "NON_PR_EVENT"}))
            return 0
        issue = issue_from_pr(pr)
        path = args.records_root / f"issue-{issue}.json" if issue is not None else None
        record = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None
        output = validate_pr_entry(pr, record, repository=args.repository)
        print(json.dumps(output))
        return 0
    except (DeliveryEntryError, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
