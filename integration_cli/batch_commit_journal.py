# -*- coding: utf-8 -*-
"""#2380 private all-or-nothing file-replacement journal and crash rollback.

Caller MUST already have WHD-verified Save->Reload staged DXFs, the durable
job identity + physical directory lease, a frozen stage snapshot and fsynced
customer-original backups. This is NOT a public CADSplit Worker command.
No new geometry/render path is introduced here.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Callable, Mapping

from integration_cli.job_identity_ledger import (
    DurableJobIdentityLedger, _directory_identity, _file_proof,
    _identity, _json, _output_directory_keys,
)
from integration_cli.original_backup_manifest import (
    DurableOriginalBackupEvidence, _sync_directory,
)
from integration_cli.prepare_evidence import PrepareEvidenceError


def _refuse(message: str) -> PrepareEvidenceError:
    return PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", message)


def _proof_equals_expected(path: Path, proof: Mapping[str, Any]) -> bool:
    try:
        actual = _file_proof(path)
        return all(actual[key] == proof[key] for key in ("sha256", "size", "mtime_ns"))
    except (OSError, ValueError, PrepareEvidenceError):
        return False


class DurableMultiDXFRollbackJournal:
    """Persistent intent before replacement; separate explicit rollback owner.

    'applied' is not a public success receipt. Only the trusted ledger.complete
    may atomically publish the immutable job receipt and release directory
    leases. A crash in 'applying' requires recovery before another job writes.
    """

    def __init__(self, ledger: DurableJobIdentityLedger):
        if not isinstance(ledger, DurableJobIdentityLedger):
            raise _refuse("trusted job ledger required")
        self._ledger = ledger
        self._backups = DurableOriginalBackupEvidence(ledger)
        with closing(self._ledger._connect()) as conn:
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

    def _read(self, request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        client, job, op, digest = _identity(request)
        if op != "export":
            raise _refuse("DXF replacement journal is export-only")
        with closing(self._ledger._connect()) as conn:
            row = conn.execute(
                """SELECT request_digest,state,plan_json,plan_sha256 FROM batch_replace_journals
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
        if row is None:
            raise _refuse("no durable batch replacement intent")
        saved_digest, state, encoded, checksum = row
        if not isinstance(saved_digest, str) or not hmac.compare_digest(saved_digest, digest):
            raise PrepareEvidenceError("WHD_JOB_ID_CONFLICT", "replacement journal digest differs")
        if (not isinstance(encoded, str) or not isinstance(checksum, str)
                or not hmac.compare_digest(
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest(), checksum
                )):
            raise _refuse("replacement journal checksum invalid")
        try:
            plan = json.loads(encoded)
            if (not isinstance(plan, dict)
                    or not isinstance(plan["items"], list)
                    or not 1 <= len(plan["items"]) <= 20
                    or len({item["physical_id"] for item in plan["items"]}) != len(plan["items"])):
                raise ValueError("invalid journal")
        except (TypeError, KeyError, ValueError) as exc:
            raise _refuse("replacement journal inventory invalid") from exc
        return state, plan

    def _verify_owner(self, request: Mapping[str, Any], plan: Mapping[str, Any]) -> Path:
        client, job, op, digest = _identity(request)
        root = Path(plan["output_directory"])
        key, = _output_directory_keys([root])
        if key != plan["directory_key"]:
            raise _refuse("replacement journal points to another directory")
        phys = _directory_identity(root)
        if list(phys) != plan["output_identity"]:
            raise _refuse("replacement directory device/inode changed")
        with closing(self._ledger._connect()) as conn:
            jobrow = conn.execute(
                """SELECT request_digest,state FROM jobs
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            lease = conn.execute(
                """SELECT l.request_digest,p.device_id,p.inode_id
                   FROM output_directory_leases l
                   JOIN output_directory_identity p ON p.directory_key=l.directory_key
                   WHERE l.directory_key=? AND l.client_id=? AND l.job_id=? AND l.operation=?""",
                (key, client, job, op),
            ).fetchone()
        if (jobrow != (digest, "started") or lease != (digest, *phys)):
            raise _refuse("replacement journal has no active physical directory lease")
        return root

    def arm(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Durably record all original/staged/backup proofs *before* any rename."""
        client, job, op, digest = _identity(request)
        if op != "export":
            raise _refuse("batch replacement is export-only")
        # W-06 all-or-nothing is the only transaction policy implemented by
        # this private commit owner; per_part has different recovery semantics.
        if request.get("transaction_mode") != "all_or_nothing":
            raise _refuse("per-part manufacturing requires its own verified journal")
        snapshot = self._ledger.require_staged_batch_snapshot_current(request)
        backup_manifest = self._backups.require_current(request)
        root = Path(backup_manifest["directory"])
        physical = _directory_identity(root)
        original_backups = backup_manifest["backups"]
        rows = []
        for item in snapshot["items"]:
            name = item["physical_id"]
            if item["original"] is not None and name not in original_backups:
                raise _refuse("no durable backup for customer original")
            rows.append({
                "physical_id": name,
                "destination": item["destination"],
                "original": item["original"],
                "staged": item["stage"],
                "backup": original_backups.get(name),
            })
        plan = {
            "directory_key": snapshot["directory_key"],
            "output_directory": str(root),
            "output_identity": list(physical),
            "backup_directory": backup_manifest["backup_directory"],
            "backup_identity": backup_manifest["backup_identity"],
            "stage_sha256": hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest(),
            "backup_sha256": hashlib.sha256(_json(backup_manifest).encode("utf-8")).hexdigest(),
            "items": rows,
        }
        self._verify_owner(request, plan)
        encoded = _json(plan)
        sha = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        conn = self._ledger._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                """SELECT 1 FROM batch_replace_journals
                   WHERE client_id=? AND job_id=? AND operation=?""",
                (client, job, op),
            ).fetchone()
            if prior is not None:
                raise _refuse("existing replacement intent cannot be restarted")
            conn.execute(
                """INSERT INTO batch_replace_journals
                   (client_id,job_id,operation,request_digest,state,plan_json,plan_sha256)
                   VALUES (?,?,?,?,'armed',?,?)""",
                (client, job, op, digest, encoded, sha),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise _refuse("cannot persist replacement intent") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        return plan

    def _change_state(self, request: Mapping[str, Any], expected: str, changed: str) -> None:
        client, job, op, digest = _identity(request)
        conn = self._ledger._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """UPDATE batch_replace_journals SET state=?
                   WHERE client_id=? AND job_id=? AND operation=? AND request_digest=? AND state=?""",
                (changed, client, job, op, digest, expected),
            )
            if cur.rowcount != 1:
                raise _refuse("replacement journal state changed or is unverified")
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise _refuse("cannot persist replacement state") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def apply(
        self,
        request: Mapping[str, Any],
        *,
        after_replace: Callable[[int], None] | None = None,
    ) -> dict[str, Path]:
        """Replace already Save->Reload-verified stage files under durable intent.

        after_replace is a *private fault injection hook*; tests raise
        SystemExit to emulate abrupt process termination between DXF renames.
        No automatic retry or resumption of an interrupted replacement.
        """
        state, plan = self._read(request)
        if state != "armed":
            raise _refuse("cannot repeat or resume a previously armed replacement")
        root = self._verify_owner(request, plan)
        # Both evidence owners require every old and stage file to match before
        # any customer output can change.
        snapshot = self._ledger.require_staged_batch_snapshot_current(request)
        backup = self._backups.require_current(request)
        if hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest() != plan["stage_sha256"]:
            raise _refuse("source stage evidence differs")
        if hashlib.sha256(_json(backup).encode("utf-8")).hexdigest() != plan["backup_sha256"]:
            raise _refuse("original backup evidence differs")
        self._change_state(request, "armed", "applying")
        result: dict[str, Path] = {}
        try:
            for index, item in enumerate(plan["items"], 1):
                target = Path(item["destination"])
                source = Path(item["staged"]["path"])
                if target.parent != root or source.parent.parent != root:
                    raise _refuse("untrusted replacement path")
                if not _proof_equals_expected(source, item["staged"]):
                    raise _refuse("new physical DXF stage changed")
                original = item["original"]
                if original is None:
                    if target.exists() or target.is_symlink():
                        raise _refuse("unexpected new customer output")
                elif not _proof_equals_expected(target, original):
                    raise _refuse("original customer output changed")
                os.replace(source, target)
                _sync_directory(root)
                if not _proof_equals_expected(target, item["staged"]):
                    raise _refuse("renamed physical DXF proof invalid")
                result[item["physical_id"]] = target
                if after_replace is not None:
                    after_replace(index)
            self._change_state(request, "applying", "applied")
        except Exception as exc:
            # The journal and original backups remain, including every
            # replacement intent. Only explicit recovery may touch outputs.
            raise _refuse("partial replacement requires journal recovery") from exc
        return result

    def recover_rollback(self, request: Mapping[str, Any]) -> str:
        """Idempotently undo a partially committed batch after interruption.

        Refuse every unexpected customer byte BEFORE modifying any target.
        Preserve the immutable backup archive; restore via separately fsynced
        temp copies. Interrupted rollback may be repeated by the same owner.
        """
        state, plan = self._read(request)
        if state == "rolled_back":
            return "rolled_back"
        if state not in ("armed", "applying", "applied", "rolling_back"):
            raise _refuse("finished journal cannot be rolled back")
        root = self._verify_owner(request, plan)
        backup_dir = Path(plan["backup_directory"])
        if (backup_dir.is_symlink() or backup_dir.parent != root
                or list(_directory_identity(backup_dir)) != plan["backup_identity"]):
            raise _refuse("durable customer-original backup directory was replaced")
        # Validate every row and original backup first, before altering ANY
        # customer output. A third-party modification must not be overwritten.
        for item in plan["items"]:
            target = Path(item["destination"])
            if target.parent != root or target.is_symlink():
                raise _refuse("unsafe recovery target")
            original = item["original"]
            new = item["staged"]
            if original is not None:
                proof = item["backup"]
                src = Path(proof["path"])
                if src.parent != backup_dir or not _proof_equals_expected(src, proof):
                    raise _refuse("missing or corrupted immutable original backup")
                if not all(proof[k] == original[k] for k in ("sha256", "size", "mtime_ns")):
                    raise _refuse("wrong original customer DXF backup")
            if target.exists():
                if not (_proof_equals_expected(target, new)
                        or (original is not None and _proof_equals_expected(target, original))):
                    raise _refuse("unexpected customer change blocks recovery")
            elif original is not None:
                # Existing original disappearing is inconsistent with an
                # interrupted rename of a complete staged replacement.
                raise _refuse("customer original disappeared unexpectedly")
        if state != "rolling_back":
            self._change_state(request, state, "rolling_back")
        try:
            for item in plan["items"]:
                destination = Path(item["destination"])
                original = item["original"]
                new = item["staged"]
                if original is None:
                    if destination.exists() and _proof_equals_expected(destination, new):
                        destination.unlink()
                        _sync_directory(root)
                elif _proof_equals_expected(destination, new):
                    backup_file = Path(item["backup"]["path"])
                    fd, tmp = tempfile.mkstemp(prefix=".whd-w06-restore-", dir=str(root))
                    temp = Path(tmp)
                    try:
                        with os.fdopen(fd, "wb") as dst, backup_file.open("rb") as src:
                            shutil.copyfileobj(src, dst, length=1024 * 1024)
                            dst.flush()
                            os.fsync(dst.fileno())
                        original_stat = backup_file.stat()
                        os.utime(temp, ns=(original_stat.st_atime_ns, original["mtime_ns"]))
                        with temp.open("rb") as saved:
                            os.fsync(saved.fileno())
                        if not _proof_equals_expected(temp, original):
                            raise _refuse("temporary original restore differs")
                        if not _proof_equals_expected(destination, new):
                            raise _refuse("destination changed during recovery")
                        os.replace(temp, destination)
                        _sync_directory(root)
                    finally:
                        if temp.exists():
                            temp.unlink()
                    if not _proof_equals_expected(destination, original):
                        raise _refuse("restored customer output mismatch")
            # Recheck whole batch before atomically closing the journal and
            # releasing both output-directory and physical-identity leases.
            for item in plan["items"]:
                target = Path(item["destination"])
                old = item["original"]
                if old is None and (target.exists() or target.is_symlink()):
                    raise _refuse("new customer output survived rollback")
                if old is not None and not _proof_equals_expected(target, old):
                    raise _refuse("customer original not fully restored")
            client, job, op, digest = _identity(request)
            conn = self._ledger._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.execute(
                    """UPDATE batch_replace_journals SET state='rolled_back'
                       WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?
                         AND state='rolling_back'""",
                    (client, job, op, digest),
                )
                if cur.rowcount != 1:
                    raise _refuse("rollback journal lost original identity")
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
                raise _refuse("cannot commit durable rollback") from exc
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as exc:
            raise _refuse("rollback requires further trusted recovery") from exc
        return "rolled_back"
