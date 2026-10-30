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
_STAGE_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}[.]dxf$", re.IGNORECASE)


def _unsafe_windows_path(path: Path) -> bool:
    """Disallow UNC/device paths and junction traversal until certified on Windows."""
    if os.name != "nt":
        return False
    if str(path).startswith(("\\\\", "//")):
        return True
    try:
        return any(part.is_junction() for part in (path, *path.parents))
    except OSError:
        return True



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
    if (not isinstance(path, Path) or _unsafe_windows_path(path)
            or path.is_symlink() or not path.is_file()):
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
                or _unsafe_windows_path(directory)
                or any(parent.is_symlink() for parent in directory.parents)):
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "unsafe or missing output directory")
        try:
            keys.append(os.path.normcase(str(directory.resolve(strict=True))))
        except OSError as exc:
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "output path is not canonical") from exc
    if len(set(keys)) != len(keys):
        raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "duplicate or aliased batch output directory")
    physical = [_directory_identity(path) for path in directories]
    if len(set(physical)) != len(physical):
        raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "duplicate physical destination under different aliases")
    return tuple(sorted(keys))


def _directory_identity(path: Path) -> tuple[int, int]:
    """Pin the actual filesystem directory, not only its reusable path text."""
    if _unsafe_windows_path(path):
        raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "Windows directory alias is not certified")
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


def _staged_batch_snapshot(
    trusted_output_dir: Path, staged: Mapping[str, Path], *, overwrite: bool,
) -> dict[str, Any]:
    """Read-only source and destination bytes before any final file mutation.

    The actual W-04 renderer owns the preverified stage. This routine does
    not trust a caller-supplied wire path, output token or DXF formula. Files
    must be in a direct .whd-dxf-stage-* child of the reserved output folder,
    on the same device. No output directory is created or mutated.
    """
    if type(overwrite) is not bool or not isinstance(staged, Mapping) or not 1 <= len(staged) <= 20:
        raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "verified batch inventory required")
    output_key, = _output_directory_keys([trusted_output_dir])
    physical_ids = set()
    filenames = set()
    entries = []
    for physical, stage in sorted(staged.items()):
        if (not isinstance(physical, str)
                or not isinstance(stage, Path)
                or not _STAGE_FILE_NAME.fullmatch(f"{physical}.dxf")
                or stage.name != f"{physical}.dxf"
                or stage.is_symlink()
                or stage.parent.is_symlink()
                or not stage.parent.name.startswith(".whd-dxf-stage-")
                or stage.parent.parent != trusted_output_dir):
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "untrusted staged physical DXF path")
        if physical.casefold() in physical_ids or stage.name.casefold() in filenames:
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "duplicate physical DXF identity")
        physical_ids.add(physical.casefold())
        filenames.add(stage.name.casefold())
        try:
            stage_stat = stage.stat()
            if stage_stat.st_dev != trusted_output_dir.stat().st_dev:
                raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "DXF stage must use target filesystem")
            if stage_stat.st_nlink != 1:
                raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "staged DXF may not hardlink another file")
        except OSError as exc:
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "DXF stage is unreadable") from exc
        original = trusted_output_dir / stage.name
        if original.is_symlink():
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "existing target is a symlink")
        if original.exists() and not overwrite:
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "existing customer DXF cannot be overwritten")
        original_proof = _file_proof(original) if original.exists() else None
        stage_proof = _file_proof(stage)
        if stage_proof["path"] == str(original.resolve(strict=False)):
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "stage is already a customer output")
        entries.append({
            "physical_id": physical,
            "destination": str(original.resolve(strict=False)),
            "stage": stage_proof,
            "original": original_proof,
        })
    return {"directory_key": output_key, "overwrite": overwrite, "items": entries}


def _assert_staged_batch_snapshot_current(snapshot: Mapping[str, Any]) -> None:
    """Refuse any changed stage or original target; never restore or replace."""
    try:
        items = snapshot["items"]
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError("bad inventory")
        for item in items:
            stage = item["stage"]
            if _file_proof(Path(stage["path"])) != stage:
                raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "staged physical DXF changed")
            target = Path(item["destination"])
            if target.is_symlink():
                raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "customer target became symlink")
            original = item["original"]
            if original is None:
                if target.exists():
                    raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "new customer target appeared")
            elif _file_proof(target) != original:
                raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "customer target changed")
    except (KeyError, ValueError, TypeError, OSError, PrepareEvidenceError) as exc:
        if isinstance(exc, PrepareEvidenceError) and exc.code == "WHD_JOB_STAGING_STALE":
            raise
        raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "persisted stage evidence is not current") from exc


