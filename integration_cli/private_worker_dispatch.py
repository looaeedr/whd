# -*- coding: utf-8 -*-
"""#2375 W-03/W-04/W-06 private execution adapter for the real W-01 Worker.

Not a public CADSplit command, installer or manufacturing certification.
Only an in-process trusted installation owner can provide the context.
The public WHD-Engine CLI never creates or accepts this context from JSON,
command arguments or environment variables. Private export returns the
unpublished W-06 ledger receipt, NOT a certified v1.1 public success.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError
import json

from integration_cli.job_identity_ledger import DurableJobIdentityLedger, _identity
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import require_matching_wire_request_digest


@dataclass(frozen=True)
class TrustedWorkerExecution:
    """Private in-process custody; no field is accepted on the wire.

    The trusted installation owner must separately verify the packaged build,
    load the DPAPI HMAC key, and supply preexisting source/output directories.
    This object is deliberately not serializable as a public CLI parameter.
    """
    resource_root: Path
    store_root: Path
    output_dir: Path | None
    source_documents: Mapping[str, Path]
    worker_key: bytes
    engine_sha256: str
    # The packaged private EXE may execute ONLY a preapproved immutable job.
    # In-process native integration tests/owners still supply their own
    # private execution context and do not use this CLI admission field.
    approved_request_identity: tuple[str, str, str, str] | None = None


def _validate_context(context: TrustedWorkerExecution, request: Mapping[str, Any]) -> None:
    if not isinstance(context, TrustedWorkerExecution):
        raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "trusted Worker context missing")
    if context.approved_request_identity is not None:
        # Rechecked AFTER the CLI's second read of --request. An attacker
        # cannot swap request bytes between the admission read and dispatch
        # to execute a different, unapproved manufacturing job.
        if (not isinstance(context.approved_request_identity, tuple)
                or len(context.approved_request_identity) != 4
                or context.approved_request_identity != _identity(request)):
            raise PrepareEvidenceError(
                "WHD_JOB_ID_CONFLICT", "installed Worker request differs from admission approval",
            )
    if (not isinstance(context.worker_key, bytes) or len(context.worker_key) < 32
            or not isinstance(context.engine_sha256, str) or len(context.engine_sha256) != 64):
        raise PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", "Worker signing/build identity missing")
    for root in (context.resource_root, context.store_root):
        if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
            raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "trusted Worker source/store unavailable")
    if not isinstance(context.source_documents, Mapping):
        raise PrepareEvidenceError("WHD_SOURCE_UNVERIFIED", "Worker source custody unavailable")
    if request["operation"] == "export":
        target = context.output_dir
        if not isinstance(target, Path) or target.is_symlink() or not target.is_dir():
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "trusted Worker output unavailable")
        if request["output"]["directory"] != str(target):
            # Wire output cannot redirect the Worker to another file system
            # destination or supply an alternate path spelling.
            raise PrepareEvidenceError("WHD_OUTPUT_PATH_INVALID", "wire output differs from trusted directory")
        if not all(isinstance(item_id, str) and isinstance(path, Path)
                   for item_id, path in context.source_documents.items()):
            raise PrepareEvidenceError("WHD_SOURCE_UNVERIFIED", "untrusted original source path")


def execute_private_worker(
    operation: str,
    request: Mapping[str, Any],
    context: TrustedWorkerExecution,
    *,
    engine_commit: str,
    build_id: str,
) -> dict[str, Any]:
    """One actual Worker dispatch: WHD W-03 -> W-06 -> W-04 -> durable DXF.

    This is *only* called from W-01 with an in-process trusted context, never
    by the public CLI. The existing W-01 CLI has exactly three commands and
    manufactures nothing until Gate A, including when called as an EXE.
    """
    if operation not in ("prepare", "export") or not isinstance(request, Mapping):
        raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "unsupported private Worker operation")
    if request.get("operation") != operation:
        raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "Worker operation mismatch")
    from integration_cli.cadsplit_worker import SCHEMA_ROOT
    schema = json.loads((SCHEMA_ROOT / "request_v1_1.schema.json").read_text(encoding="utf-8"))
    try:
        Draft202012Validator(schema).validate(request)
    except ValidationError as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "invalid versioned Worker request") from exc
    require_matching_wire_request_digest(request)
    _identity(request)
    _validate_context(context, request)
    ledger = DurableJobIdentityLedger(context.store_root)
    if operation == "prepare":
        # Source/document mapping is not consulted for W-03 prepare; actual
        # W-03 resource/Frame and DPAPI-owned HMAC evidence remain authoritative.
        return ledger.prepare_and_persist(
            request, resource_root=context.resource_root,
            engine_commit=engine_commit, engine_sha256=context.engine_sha256,
            build_id=build_id, worker_key=context.worker_key,
        )

    # Never trust original Prepare bytes or response copied into Export JSON.
    # This read authenticates both using the installation-owned HMAC.
    original, receipt = ledger.recheck_persisted_prepare_for_export(
        request, resource_root=context.resource_root,
        engine_commit=engine_commit, engine_sha256=context.engine_sha256,
        build_id=build_id, worker_key=context.worker_key,
        source_documents=context.source_documents,
    )

    # A successful replay may return only the original immutable, physically
    # re-attested result. Do not call W-04 a second time or rewrite final DXF.
    with ledger._connect() as conn:
        existing = conn.execute(
            """SELECT 1 FROM jobs
               WHERE client_id=? AND job_id=? AND operation='export'""",
            (request["client_installation_id"], request["job_id"]),
        ).fetchone()
    if existing is not None:
        replay = ledger.claim(request)
        if replay.state != "committed" or replay.result is None:
            raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "unfinished export cannot be rendered again")
        return replay.result

    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    save_trusted_door_circle_finalscene_batch(
        original, receipt, request,
        source_documents=context.source_documents,
        resource_root=context.resource_root,
        output_dir=context.output_dir,
        engine_commit=engine_commit,
        engine_sha256=context.engine_sha256,
        build_id=build_id,
        worker_key=context.worker_key,
        overwrite=request["output"]["overwrite"],
        durable_ledger=ledger,
    )
    final = ledger.claim(request)
    if final.state != "committed" or final.result is None:
        raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", "W-06 committed receipt missing")
    # This internal result has manufacturing_verified=False by design. Do not
    # adapt it to the public response_v1_1 'success' schema until Gate A.
    return final.result
