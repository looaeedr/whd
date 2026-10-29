# -*- coding: utf-8 -*-
"""#2380 W-06 PRIVATE durable job identity and immutable result readback.

Not the public Worker, path lock, multi-file commit journal or crash recovery.
An unfinished job can *never* be retried as a new manufacturing operation.
Only a verified, completed local result can be replayed. The installation
ledger root and output paths must come from trusted Worker custody, not wire.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from integration_cli.prepare_evidence import (
    PrepareEvidenceError, _pure_json, _snapshot_bytes,
)
from integration_cli.request_canonical import require_matching_wire_request_digest

_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_DB_FILENAME = "job_identity.sqlite3"


@dataclass(frozen=True)
class JobClaim:
    state: str  # "new" or "committed"; no automatic uncertain retry
    result: dict[str, Any] | None = None


def _identity(request: Mapping[str, Any]) -> tuple[str, str, str, str]:
    digest = require_matching_wire_request_digest(request)
    client, job, operation = (
        request.get("client_installation_id"),
        request.get("job_id"),
        request.get("operation"),
    )
    if (not isinstance(client, str) or not _JOB_ID.fullmatch(client)
            or not isinstance(job, str) or not _JOB_ID.fullmatch(job)
            or operation not in ("prepare", "export")):
        raise PrepareEvidenceError("WHD_JOB_ID_INVALID", "invalid worker job identity")
    return client, job, operation, digest


def _json(value: Any) -> str:
    return json.dumps(
        _pure_json(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def _file_proof(path: Path) -> dict[str, Any]:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "committed file is missing or unsafe")
    try:
        sha, size = _snapshot_bytes(path)
        metadata = path.stat()
    except (OSError, ValueError, PrepareEvidenceError) as exc:
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "committed file cannot be verified") from exc
    return {
        "path": str(path.resolve(strict=True)),
        "sha256": sha,
        "size": size,
        "mtime_ns": metadata.st_mtime_ns,
    }


def _file_proofs(files: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    if not isinstance(files, Mapping) or any(
        not isinstance(k, str) or not _JOB_ID.fullmatch(k) for k in files
    ):
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "invalid trusted artifact mapping")
    paths = [str(p) for p in files.values()]
    if len(set(paths)) != len(paths):
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "multiple artifacts share a path")
    return {key: _file_proof(path) for key, path in sorted(files.items())}


class DurableJobIdentityLedger:
    """Private same-job replay ledger, isolated from unfinished W-06 output journal.

    SQLite BEGIN IMMEDIATE serializes same identity claims across processes.
    This intentionally does NOT serialize *different* jobs that target the
    same output directory; W-06 path locks and recovery are still mandatory.
    """

    def __init__(self, trusted_store_root: Path):
        if (not isinstance(trusted_store_root, Path)
                or trusted_store_root.is_symlink()
                or not trusted_store_root.is_dir()):
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "trusted installation store unavailable")
        self._root = trusted_store_root
        self._db = trusted_store_root / _DB_FILENAME
        with closing(self._connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('started','committed')),
                    result_json TEXT,
                    result_sha256 TEXT,
                    artifact_json TEXT,
                    PRIMARY KEY (client_id, job_id, operation)
                )
            """)

    def _connect(self):
        if (self._root.is_symlink() or not self._root.is_dir()
                or self._db.is_symlink()):
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "untrusted job store path")
        try:
            conn = sqlite3.connect(str(self._db), isolation_level=None, timeout=5.0)
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = FULL")
            return conn
        except sqlite3.Error as exc:
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "job store cannot be opened") from exc

    def claim(self, request: Mapping[str, Any]) -> JobClaim:
        """First claim starts once; incomplete replay never authorizes a rerun."""
        client, job, op, digest = _identity(request)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,state,result_json,result_sha256,artifact_json
                   FROM jobs WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None:
                conn.execute(
                    """INSERT INTO jobs(client_id,job_id,operation,request_digest,state)
                       VALUES (?,?,?,?,'started')""",
                    (client, job, op, digest),
                )
                conn.commit()
                return JobClaim("new")
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot reserve job identity") from exc
        finally:
            conn.close()
        recorded_digest, state, payload, payload_hash, proof_json = row
        if not hmac.compare_digest(recorded_digest, digest):
            raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "same job identity has different semantic request")
        if state != "committed":
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "previous job has no durable completion")
        if (not payload or not payload_hash or not proof_json
                or not hmac.compare_digest(hashlib.sha256(payload.encode("utf-8")).hexdigest(), payload_hash)):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "persisted result is missing or invalid")
        try:
            proofs = json.loads(proof_json)
            result = json.loads(payload)
            if not isinstance(proofs, dict) or not isinstance(result, dict):
                raise ValueError("invalid record")
            for proof in proofs.values():
                actual = _file_proof(Path(proof["path"]))
                if actual != proof:
                    raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "committed artifact changed")
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "persisted manifest cannot be trusted") from exc
        return JobClaim("committed", result)

    def complete(
        self,
        request: Mapping[str, Any],
        trusted_result: Mapping[str, Any],
        *,
        trusted_artifacts: Mapping[str, Path],
    ) -> None:
        """Only the trusted Worker may call after verified stage/commit.

        A persisted result is accepted for later replay only if export has
        actual file attestations; this seam does not commit any output itself.
        """
        client, job, op, digest = _identity(request)
        if (not isinstance(trusted_result, Mapping)
                or trusted_result.get("status") != "success"
                or trusted_result.get("operation") != op
                or trusted_result.get("job_id") != job
                or trusted_result.get("client_installation_id") != client):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "unverified completion receipt")
        proofs = _file_proofs(trusted_artifacts)
        if op == "export" and not proofs:
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "export has no verified physical artifacts")
        payload = _json(trusted_result)
        encoded_proofs = _json(proofs)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None:
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "job not reserved")
            if not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "completion digest changed")
            if row[1] != "started":
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "job already completed")
            conn.execute(
                """UPDATE jobs SET state='committed',result_json=?,result_sha256=?,artifact_json=?
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (payload, hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                 encoded_proofs, client, job, op),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot persist completed identity") from exc
        finally:
            conn.close()