class DurableJobIdentityLedger:
    """Private same-job replay ledger, isolated from unfinished W-06 output journal.

    SQLite BEGIN IMMEDIATE serializes same identity and output directory
    reservations across processes. A lease survives an unfinished job/crash.
    This is not a multi-file commit journal or a complete Windows alias gate.
    """

    def __init__(self, trusted_store_root: Path):
        if (not isinstance(trusted_store_root, Path)
                or trusted_store_root.is_symlink()
                or _unsafe_windows_path(trusted_store_root)
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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS staged_batch_snapshots (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL,
                    PRIMARY KEY (client_id, job_id, operation)
                )
            """)

            # W-03 trusted prepare request and genuine WHD receipt are one
            # authenticated, immutable W-06 job transaction. Never derive
            # a new original request from CADSplit export wire JSON.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_prepares (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    source_and_receipt_json TEXT NOT NULL,
                    source_and_receipt_hmac TEXT NOT NULL,
                    PRIMARY KEY(client_id,job_id)
                )
            """)

            # W-06 cancel is private, durable and irreversible for a job.
            # Once a replacement is ARMED, cancellation cannot interrupt a
            # multi-DXF transaction; explicit crash recovery remains owner.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_cancel_intents (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    PRIMARY KEY(client_id,job_id,operation)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_replace_journals (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('armed','applying','applied','rolling_back','rolled_back','committed')
                    ),
                    plan_json TEXT NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    PRIMARY KEY (client_id,job_id,operation)
                )
            """)

    def _connect(self):
        if (self._root.is_symlink() or _unsafe_windows_path(self._root)
                or not self._root.is_dir() or self._db.is_symlink()):
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
            # A rollback is durable and final: do not rerender it under the
            # same immutable job identity, even though jobs.state is started.
            with closing(self._connect()) as conn:
                terminal = conn.execute(
                    """SELECT state,request_digest FROM batch_replace_journals
                       WHERE client_id=? AND job_id=? AND operation=?""",
                    (client, job, op),
                ).fetchone()
            if terminal is not None and terminal == ("rolled_back", digest):
                # Never trust an easily corrupted terminal-state string alone:
                # rehash the original final DXFs and journal against the
                # original directory's physical identity on every readback.
                from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal
                DurableMultiDXFRollbackJournal(self).verify_rolled_back(request)
                return JobClaim("rolled_back")
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


    def prepare_and_persist(
        self,
        request: Mapping[str, Any],
        *,
        resource_root: Path,
        engine_commit: str,
        engine_sha256: str,
        build_id: str,
        worker_key: bytes,
    ) -> dict[str, Any]:
        """PRIVATE W-03→W-06 bridge, not an activated public Worker handler.

        First claim is durable BEFORE WHD processes the batch. W-03 recomputes
        all physical Frame/baseline/policy/HMAC facts. The exact original
        request and actual WHD receipt are HMAC-sealed and committed together
        with the W-06 immutable result in ONE SQLite transaction.
        A crash after claim is recovery-required, NEVER a second render.
        """
        client, job, operation, digest = _identity(request)
        if operation != "prepare":
            raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "private prepare only")
        if not isinstance(worker_key, bytes) or len(worker_key) < 32:
            raise PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", "trusted Worker key missing")
        claim = self.claim(request)
        if claim.state == "committed":
            original, persisted = self.load_trusted_prepare(
                client_installation_id=client, job_id=job, worker_key=worker_key,
            )
            if _identity(original)[3] != digest:
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "immutable prepare request changed")
            return persisted
        if claim.state != "new":
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "prepare cannot be rerun")
        self.assert_not_cancelled(request)

        from integration_cli.prepare_batch import prepare_trusted_door_batch

        receipt = prepare_trusted_door_batch(
            request, resource_root=resource_root, engine_commit=engine_commit,
            engine_sha256=engine_sha256, build_id=build_id, worker_key=worker_key,
        )
        if (receipt.get("operation") != "prepare" or receipt.get("status") != "success"
                or receipt.get("manufacturing_verified") is not False
                or receipt.get("client_installation_id") != client
                or receipt.get("job_id") != job or receipt.get("request_digest") != digest):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "WHD-owned prepare receipt invalid")
        payload = _json({"original_request": request, "trusted_receipt": receipt})
        mac = hmac.new(
            worker_key, ("WHD-W06-TRUSTED-PREPARE-v1\x00" + client + "\x00"
                         + job + "\x00" + digest + "\x00" + payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        result_json = _json(receipt)
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                job_row = conn.execute(
                    """SELECT request_digest,state FROM jobs
                       WHERE client_id=? AND job_id=? AND operation='prepare'""",
                    (client, job),
                ).fetchone()
                if not job_row or job_row != (digest, "started"):
                    raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "prepare job changed before commit")
                if conn.execute(
                    """SELECT 1 FROM job_cancel_intents
                       WHERE client_id=? AND job_id=? AND operation='prepare' AND request_digest=?""",
                    (client, job, digest),
                ).fetchone():
                    raise PrepareEvidenceError("WHD_JOB_CANCELLED", "prepare cancelled before immutable receipt")
                conn.execute(
                    """INSERT INTO trusted_prepares
                       (client_id,job_id,request_digest,source_and_receipt_json,source_and_receipt_hmac)
                       VALUES (?,?,?,?,?)""",
                    (client, job, digest, payload, mac),
                )
                conn.execute(
                    """UPDATE jobs SET state='committed',result_json=?,result_sha256=?,artifact_json='{}'
                       WHERE client_id=? AND job_id=? AND operation='prepare' AND state='started'""",
                    (result_json, hashlib.sha256(result_json.encode("utf-8")).hexdigest(), client, job),
                )
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot atomically persist prepared batch") from exc
            except BaseException:
                conn.rollback()
                raise
        return receipt

    def load_trusted_prepare(
        self, *, client_installation_id: str, job_id: str, worker_key: bytes,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Read original Worker-owned W-03 evidence, never trust client copies.

        A checksum alone is insufficient: every load checks an HMAC bound to
        the original job, the identical persisted job result, and its digest.
        This does NOT assert source DXF is still current: export-time W-03
        recheck independently rereads the actual resources and source bytes.
        """
        client, job = client_installation_id, job_id
        if not isinstance(client, str) or not _JOB_ID.fullmatch(client) or (
                not isinstance(job, str) or not _JOB_ID.fullmatch(job)):
            raise PrepareEvidenceError("WHD_JOB_ID_INVALID", "invalid prepared job identity")
        if not isinstance(worker_key, bytes) or len(worker_key) < 32:
            raise PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", "trusted Worker key missing")
        with closing(self._connect()) as conn:
            row = conn.execute(
                """SELECT j.request_digest,j.state,j.result_json,j.result_sha256,j.artifact_json,
                          t.request_digest,t.source_and_receipt_json,t.source_and_receipt_hmac
                   FROM jobs AS j LEFT JOIN trusted_prepares AS t
                     ON t.client_id=j.client_id AND t.job_id=j.job_id
                   WHERE j.client_id=? AND j.job_id=? AND j.operation='prepare'""",
                (client, job),
            ).fetchone()
        if row is None or row[1] != "committed":
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "trusted prepare has no durable completion")
        digest, _, result_json, result_hash, artifacts, sealed_digest, payload, mac = row
        if not all(isinstance(value, str) for value in
                   (digest, result_json, result_hash, artifacts, sealed_digest, payload, mac)):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "trusted prepare record is incomplete")
        expected_mac = hmac.new(
            worker_key, ("WHD-W06-TRUSTED-PREPARE-v1\x00" + client + "\x00"
                         + job + "\x00" + digest + "\x00" + payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if (not hmac.compare_digest(digest, sealed_digest)
                or not hmac.compare_digest(expected_mac, mac)
                or not hmac.compare_digest(hashlib.sha256(result_json.encode("utf-8")).hexdigest(), result_hash)
                or artifacts != "{}"):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "trusted prepare has changed on disk")
        try:
            decoded = json.loads(payload)
            request = decoded["original_request"]
            receipt = decoded["trusted_receipt"]
            if (not isinstance(request, dict) or not isinstance(receipt, dict)
                    or _identity(request) != (client, job, "prepare", digest)
                    or _json(receipt) != result_json
                    or receipt.get("status") != "success"
                    or receipt.get("manufacturing_verified") is not False
                    or receipt.get("operation") != "prepare"
                    or receipt.get("client_installation_id") != client
                    or receipt.get("job_id") != job
                    or receipt.get("request_digest") != digest):
                raise ValueError("bad persisted prepare record")
        except (KeyError, TypeError, ValueError, PrepareEvidenceError) as exc:
            raise PrepareEvidenceError(
                "WHD_JOB_RECOVERY_REQUIRED", "trusted prepare original request/receipt unverified"
            ) from exc
        return request, receipt

    def recheck_persisted_prepare_for_export(
        self,
        export_request: Mapping[str, Any],
        *,
        resource_root: Path,
        engine_commit: str,
        engine_sha256: str,
        build_id: str,
        worker_key: bytes,
        source_documents: Mapping[str, Path] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Export guard requires original *stored* WHD receipt, not wire copies."""
        if not isinstance(export_request, Mapping) or export_request.get("operation") != "export":
            raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "export evidence required")
        original, receipt = self.load_trusted_prepare(
            client_installation_id=export_request.get("client_installation_id"),
            job_id=export_request.get("job_id"), worker_key=worker_key,
        )
        from integration_cli.prepare_recheck import recheck_trusted_door_export
        recheck_trusted_door_export(
            original, receipt, export_request,
            resource_root=resource_root, engine_commit=engine_commit,
            engine_sha256=engine_sha256, build_id=build_id,
            worker_key=worker_key, source_documents=source_documents,
        )
        return original, receipt

    def request_cancel(self, request: Mapping[str, Any]) -> str:
        """PRIVATE trusted-Worker cancellation, never a public JSON handler.

        Only a currently started job with the exact canonical digest can be
        cancelled. SQLite BEGIN IMMEDIATE serializes this against W-06 journal
        arm, so cancellation after commit intent is NOT falsely accepted.
        """
        client, job, op, digest = _identity(request)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None or row[1] != "started":
                raise PrepareEvidenceError(
                    "WHD_JOB_RECOVERY_REQUIRED", "job is not cancellable",
                )
            if not isinstance(row[0], str) or not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "cancel job digest differs")
            if op == "export" and conn.execute(
                """SELECT 1 FROM batch_replace_journals
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone() is not None:
                raise PrepareEvidenceError(
                    "WHD_JOB_RECOVERY_REQUIRED",
                    "replacement already armed; only verified recovery can resolve job",
                )
            current = conn.execute(
                """SELECT request_digest FROM job_cancel_intents
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if current is not None and (
                not isinstance(current[0], str) or
                not hmac.compare_digest(current[0], digest)
            ):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "cancel intent digest changed")
            if current is None:
                conn.execute(
                    """INSERT INTO job_cancel_intents
                       (client_id,job_id,operation,request_digest)
                       VALUES (?,?,?,?)""", (client, job, op, digest),
                )
            conn.commit()
            return "requested"
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot persist cancel intent") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def assert_not_cancelled(self, request: Mapping[str, Any]) -> None:
        """Private safe-point check; no IO to a customer destination."""
        client, job, op, digest = _identity(request)
        with closing(self._connect()) as conn:
            row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            cancel = conn.execute(
                """SELECT request_digest FROM job_cancel_intents
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
        if row is None or row[1] != "started" or not isinstance(row[0], str):
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "no active job for cancel checkpoint")
        if not hmac.compare_digest(row[0], digest):
            raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "cancel checkpoint job digest differs")
        if cancel is not None:
            if not isinstance(cancel[0], str) or not hmac.compare_digest(cancel[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "untrusted cancel intent")
            raise PrepareEvidenceError("WHD_JOB_CANCELLED", "trusted Worker job cancellation requested")

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
                # A different spelling or DOS drive letter cannot grant a
                # second exclusive lock on one physical directory.
                alias = conn.execute(
                    """SELECT l.directory_key FROM output_directory_leases AS l
                       JOIN output_directory_identity AS i
                         ON i.directory_key=l.directory_key
                       WHERE i.device_id=? AND i.inode_id=?
                         AND l.directory_key<>?""",
                    (*physical[key], key),
                ).fetchone()
                if alias is not None:
                    raise PrepareEvidenceError(
                        "WHD_OUTPUT_PATH_LOCKED",
                        "physical directory already leased under another path",
                    )
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

    def record_staged_batch_snapshot(
        self,
        request: Mapping[str, Any],
        *,
        trusted_output_dir: Path,
        trusted_staged: Mapping[str, Path],
        overwrite: bool,
    ) -> dict[str, Any]:
        """Persist immutable *precommit* evidence for an already reserved job.

        An actual W-06 durable backup+commit/recovery owner must be created
        before this record may authorize a customer DXF replacement. This
        method never writes to, deletes or moves any customer DXF.
        """
        client, job, op, digest = _identity(request)
        if op != "export":
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "only export may stage a batch")
        output = request.get("output")
        if (not isinstance(output, Mapping)
                or type(output.get("overwrite")) is not bool
                or output["overwrite"] is not overwrite):
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "overwrite must match authenticated wire intent")
        snapshot = _staged_batch_snapshot(
            trusted_output_dir, trusted_staged, overwrite=overwrite,
        )
        encoded = _json(snapshot)
        proof_sha = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None or row[1] != "started":
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "job has no active durable reservation")
            if not isinstance(row[0], str) or not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "job content changed")
            lease = conn.execute(
                """SELECT request_digest FROM output_directory_leases
                   WHERE directory_key=? AND client_id=? AND job_id=? AND operation=?""",
                (snapshot["directory_key"], client, job, op),
            ).fetchone()
            if lease is None or lease[0] != digest:
                raise PrepareEvidenceError("WHD_OUTPUT_PATH_LOCKED", "stage directory not leased by job")
            pinned = conn.execute(
                """SELECT device_id,inode_id FROM output_directory_identity WHERE directory_key=?""",
                (snapshot["directory_key"],),
            ).fetchone()
            if pinned is None or pinned != _directory_identity(trusted_output_dir):
                raise PrepareEvidenceError(
                    "WHD_JOB_RECOVERY_REQUIRED", "staged destination physical directory differs from lease"
                )
            prior = conn.execute(
                """SELECT request_digest,snapshot_json,snapshot_sha256
                   FROM staged_batch_snapshots
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if prior is not None:
                if prior != (digest, encoded, proof_sha):
                    raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "job staged inventory differs")
            else:
                conn.execute(
                    """INSERT INTO staged_batch_snapshots
                       (client_id,job_id,operation,request_digest,snapshot_json,snapshot_sha256)
                       VALUES (?,?,?,?,?,?)""",
                    (client, job, op, digest, encoded, proof_sha),
                )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot persist stage snapshot") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        _assert_staged_batch_snapshot_current(snapshot)
        return snapshot

    def require_staged_batch_snapshot_current(
        self, request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Read back durable precommit manifest and independently rehash disk."""
        client, job, op, digest = _identity(request)
        if op != "export":
            raise PrepareEvidenceError("WHD_JOB_STAGING_INVALID", "only export has staged inventory")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT request_digest,snapshot_json,snapshot_sha256
                   FROM staged_batch_snapshots
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if row is None:
                raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "no durable staged inventory")
            if not isinstance(row[0], str) or not hmac.compare_digest(row[0], digest):
                raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "staged job identity changed")
            encoded, sha = row[1], row[2]
            if (not isinstance(encoded, str) or not isinstance(sha, str)
                    or not hmac.compare_digest(hashlib.sha256(encoded.encode("utf-8")).hexdigest(), sha)):
                raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "stage journal checksum invalid")
            snapshot = json.loads(encoded)
            leased = conn.execute(
                """SELECT request_digest FROM output_directory_leases
                   WHERE directory_key=? AND client_id=? AND job_id=? AND operation=?""",
                (snapshot["directory_key"], client, job, op),
            ).fetchone()
            if leased is None or leased[0] != digest:
                raise PrepareEvidenceError("WHD_OUTPUT_PATH_LOCKED", "stage journal has no live lease")
            pinned = conn.execute(
                """SELECT device_id,inode_id FROM output_directory_identity WHERE directory_key=?""",
                (snapshot["directory_key"],),
            ).fetchone()
            if pinned is None or pinned != _directory_identity(Path(snapshot["directory_key"])):
                raise PrepareEvidenceError(
                    "WHD_JOB_RECOVERY_REQUIRED", "staged destination was replaced after lease"
                )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "cannot read stage journal") from exc
        except (KeyError, TypeError, ValueError) as exc:
            conn.rollback()
            raise PrepareEvidenceError("WHD_JOB_STAGING_STALE", "stage journal is corrupt") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        _assert_staged_batch_snapshot_current(snapshot)
        return snapshot

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
            if conn.execute(
                """SELECT 1 FROM job_cancel_intents
                   WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
                (client, job, op, digest),
            ).fetchone():
                raise PrepareEvidenceError("WHD_JOB_CANCELLED", "cancelled job cannot commit success")
            if op == "export":
                pending_stage = conn.execute(
                    """SELECT 1 FROM staged_batch_snapshots
                       WHERE client_id=? AND job_id=? AND operation=?""",
                    (client, job, op),
                ).fetchone()
                if pending_stage is not None:
                    # A staged proof alone must NEVER authorize success. Only
                    # the real persisted replacement journal in 'applied'
                    # state, with identical physical final-file bytes, does.
                    journal = conn.execute(
                        """SELECT request_digest,state,plan_json,plan_sha256
                           FROM batch_replace_journals
                           WHERE client_id=? AND job_id=? AND operation=?""",
                        (client, job, op),
                    ).fetchone()
                    if (journal is None or journal[0] != digest
                            or journal[1] != "applied"
                            or not isinstance(journal[2], str)
                            or not isinstance(journal[3], str)
                            or not hmac.compare_digest(
                                hashlib.sha256(journal[2].encode("utf-8")).hexdigest(),
                                journal[3],
                            )):
                        raise PrepareEvidenceError(
                            "WHD_JOB_RECOVERY_REQUIRED", "staged batch lacks verified durable commit journal"
                        )
                    try:
                        plan = json.loads(journal[2])
                        expected = {item["physical_id"]: item for item in plan["items"]}
                    except (ValueError, KeyError, TypeError) as exc:
                        raise PrepareEvidenceError(
                            "WHD_JOB_RECOVERY_REQUIRED", "corrupt replacement inventory"
                        ) from exc
                    if not expected or set(proofs) != set(expected):
                        raise PrepareEvidenceError(
                            "WHD_JOB_RECOVERY_REQUIRED", "partial replacement receipt"
                        )
                    for physical, proof in proofs.items():
                        item = expected[physical]
                        stage = item["staged"]
                        if (proof["path"] != item["destination"]
                                or any(proof[k] != stage[k] for k in ("sha256", "size", "mtime_ns"))):
                            raise PrepareEvidenceError(
                                "WHD_JOB_RECOVERY_REQUIRED", "committed DXF proof differs from durable intent"
                            )
                        backup = item.get("backup")
                        original = item.get("original")
                        if original is not None:
                            if (not isinstance(backup, dict)
                                    or any(backup[k] != original[k]
                                           for k in ("sha256", "size", "mtime_ns"))
                                    or _file_proof(Path(backup["path"])) != backup):
                                raise PrepareEvidenceError(
                                    "WHD_JOB_RECOVERY_REQUIRED", "customer original recovery backup lost"
                                )
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
            if op == "export" and pending_stage is not None:
                cur = conn.execute(
                    """UPDATE batch_replace_journals SET state='committed'
                       WHERE client_id=? AND job_id=? AND operation=? AND
                             request_digest=? AND state='applied'""",
                    (client, job, op, digest),
                )
                if cur.rowcount != 1:
                    raise PrepareEvidenceError(
                        "WHD_JOB_RECOVERY_REQUIRED", "replacement journal lost before receipt commit"
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
