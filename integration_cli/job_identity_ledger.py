# -*- coding: utf-8 -*-
"""#2380 W-06 PRIVATE durable job identity and immutable result readback.

Not the public Worker, full Windows path-alias gate, multi-file commit journal or crash recovery.
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
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any, Mapping, Sequence

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


def _output_directory_keys(directories: Sequence[Path]) -> tuple[str, ...]:
    """Canonicalize *trusted Worker selected* pre-existing output directories.

    Never take a directory path from untrusted CADSplit data. Local symlinks
    and non-absolute/absent directories fail closed. Windows case handling is
    delegated to the host path API; drive aliases/junctions still need Gate A.
    """
    if (not isinstance(directories, (list, tuple)) or not directories
            or len(directories) > 20):
        raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "trusted output directory list required")
    keys = []
    for directory in directories:
        if (not isinstance(directory, Path) or not directory.is_absolute()
                or not directory.is_dir()
                or directory.is_symlink()
                or any(parent.is_symlink() for parent in directory.parents)):
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "unsafe or missing output directory")
        try:
            keys.append(os.path.normcase(str(directory.resolve(strict=True))))
        except OSError as exc:
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "output path is not canonical") from exc
    if len(set(keys)) != len(keys):
        raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "duplicate or aliased batch output directory")
    return tuple(sorted(keys))


def _directory_identity(path: Path) -> tuple[int, int]:
    """Pin the actual filesystem directory, not only its reusable path text."""
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "reserved output directory vanished") from exc
    if (not stat.S_ISDIR(metadata.st_mode)
            or not isinstance(metadata.st_dev, int)
            or not isinstance(metadata.st_ino, int)
            or metadata.st_dev <= 0 or metadata.st_ino <= 0):
        raise PrepareEvidenceError(
            "WHD_JOB_RECOVERY_REQUIRED", "reserved output directory identity unverified"
        )
    return metadata.st_dev, metadata.st_ino


class DurableJobIdentityLedger:
    """Private same-job replay ledger, isolated from unfinished W-06 output journal.

    SQLite BEGIN IMMEDIATE serializes same identity and output directory
    reservations across processes. A lease survives an unfinished job/crash.
    This is not a multi-file commit journal or a complete Windows alias gate.
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS output_directory_leases (
                    directory_key TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL
                )
            """)
            # Additive fail-closed evidence table; older unfinished leases
            # without identity proofs cannot silently acquire new authority.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS output_directory_identity (
                    directory_key TEXT PRIMARY KEY,
                    device_id INTEGER NOT NULL,
                    inode_id INTEGER NOT NULL
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
        if not isinstance(recorded_digest, str):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "durable identity record is invalid")
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


    def reserve_output_directories(
        self, request: Mapping[str, Any], *, trusted_directories: Sequence[Path],
    ) -> tuple[str, ...]:
        """Acquire an all-or-none durable lease over every *batch* destination.

        Only the one live trusted Worker that created the original reservation
        may invoke this. No directory is ever created by this method. Separate
        jobs cannot hold the same directory until verified completion; a crash
        leaves the old lease in place for future W-06 recovery, not stealing.
        """
        client, job, op, digest = _identity(request)
        if op != "export":
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "only export can lease output destinations")
        keys = _output_directory_keys(trusted_directories)
        physical = {
            os.path.normcase(str(directory.resolve(strict=True))): _directory_identity(directory)
            for directory in trusted_directories
        }
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None or row[1] != "started":
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "export job is not newly reserved")
            if not isinstance(row[0], str):
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "invalid durable job record")
            if not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "export job identity changed")
            for key in keys:
                holder = conn.execute(
                    """SELECT client_id,job_id,operation,request_digest
                       FROM output_directory_leases WHERE directory_key=?""",
                    (key,),
                ).fetchone()
                if holder is not None and holder != (client, job, op, digest):
                    raise PrepareEvidenceError(
                        "WHD_OUTPUT_PATH_LOCKED", "a different unfinished job owns this destination"
                    )
            for key in keys:
                persisted = conn.execute(
                    """SELECT device_id,inode_id FROM output_directory_identity
                       WHERE directory_key=?""", (key,),
                ).fetchone()
                already = conn.execute(
                    """SELECT 1 FROM output_directory_leases WHERE directory_key=?""",
                    (key,),
                ).fetchone()
                if already and persisted != physical[key]:
                    raise PrepareEvidenceError(
                        "WHD_JOB_RECOVERY_REQUIRED", "previous output directory identity changed or is unverified"
                    )
                if not already:
                    conn.execute(
                        """INSERT INTO output_directory_leases
                           (directory_key,client_id,job_id,operation,request_digest)
                           VALUES (?,?,?,?,?)""",
                        (key, client, job, op, digest),
                    )
                    conn.execute(
                        """INSERT INTO output_directory_identity(directory_key,device_id,inode_id)
                           VALUES (?,?,?)""",
                        (key, *physical[key]),
                    )
            conn.commit()
            return keys
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "output lease transaction failed") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

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
                or trusted_result.get("client_installation_id") != client
                or trusted_result.get("request_digest") != digest):
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
            if not isinstance(row[0], str):
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "durable identity record invalid")
            if not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "completion digest changed")
            if row[1] != "started":
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "job already completed")
            if op == "export":
                leased = conn.execute(
                    """SELECT COUNT(*) FROM output_directory_leases
                       WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
                    (client, job, op, digest),
                ).fetchone()[0]
                if leased == 0:
                    raise PrepareEvidenceError(
                        "WHD_JOB_RECOVERY_REQUIRED", "export output directories were never exclusively reserved"
                    )
                reserved_keys = {
                    row[0] for row in conn.execute(
                        """SELECT directory_key FROM output_directory_leases
                           WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
                        (client, job, op, digest),
                    )
                }
                for reserved_key in reserved_keys:
                    recorded = conn.execute(
                        """SELECT device_id,inode_id FROM output_directory_identity
                           WHERE directory_key=?""", (reserved_key,),
                    ).fetchone()
                    if recorded is None or recorded != _directory_identity(Path(reserved_key)):
                        raise PrepareEvidenceError(
                            "WHD_JOB_RECOVERY_REQUIRED", "reserved output directory was replaced"
                        )
                for attested in proofs.values():
                    # Every physical file must reside directly within this
                    # job's exclusively held directory; merely locking A
                    # cannot certify a manufactured output in directory B.
                    actual_directory, = _output_directory_keys(
                        [Path(attested["path"]).parent]
                    )
                    if actual_directory not in reserved_keys:
                        raise PrepareEvidenceError(
                            "WHD_JOB_RECOVERY_REQUIRED", "attested output escaped its reserved directory"
                        )
            conn.execute(
                """UPDATE jobs SET state='committed',result_json=?,result_sha256=?,artifact_json=?
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (payload, hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                 encoded_proofs, client, job, op),
            )
            # Release the batch leases *in the same durable transaction* as
            # successful immutable result publication; never on failure.
            conn.execute(
                """DELETE FROM output_directory_identity
                   WHERE directory_key IN (
                       SELECT directory_key FROM output_directory_leases
                       WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?
                   )""",
                (client, job, op, digest),
            )
            conn.execute(
                """DELETE FROM output_directory_leases
                   WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
                (client, job, op, digest),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot persist completed identity") from exc
        finally:
            conn.close()
