# -*- coding: utf-8 -*-
"""Private, preprovisioned Windows installation custody for WHD-Engine.exe.

The regular CADSplit CLI cannot provision this record. This adapter reads
ONLY a Worker-owned, DPAPI-key-HMAC-authenticated record, then binds its
package resources / original DXF paths / output directory to private dispatch.
Not a public manufacturing authorization or Gate A certification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.worker_key_custody import (
    _store_root, _check_existing, _check_ancestors, load_installation_key,
)
from integration_cli.private_worker_dispatch import TrustedWorkerExecution
from integration_cli.job_identity_ledger import _identity, _json, _unsafe_windows_path

_FILE = "trusted_sources_v1.json"
_PREFIX = b"WHD-W06-TRUSTED-INSTALL-CONTEXT-v1\x00"


def _deny(message="trusted installed Worker context unavailable"):
    raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", message)


def _trusted_dir(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or _unsafe_windows_path(value):
        _deny()
    _check_ancestors(value)
    if not value.is_dir():
        _deny()
    return value


def _trusted_file(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or _unsafe_windows_path(value):
        _deny()
    _check_ancestors(value.parent)
    _check_existing(value, directory=False)
    return value


def _assert_separate_custody(
    store: Path, output: Path, source_documents: Mapping[str, Path],
) -> None:
    """Never provision customer originals inside a Worker-writable tree.

    Durable DXF commits write into output, while SQLite/journals write into
    store.  An overlapping tree (including a source file *under* either)
    is not a safe installation authority even if its path is HMAC sealed.
    Directory reparse aliases are refused by the trusted path readers first.
    """
    try:
        store_real = store.resolve(strict=True)
        output_real = output.resolve(strict=True)
        if (store_real == output_real or store_real in output_real.parents
                or output_real in store_real.parents):
            _deny("Worker state and customer output locations overlap")
        for original in source_documents.values():
            source_real = original.resolve(strict=True)
            if output_real in source_real.parents or store_real in source_real.parents:
                _deny("original source DXF is inside a Worker writable directory")
    except OSError as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_STORE_UNAVAILABLE", "installed path custody cannot be verified",
        ) from exc


def _signed_payload(key: bytes, payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(key, _PREFIX + raw, hashlib.sha256).hexdigest()


def provision_private_installation(
    installation_id: str, *, store_root: Path, output_dir: Path,
    source_documents: dict[str, Path], expected_engine_sha256: str,
) -> None:
    """Trusted installer-only API; NEVER exposed by EXE CLI or wire JSON.

    Installs one immutable source/output custody mapping. Reprovisioning and
    untrusted paths are rejected rather than silently changing job authority.
    """
    folder, _ = _store_root(installation_id, initialize=False)
    key = load_installation_key(installation_id)
    if (not isinstance(expected_engine_sha256, str) or len(expected_engine_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_engine_sha256)):
        _deny()
    store = _trusted_dir(store_root)
    output = _trusted_dir(output_dir)
    if not isinstance(source_documents, dict) or not source_documents:
        _deny()
    mapping = {}
    for item, src in source_documents.items():
        if not isinstance(item, str) or not item or len(item) > 128:
            _deny()
        mapping[item] = _trusted_file(src)
    _assert_separate_custody(store, output, mapping)
    payload = {
        "schema": "whd-private-install-custody-v1",
        "store_root": str(store),
        "output_dir": str(output),
        "source_documents": {item: str(path) for item, path in mapping.items()},
        "engine_sha256": expected_engine_sha256,
    }
    record = {"payload": payload, "hmac": _signed_payload(key, payload)}
    destination = folder / _FILE
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "installation already provisioned or not writable") from exc
    with os.fdopen(fd, "wb") as output:
        output.write(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())


def load_private_execution(installation_id: str, *, engine_sha256: str) -> TrustedWorkerExecution:
    """Reopen pinned installer custody and validate actual EXE hash."""
    folder, _ = _store_root(installation_id, initialize=False)
    key = load_installation_key(installation_id)
    path = folder / _FILE
    _check_existing(path, directory=False)
    try:
        if path.stat().st_size > 256 * 1024:
            _deny()
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or set(record) != {"payload", "hmac"}:
            _deny()
        data, tag = record["payload"], record["hmac"]
        if not isinstance(data, dict) or not isinstance(tag, str):
            _deny()
        if (not hmac.compare_digest(tag, _signed_payload(key, data))
                or set(data) != {"schema","store_root","output_dir","source_documents","engine_sha256"}
                or data["schema"] != "whd-private-install-custody-v1"
                or not hmac.compare_digest(data["engine_sha256"], engine_sha256)):
            _deny()
        sources = data["source_documents"]
        if not isinstance(sources, dict) or not sources:
            _deny()
        store = _trusted_dir(Path(data["store_root"]))
        output = _trusted_dir(Path(data["output_dir"]))
        mapping = {item: _trusted_file(Path(path)) for item, path in sources.items()}
        _assert_separate_custody(store, output, mapping)
        return TrustedWorkerExecution(
            resource_root=(Path(sys._MEIPASS) if getattr(sys, "frozen", False)
                           else Path(__file__).resolve().parents[1]),
            store_root=store,
            output_dir=output,
            source_documents=mapping,
            worker_key=key,
            engine_sha256=engine_sha256,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "installed Worker custody is invalid") from exc


# Separate domain from the installation mapping signature. A provisioning
# record is NOT authorization to manufacture arbitrary later jobs.
_JOB_PREFIX = b"WHD-W06-INSTALLED-JOB-APPROVAL-v1\x00"


def _job_approval_file(folder: Path, request: Mapping[str, Any]) -> Path:
    client, job, operation, _ = _identity(request)
    opaque = hashlib.sha256(
        _json([client, job, operation]).encode("utf-8")
    ).hexdigest()
    return folder / ("approved-" + opaque + ".json")


def _approval_mac(key: bytes, identity: list[str]) -> str:
    return hmac.new(
        key, _JOB_PREFIX + _json(identity).encode("utf-8"), hashlib.sha256,
    ).hexdigest()


def authorize_private_job(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> None:
    """Trusted installation owner ONLY, never an EXE command/JSON switch.

    Requires the complete valid canonical request and the already sealed
    installation, then exclusively creates one immutable HMAC-bound approval.
    It never initiates a Prepare/Export or writes a customer DXF.
    """
    from jsonschema import Draft202012Validator, ValidationError
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    root = context.resource_root
    try:
        schema = json.loads(
            (root / "integration_cli" / "schemas" / "request_v1_1.schema.json"
             ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(request)
    except (OSError, ValueError, TypeError, ValidationError) as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "private job approval schema invalid") from exc
    identity = list(_identity(request))
    if request["operation"] == "export":
        if (request["output"]["directory"] != str(context.output_dir)
                or not all(
                    item["item_id"] in context.source_documents
                    for item in request["items"]
                )):
            raise PrepareEvidenceError(
                "WHD_SOURCE_UNVERIFIED", "job outside sealed source/output authority",
            )
    folder, _ = _store_root(installation_id, initialize=False)
    ticket = _job_approval_file(folder, request)
    payload = {"schema": "whd-private-job-approval-v1", "identity": identity}
    raw = (_json({"payload": payload, "hmac": _approval_mac(context.worker_key, identity)})
           + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(ticket, flags, 0o600)
    except OSError as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_ID_CONFLICT", "installed job already approved or inaccessible",
        ) from exc
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def load_private_authorized_execution(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> TrustedWorkerExecution:
    """Verify exact trusted job approval before private packaged EXE dispatch.

    Another installed job cannot be substituted, even with the same client
    installation ID or a manually recomputed canonical wire digest.
    """
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    folder, _ = _store_root(installation_id, initialize=False)
    approved_path = _job_approval_file(folder, request)
    try:
        _check_existing(approved_path, directory=False)
        if not 1 <= approved_path.stat().st_size <= 4096:
            _deny("private job approval size invalid")
        entry = json.loads(approved_path.read_text(encoding="utf-8"))
        identity = list(_identity(request))
        expected = {"schema": "whd-private-job-approval-v1", "identity": identity}
        if (not isinstance(entry, dict) or set(entry) != {"payload", "hmac"}
                or entry["payload"] != expected
                or not isinstance(entry["hmac"], str)
                or not hmac.compare_digest(
                    entry["hmac"], _approval_mac(context.worker_key, identity),
                )):
            _deny("private job approval is invalid")
        return replace(context, approved_request_identity=tuple(identity))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_STORE_UNAVAILABLE", "private job not approved or invalid",
        ) from exc


# An Export approval never permits customer-file rollback. Only the trusted
# installation owner may explicitly seal a SEPARATE recovery intent, bound
# to the exact original Export digest and existing uncommitted journal.
_RECOVERY_PREFIX = b"WHD-W06-INSTALLED-ROLLBACK-APPROVAL-v1\x00"


def _recovery_approval_file(folder: Path, request: Mapping[str, Any]) -> Path:
    client, job, operation, _ = _identity(request)
    opaque = hashlib.sha256(
        _json(["recover-rollback", client, job, operation]).encode("utf-8")
    ).hexdigest()
    return folder / ("recover-" + opaque + ".json")


def _recovery_mac(key: bytes, identity: list[str]) -> str:
    return hmac.new(
        key, _RECOVERY_PREFIX + _json(identity).encode("utf-8"), hashlib.sha256,
    ).hexdigest()


def authorize_private_recovery(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> None:
    """Installer-owner only: approve one immutable, pending Export rollback.

    This does not restore, regenerate, or modify any customer file.
    An ordinary Export job approval is NOT sufficient to authorize rollback.
    """
    from jsonschema import Draft202012Validator, ValidationError
    from integration_cli.private_worker_dispatch import _validate_context
    from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    try:
        schema = json.loads(
            (context.resource_root / "integration_cli" / "schemas" /
             "request_v1_1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(request)
    except (OSError, ValueError, TypeError, ValidationError) as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "rollback request schema invalid") from exc
    if request.get("operation") != "export":
        raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "rollback requires original Export")
    _validate_context(context, request)
    journal = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(context.store_root))
    state, plan = journal._read(request)
    if state not in ("armed", "applying", "applied", "rolling_back"):
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "no unfinished Export to recover")
    journal._verify_owner(request, plan)
    identity = list(_identity(request))
    folder, _ = _store_root(installation_id, initialize=False)
    ticket = _recovery_approval_file(folder, request)
    payload = {"schema": "whd-private-rollback-approval-v1", "identity": identity}
    raw = (_json({"payload": payload, "hmac": _recovery_mac(context.worker_key, identity)})
           + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(ticket, flags, 0o600)
    except OSError as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_ID_CONFLICT", "recovery already approved or inaccessible",
        ) from exc
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def load_private_recovery_execution(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> TrustedWorkerExecution:
    """Verify a distinct HMAC-sealed rollback approval; fail before disk writes."""
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    folder, _ = _store_root(installation_id, initialize=False)
    ticket = _recovery_approval_file(folder, request)
    try:
        _check_existing(ticket, directory=False)
        if not 1 <= ticket.stat().st_size <= 4096:
            _deny("recovery ticket size invalid")
        entry = json.loads(ticket.read_text(encoding="utf-8"))
        identity = list(_identity(request))
        expected = {"schema": "whd-private-rollback-approval-v1", "identity": identity}
        if (not isinstance(entry, dict) or set(entry) != {"payload", "hmac"}
                or entry["payload"] != expected
                or not isinstance(entry["hmac"], str)
                or not hmac.compare_digest(
                    entry["hmac"], _recovery_mac(context.worker_key, identity),
                )):
            _deny("private rollback approval invalid")
        return replace(context, approved_request_identity=tuple(identity))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_STORE_UNAVAILABLE", "private rollback not approved or invalid",
        ) from exc


# Cancellation has a different authority from Export and rollback. An
# installed Export approval cannot manufacture a cancellation ticket.
_CANCEL_PREFIX = b"WHD-W06-INSTALLED-CANCEL-APPROVAL-v1\x00"


def _cancel_approval_file(folder: Path, request: Mapping[str, Any]) -> Path:
    client, job, operation, _ = _identity(request)
    key = hashlib.sha256(
        _json(["request-cancel", client, job, operation]).encode("utf-8")
    ).hexdigest()
    return folder / ("cancel-" + key + ".json")


def _cancel_mac(key: bytes, identity: list[str]) -> str:
    return hmac.new(
        key, _CANCEL_PREFIX + _json(identity).encode("utf-8"), hashlib.sha256,
    ).hexdigest()


def authorize_private_cancel(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> None:
    """Separate installer-only approval, only for an existing cancellable job.

    Approving cancellation does not cancel the job; the packaged Worker
    must still verify this ticket and race cancellation with journal arm.
    """
    from jsonschema import Draft202012Validator, ValidationError
    from integration_cli.private_worker_dispatch import _validate_context
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    try:
        schema = json.loads(
            (context.resource_root / "integration_cli" / "schemas" /
             "request_v1_1.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(request)
    except (OSError, ValueError, TypeError, ValidationError) as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "private cancellation schema invalid") from exc
    _validate_context(context, request)
    client, job, operation, digest = _identity(request)
    ledger = DurableJobIdentityLedger(context.store_root)
    with ledger._connect() as conn:
        jobrow = conn.execute(
            """SELECT request_digest,state FROM jobs
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, operation),
        ).fetchone()
        replacement = conn.execute(
            """SELECT 1 FROM batch_replace_journals
               WHERE client_id=? AND job_id=? AND operation=?""",
            (client, job, operation),
        ).fetchone()
    if jobrow != (digest, "started") or replacement is not None:
        raise PrepareEvidenceError(
            "WHD_JOB_RECOVERY_REQUIRED", "job is not safely cancellable",
        )
    identity = [client, job, operation, digest]
    folder, _ = _store_root(installation_id, initialize=False)
    ticket = _cancel_approval_file(folder, request)
    payload = {"schema": "whd-private-cancel-approval-v1", "identity": identity}
    raw = (_json({"payload": payload, "hmac": _cancel_mac(context.worker_key, identity)})
           + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(ticket, flags, 0o600)
    except OSError as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_ID_CONFLICT", "cancel already approved or inaccessible",
        ) from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def load_private_cancel_execution(
    installation_id: str, request: Mapping[str, Any], *, engine_sha256: str,
) -> TrustedWorkerExecution:
    """Verify distinct HMAC-sealed cancel authority, not Export approval."""
    context = load_private_execution(installation_id, engine_sha256=engine_sha256)
    folder, _ = _store_root(installation_id, initialize=False)
    ticket = _cancel_approval_file(folder, request)
    try:
        _check_existing(ticket, directory=False)
        if not 1 <= ticket.stat().st_size <= 4096:
            _deny("cancel ticket size invalid")
        entry = json.loads(ticket.read_text(encoding="utf-8"))
        identity = list(_identity(request))
        expected = {"schema": "whd-private-cancel-approval-v1", "identity": identity}
        if (not isinstance(entry, dict) or set(entry) != {"payload", "hmac"}
                or entry["payload"] != expected
                or not isinstance(entry["hmac"], str)
                or not hmac.compare_digest(
                    entry["hmac"], _cancel_mac(context.worker_key, identity),
                )):
            _deny("private cancellation approval invalid")
        return replace(context, approved_request_identity=tuple(identity))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_STORE_UNAVAILABLE", "private cancellation not approved or invalid",
        ) from exc
