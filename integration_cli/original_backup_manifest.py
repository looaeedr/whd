# -*- coding: utf-8 -*-
"""#2380 W-06 private customer-original DXF backup evidence, before any commit.

Backups of ORIGINAL customer files only. The real WHD FinalScene producer
and its Save→Reload verifier own stage DXFs. This module NEVER replaces,
unlinks, moves or creates a customer output file, and NEVER declares a job
committed. Missing journal/backup after a crash remains recovery_required.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Mapping

from integration_cli.job_identity_ledger import (
    DurableJobIdentityLedger,
    _directory_identity, _file_proof, _identity, _json,
    _output_directory_keys,
)
from integration_cli.prepare_evidence import PrepareEvidenceError


def _backup_error(message: str) -> PrepareEvidenceError:
    return PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", message)


def _sync_directory(path: Path) -> None:
    """Sync real directory metadata; refuse the transaction if unsupported.

    Windows Python's CRT os.open/os.fsync cannot flush a directory. The
    Windows path uses a real GENERIC_WRITE Win32 directory handle and
    FlushFileBuffers instead of silently skipping this durability barrier.
    """
    if not path.is_dir() or path.is_symlink():
        raise _backup_error("untrusted original-backup directory")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        create.restype = wintypes.HANDLE
        flush = kernel.FlushFileBuffers
        flush.argtypes = (wintypes.HANDLE,)
        flush.restype = wintypes.BOOL
        close = kernel.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        # GENERIC_READ|WRITE, share read/write/delete, OPEN_EXISTING and
        # FILE_FLAG_BACKUP_SEMANTICS for a real directory Win32 handle.
        handle = create(str(path), 0xC0000000, 0x7, None, 3, 0x02000000, None)
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise _backup_error("Windows directory durability handle unavailable")
        try:
            if not flush(handle):
                raise _backup_error("Windows directory flush unavailable")
        finally:
            close(handle)
        return
    try:
        handle = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
    except OSError as exc:
        raise _backup_error("original-backup directory fsync unavailable") from exc


def _verified_backup_file(original: Mapping[str, Any], backup: Path) -> dict[str, Any]:
    source = Path(original["path"])
    if not source.is_file() or source.is_symlink():
        raise _backup_error("customer original disappeared before backup")
    if _file_proof(source) != original:
        raise _backup_error("customer original changed before backup")
    if backup.exists() or backup.is_symlink():
        raise _backup_error("private backup target is occupied")
    try:
        # Exclusive destination creation: do not follow or overwrite a
        # preexisting file even inside the private backup directory.
        with source.open("rb") as src, backup.open("xb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        srcstat = source.stat()
        os.utime(backup, ns=(srcstat.st_atime_ns, original["mtime_ns"]))
        # Windows CRT _commit() needs a writable file handle. This is the
        # newly generated PRIVATE backup, never the customer original file.
        with backup.open("rb+") as verified:
            os.fsync(verified.fileno())
        proof = _file_proof(backup)
    except (OSError, ValueError) as exc:
        raise _backup_error("cannot create and fsync customer original backup") from exc
    if (proof["sha256"], proof["size"], proof["mtime_ns"]) != (
        original["sha256"], original["size"], original["mtime_ns"]
    ) or _file_proof(source) != original:
        raise _backup_error("backup or customer original changed during copy")
    return proof


class DurableOriginalBackupEvidence:
    """Worker-private, read-only recovery input for a future multi-DXF journal.

    Backup files are physically on the output volume, in a Worker-generated
    inaccessible-by-wire directory. Once confirmed, the immutable SQLite
    receipt binds both saved original-file proofs and backup-file proofs.
    This does not finish/rollback a job; ledger's pending-stage gate remains.
    """

    def __init__(self, ledger: DurableJobIdentityLedger):
        if not isinstance(ledger, DurableJobIdentityLedger):
            raise _backup_error("trusted W-06 job ledger required")
        self._ledger = ledger
        with closing(ledger._connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS original_backup_manifests (
                    client_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    PRIMARY KEY (client_id,job_id,operation)
                )
            """)

    def _load_row(self, request: Mapping[str, Any]):
        client, job, operation, _ = _identity(request)
        with closing(self._ledger._connect()) as conn:
            return conn.execute(
                """SELECT request_digest,manifest_json,manifest_sha256
                   FROM original_backup_manifests
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, operation),
            ).fetchone()

    def _validate(
        self, request: Mapping[str, Any], snapshot: Mapping[str, Any], row,
    ) -> dict[str, Any]:
        _, _, op, digest = _identity(request)
        if op != "export" or row is None:
            raise _backup_error("no durable original-backup manifest")
        if not isinstance(row[0], str) or not hmac.compare_digest(row[0], digest):
            raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "backup manifest job digest differs")
        payload, sha = row[1], row[2]
        if (not isinstance(payload, str) or not isinstance(sha, str)
                or not hmac.compare_digest(hashlib.sha256(payload.encode("utf-8")).hexdigest(), sha)):
            raise _backup_error("original-backup manifest checksum invalid")
        try:
            manifest = json.loads(payload)
            if (manifest["stage_snapshot_sha256"]
                    != hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest()):
                raise _backup_error("original backup no longer matches staged batch")
            root = Path(manifest["directory"])
            key, = _output_directory_keys([root])
            if key != snapshot["directory_key"]:
                raise _backup_error("backup and staged output destinations differ")
            source_identity = _directory_identity(root)
            if tuple(manifest["output_identity"]) != source_identity:
                raise _backup_error("output directory was replaced")
            folder = Path(manifest["backup_directory"])
            if (folder.is_symlink() or not folder.is_dir() or
                    folder.parent != root or
                    not folder.name.startswith(".whd-w06-original-backup-") or
                    tuple(manifest["backup_identity"]) != _directory_identity(folder) or
                    folder.stat().st_dev != root.stat().st_dev):
                raise _backup_error("private backup folder lost its physical identity")
            original_rows = {
                item["physical_id"]: item["original"] for item in snapshot["items"]
                if item["original"] is not None
            }
            if set(original_rows) != set(manifest["backups"]):
                raise _backup_error("backup manifest has wrong original inventory")
            for physical, proof in manifest["backups"].items():
                file = Path(proof["path"])
                if (file.parent != folder or file.name != f"{physical}.dxf"
                        or _file_proof(file) != proof):
                    raise _backup_error("private original DXF backup changed")
                prior = original_rows[physical]
                if (proof["sha256"], proof["size"], proof["mtime_ns"]) != (
                    prior["sha256"], prior["size"], prior["mtime_ns"]
                ):
                    raise _backup_error("private backup differs from customer original")
        except (KeyError, ValueError, TypeError, OSError, PrepareEvidenceError) as exc:
            if isinstance(exc, PrepareEvidenceError) and exc.code == "WHD_JOB_ID_CONFLICT":
                raise
            raise _backup_error("original-backup evidence is incomplete or untrusted") from exc
        return manifest

    def require_current(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Read-only independent reopen; no customer DXF is altered."""
        snapshot = self._ledger.require_staged_batch_snapshot_current(request)
        return self._validate(request, snapshot, self._load_row(request))

    def create_verified_original_backups(
        self, request: Mapping[str, Any], *, trusted_output_dir: Path,
    ) -> dict[str, Any]:
        """Copy only existing originals, fsync proof, then durably record manifest.

        A crash before the SQLite receipt leaves *only* a private orphan
        backup folder; no customer output was touched and rerender remains
        blocked by the original immutable job identity and directory lease.
        A preexisting valid receipt is returned without rewriting any bytes.
        """
        client, job, op, digest = _identity(request)
        if op != "export":
            raise _backup_error("only export may snapshot original physical DXFs")
        snapshot = self._ledger.require_staged_batch_snapshot_current(request)
        outkey, = _output_directory_keys([trusted_output_dir])
        if snapshot["directory_key"] != outkey:
            raise _backup_error("trusted output directory differs from staged batch")
        existing = self._load_row(request)
        if existing is not None:
            return self._validate(request, snapshot, existing)
        # This is a pure original-file backup. No staged file is moved and no
        # final customer path is created, unlinked, or replaced.
        try:
            folder = Path(tempfile.mkdtemp(prefix=".whd-w06-original-backup-", dir=str(trusted_output_dir)))
            if folder.stat().st_dev != trusted_output_dir.stat().st_dev:
                raise _backup_error("backup folder is not on original target volume")
            copies = {}
            for item in snapshot["items"]:
                old = item["original"]
                if old is not None:
                    copies[item["physical_id"]] = _verified_backup_file(
                        old, folder / f"{item['physical_id']}.dxf"
                    )
            _sync_directory(folder)
            _sync_directory(trusted_output_dir)
        except (OSError, ValueError) as exc:
            raise _backup_error("cannot persist original DXF backups") from exc
        # The sources must still be unchanged after potentially long copies.
        if self._ledger.require_staged_batch_snapshot_current(request) != snapshot:
            raise _backup_error("stage or customer original changed during backup")
        manifest = {
            "directory": str(trusted_output_dir),
            "output_identity": list(_directory_identity(trusted_output_dir)),
            "backup_directory": str(folder),
            "backup_identity": list(_directory_identity(folder)),
            "stage_snapshot_sha256": hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest(),
            "backups": copies,
        }
        encoded = _json(manifest)
        encoded_sha = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        conn = self._ledger._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                """SELECT request_digest,manifest_json,manifest_sha256 FROM original_backup_manifests
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if current is not None:
                raise _backup_error("another backup manifest was committed concurrently")
            job_row = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if job_row != (digest, "started"):
                raise _backup_error("original export reservation changed during backup")
            pinned = conn.execute(
                """SELECT l.request_digest,p.device_id,p.inode_id FROM output_directory_leases l
                   JOIN output_directory_identity p ON l.directory_key=p.directory_key
                   WHERE l.directory_key=? AND l.client_id=? AND l.job_id=? AND l.operation=?""",
                (outkey, client, job, op),
            ).fetchone()
            if pinned != (digest, *manifest["output_identity"]):
                raise _backup_error("output physical directory lease changed during backup")
            conn.execute(
                """INSERT INTO original_backup_manifests
                   (client_id,job_id,operation,request_digest,manifest_json,manifest_sha256)
                   VALUES (?,?,?,?,?,?)""",
                (client, job, op, digest, encoded, encoded_sha),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise _backup_error("cannot persist original-backup manifest") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._validate(request, snapshot, (digest, encoded, encoded_sha))
