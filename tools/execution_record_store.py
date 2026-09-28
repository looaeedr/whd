"""Canonical record-only store for WHD Flow v2 P1.

P1 owns only ``.dispatch/execution/issue-<N>.json``.  The derived
``ready-index.json`` cache belongs to Flow v2 P3 and is intentionally absent
from this module so execution-state authority cannot be duplicated early.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

from tools.execution_record import (
    ExecutionRecord,
    ExecutionRecordError,
    execution_record_fingerprint,
    execution_record_from_payload,
    execution_record_to_payload,
)

EXECUTION_DIR = Path(".dispatch/execution")
_ISSUE_FILE_RE = re.compile(r"^issue-([1-9][0-9]*)\.json$")


class ExecutionStoreError(RuntimeError):
    """Raised when canonical execution-store identity or CAS validation fails."""


class ExecutionStoreConflict(ExecutionStoreError):
    """Raised when an optimistic store write observes stale identity."""


def execution_record_relative_path(issue: int) -> Path:
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionStoreError("issue must be a positive integer")
    return EXECUTION_DIR / f"issue-{issue}.json"


def _rooted(root: Path | str, relative: Path) -> Path:
    return Path(root) / relative


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def load_record_file(path: Path | str) -> ExecutionRecord:
    file_path = Path(path)
    match = _ISSUE_FILE_RE.fullmatch(file_path.name)
    if match is None:
        raise ExecutionStoreError(
            f"non-canonical execution record filename: {file_path.name}"
        )
    issue_from_name = int(match.group(1))
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        record = execution_record_from_payload(payload)
    except (OSError, json.JSONDecodeError, ExecutionRecordError) as exc:
        raise ExecutionStoreError(
            f"cannot load execution record {file_path}: {exc}"
        ) from exc
    if record.issue != issue_from_name:
        raise ExecutionStoreError(
            "execution record filename/payload issue mismatch: "
            f"file={issue_from_name} payload={record.issue}"
        )
    return record


def load_execution_records(root: Path | str) -> tuple[ExecutionRecord, ...]:
    directory = _rooted(root, EXECUTION_DIR)
    if not directory.exists():
        return ()
    records = [
        load_record_file(path)
        for path in sorted(directory.glob("issue-*.json"), key=lambda p: p.name)
    ]
    issues = [record.issue for record in records]
    if len(issues) != len(set(issues)):
        raise ExecutionStoreError("duplicate issue identities in execution store")
    return tuple(sorted(records, key=lambda record: record.issue))


def write_execution_record_atomic(
    root: Path | str,
    record: ExecutionRecord,
    *,
    expected_fingerprint: str | None,
) -> str:
    """Create/update one record with exact canonical-fingerprint CAS."""
    if not isinstance(record, ExecutionRecord):
        raise ExecutionStoreError("record must be an ExecutionRecord")
    path = _rooted(root, execution_record_relative_path(record.issue))
    if path.exists():
        current = load_record_file(path)
        current_fp = execution_record_fingerprint(current)
        if expected_fingerprint is None:
            raise ExecutionStoreConflict(
                "record already exists; create-only write rejected"
            )
        if current_fp != expected_fingerprint:
            raise ExecutionStoreConflict(
                "record fingerprint drift: "
                f"expected={expected_fingerprint} observed={current_fp}"
            )
    elif expected_fingerprint is not None:
        raise ExecutionStoreConflict(
            "record missing for expected-fingerprint update"
        )

    _write_json_atomic(path, execution_record_to_payload(record))
    readback = load_record_file(path)
    if readback != record:
        raise ExecutionStoreError("post-write execution record readback mismatch")
    return execution_record_fingerprint(readback)
