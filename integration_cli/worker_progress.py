# -*- coding: utf-8 -*-
"""#2380 W-06 private progress.json, a read-only SQLite-derived projection.

Never grants manufacturing authority, authorizes an export, resumes an
uncertain job, or marks a partial multi-DXF replacement successful. All
paths originate in the trusted Worker store, not CADSplit JSON. Persisted
progress.json is informational; every read is recomputed from the ledger.
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
    DurableJobIdentityLedger, _identity, _json, _unsafe_windows_path,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.original_backup_manifest import _sync_directory


def _error(code: str, detail: str) -> PrepareEvidenceError:
    return PrepareEvidenceError(code, detail)


class PrivateWorkerProgress:
    """Project the actual W-06 durable state to one file per immutable job."""

    def __init__(self, ledger: DurableJobIdentityLedger):
        if not isinstance(ledger, DurableJobIdentityLedger):
            raise _error("WHD_JOB_STORE_UNAVAILABLE", "trusted Worker ledger required")
        self._ledger = ledger

    def _snapshot(self, request: Mapping[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
        client, job, op, digest = _identity(request)
        row = conn.execute(
            """SELECT request_digest,state FROM jobs
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, op),
        ).fetchone()
        if row is None or row[1] not in ("started", "committed"):
            raise _error("WHD_JOB_RECOVERY_REQUIRED", "progress job is not reserved")
        if not isinstance(row[0], str) or not hmac.compare_digest(row[0], digest):
            raise _error("WHD_JOB_ID_CONFLICT", "progress job has different semantic request")

        cancel = conn.execute(
            """SELECT request_digest FROM job_cancel_intents
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, op),
        ).fetchone()
        if cancel is not None and (
            not isinstance(cancel[0], str) or not hmac.compare_digest(cancel[0], digest)
        ):
            raise _error("WHD_JOB_ID_CONFLICT", "untrusted progress cancel intent")
        journal = conn.execute(
            """SELECT request_digest,state,plan_json,plan_sha256
               FROM batch_replace_journals
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, op),
        ).fetchone()
        if journal is not None:
            if (not isinstance(journal[0], str)
                    or not hmac.compare_digest(journal[0], digest)
                    or journal[1] not in (
                        "armed", "applying", "applied", "rolling_back",
                        "rolled_back", "committed",
                    )
                    or not isinstance(journal[2], str)
                    or not isinstance(journal[3], str)
                    or not hmac.compare_digest(
                        hashlib.sha256(journal[2].encode("utf-8")).hexdigest(),
                        journal[3],
                    )):
                raise _error("WHD_JOB_RECOVERY_REQUIRED", "untrusted replacement journal")
        staged = conn.execute(
            """SELECT request_digest,snapshot_json,snapshot_sha256
               FROM staged_batch_snapshots
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, op),
        ).fetchone()
        if staged is not None:
            if (not isinstance(staged[0], str)
                    or not hmac.compare_digest(staged[0], digest)
                    or not isinstance(staged[1], str)
                    or not isinstance(staged[2], str)
                    or not hmac.compare_digest(
                        hashlib.sha256(staged[1].encode("utf-8")).hexdigest(),
                        staged[2],
                    )):
                raise _error("WHD_JOB_RECOVERY_REQUIRED", "untrusted staged progress")
        if not isinstance(request.get("items"), list) or not 1 <= len(request["items"]) <= 20:
            raise _error("WHD_JOB_ID_INVALID", "progress requires verified batch count")
        total = len(request["items"])
        completed = row[1] == "committed"
        if completed and cancel is not None:
            raise _error("WHD_JOB_RECOVERY_REQUIRED", "committed job has cancel intent")
        if completed:
            phase, percent = ("prepared" if op == "prepare" else "completed"), 100
        elif journal is not None:
            state = journal[1]
            phase, percent = {
                "armed": ("precommit", 75),
                "applying": ("recovery_required", 75),
                "applied": ("awaiting_verified_receipt", 90),
                "rolling_back": ("recovery_required", 75),
                "rolled_back": ("rolled_back", 75),
                "committed": ("recovery_required", 90),
            }[state]
        elif cancel is not None:
            phase, percent = "cancel_requested", 0
        elif staged is not None:
            phase, percent = "staged", 50
        else:
            phase, percent = "claimed", 0
        # A cancellation occurring before journal arm wins, including when
        # stage evidence already exists. Never claim a cancellable "success".
        if cancel is not None and not completed and journal is None:
            phase = "cancel_requested"
        return {
            "schema": "whd-worker-private-progress-v1",
            "client_installation_id": client,
            "job_id": job,
            "operation": op,
            "request_digest": digest,
            "phase": phase,
            "percent": percent,
            "completed_items": total if completed else 0,
            "total_items": total,
            "manufacturing_verified": False,
        }

    def read(
        self, request: Mapping[str, Any], *, worker_key: bytes | None = None,
    ) -> dict[str, Any]:
        """Always derive fresh authority from DB; never parse progress.json."""
        client, job, op, digest = _identity(request)
        # The normal immutable result readback is the only success authority.
        with closing(self._ledger._connect()) as conn:
            row = conn.execute(
                """SELECT state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
                (client, job, op, digest),
            ).fetchone()
        if row and row[0] == "committed":
            self._ledger.claim(request)  # rehash actual immutable artifact proof
            if op == "prepare":
                # Plain job SHA alone cannot authenticate a W-03 prepare
                # receipt. Require the real Worker-owned HMAC secret before
                # publishing any 100% prepare projection.
                self._ledger.load_trusted_prepare(
                    client_installation_id=client, job_id=job,
                    worker_key=worker_key,
                )
        with closing(self._ledger._connect()) as conn:
            return self._snapshot(request, conn)

    def publish(
        self, request: Mapping[str, Any], *, worker_key: bytes | None = None,
    ) -> Path:
        """Atomically publish a non-authoritative progress.json in Worker store.

        SQLite BEGIN IMMEDIATE prevents concurrent projection writes and
        ordering regressions from separate Worker processes. Fail-closed on
        unsafe paths and IO; no client-chosen output path is accepted.
        """
        client, job, op, digest = _identity(request)
        # Verify a completed job before any JSON can say "100%".
        self.read(request, worker_key=worker_key)
        encoded_identity = _json([client, job, op, digest]).encode("utf-8")
        directory_name = "job-" + hashlib.sha256(encoded_identity).hexdigest()
        conn = self._ledger._connect()
        tmp: Path | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            state = self._snapshot(request, conn)
            if state["percent"] == 100:
                # This exact durable result was independently checked by
                # read() before BEGIN IMMEDIATE, and a committed job cannot
                # be rewritten by normal W-06 transitions.
                pass
            root = self._ledger._root
            progress_dir = root / "progress"
            if not progress_dir.exists():
                progress_dir.mkdir()
            folder = progress_dir / directory_name
            if not folder.exists():
                folder.mkdir()
            for node in (root, progress_dir, folder):
                if node.is_symlink() or _unsafe_windows_path(node) or not node.is_dir():
                    raise _error("WHD_JOB_STORE_UNAVAILABLE", "untrusted progress path")
            target = folder / "progress.json"
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise _error("WHD_JOB_STORE_UNAVAILABLE", "untrusted progress target")
            raw = (_json(state) + "\n").encode("utf-8")
            fd, name = tempfile.mkstemp(prefix=".progress-", suffix=".tmp", dir=folder)
            tmp = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
            tmp = None
            _sync_directory(folder)
            conn.commit()
            return target
        except (OSError, sqlite3.Error) as exc:
            conn.rollback()
            raise _error("WHD_JOB_STORE_UNAVAILABLE", "cannot publish private progress") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            conn.close()
