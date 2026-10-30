# -*- coding: utf-8 -*-
"""Gate A public three-command adapter, gated by signed installed job authority.

Only actual packaged Windows EXEs with a provisioned, *separately approved*
immutable job may use the certified v1.1 public prepare/export response.
Never take source directories, Worker state, signing keys or provenance from
the public wire. The legacy source-only public CLI remains fail-closed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError

from integration_cli.job_identity_ledger import (
    DurableJobIdentityLedger, _file_proof, _identity,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.private_worker_dispatch import (
    execute_private_worker, read_private_worker_immutable_result,
)
from integration_cli.private_worker_installation import (
    load_private_authorized_execution,
)
from integration_cli.request_canonical import require_matching_wire_request_digest


def _reject(message: str) -> None:
    raise PrepareEvidenceError("WHD_JOB_RECOVERY_REQUIRED", message)


def _public_export_receipt(
    request: Mapping[str, Any], context, private: Mapping[str, Any],
    *, engine_commit: str, build_id: str,
) -> dict[str, Any]:
    """Certify physical journal-backed FinalScene results, NOT a private flag.

    W-04's *only* durable commit callback is executed after canonical
    FinalScene -> staging -> DXF Save/Reload and rechecking W-03 original
    source, Feature, Registry, baseline, Frame and token. This path demands
    its durable committed journal and every physical file proof before
    publishing an external manufacturing success. No re-render or writes.
    """
    if (not isinstance(private, Mapping)
            or private.get("status") != "success"
            or private.get("manufacturing_verified") is not False):
        _reject("unverified private Export state")
    original = read_private_worker_immutable_result(request, context)
    if original != private:
        _reject("immutable result differs from trusted Worker export")
    client, job, op, digest = _identity(request)
    if op != "export" or request.get("transaction_mode") != "all_or_nothing":
        _reject("public manufacturing requires all-or-nothing journal")
    ledger = DurableJobIdentityLedger(context.store_root)
    with ledger._connect() as conn:
        saved = conn.execute(
            """SELECT artifact_json FROM jobs
               WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?
                 AND state='committed'""",
            (client, job, op, digest),
        ).fetchone()
        journal = conn.execute(
            """SELECT state,plan_json,plan_sha256 FROM batch_replace_journals
               WHERE client_id=? AND job_id=? AND operation=? AND request_digest=?""",
            (client, job, op, digest),
        ).fetchone()
    if saved is None or journal is None or journal[0] != "committed":
        _reject("trusted W-04 transaction has no completed physical journal")
    try:
        if not hmac.compare_digest(
            hashlib.sha256(journal[1].encode("utf-8")).hexdigest(), journal[2],
        ):
            raise ValueError("journal checksum mismatch")
        plan = json.loads(journal[1])
        proofs = json.loads(saved[0])
        by_item = {r["physical_part_id"]: r["path"] for r in private["items"]}
        expected = {r["physical_part_id"] for r in request["items"]}
        planned = {r["physical_id"]: r for r in plan["items"]}
        if (not 1 <= len(expected) <= 20 or len(private["items"]) != len(expected)
                or len(by_item) != len(expected) or len(request["items"]) != len(expected)
                or set(by_item) != expected or set(proofs) != expected
                or set(planned) != expected):
            raise ValueError("incomplete physical batch inventory")
        for physical in expected:
            path = by_item[physical]
            proof = proofs[physical]
            intent = planned[physical]
            if (proof["path"] != path or intent["destination"] != path
                    or any(proof[k] != intent["staged"][k]
                           for k in ("sha256", "size", "mtime_ns"))
                    or _file_proof(Path(path)) != proof
                    or Path(path).parent != context.output_dir):
                raise ValueError("DXF differs from W-04 attested output")
    except (KeyError, ValueError, TypeError, IndexError, OSError) as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_RECOVERY_REQUIRED", "DXF or canonical journal cannot be certified",
        ) from exc

    rows = []
    for item in request["items"]:
        kind = item["part"]["kind"]
        physical = item["physical_part_id"]
        if kind not in {
            "door", "indicator_small_door", "indicator_box",
            "end_cap_head", "end_cap_tail",
        }:
            _reject("part has no attested W-04 production owner")
        proof = proofs[physical]
        rows.append({
            "item_id": item["item_id"],
            "status": "committed",
            "physical_part_id": physical,
            "production_scope": "single_part",
            "manufacturing_verified": True,
            "parts": [{
                "physical_part_id": physical,
                "part_kind": kind,
                "output_path": proof["path"],
                "output_sha256": proof["sha256"],
                "save_reload_verified": True,
                "manufacturing_verified": True,
                "exporter_name": "WHD canonical FinalScene",
                "used_baseline": True,
            }],
            "diagnostics": [],
        })
    return {
        "protocol_version": "1.1.0",
        "operation": "export",
        "client_installation_id": client,
        "request_id": request["request_id"],
        "job_id": job,
        "request_digest": digest,
        "status": "success",
        "engine_commit": engine_commit,
        "build_id": build_id,
        "environment_fingerprint": request["environment_fingerprint_expected"],
        "transaction_mode": "all_or_nothing",
        "manufacturing_verified": True,
        "items": rows,
        "diagnostics": [],
    }


def execute_public_installed(
    operation: str, request: Mapping[str, Any], *,
    engine_commit: str, build_id: str, engine_sha256: str,
    resource_root: Path,
) -> dict[str, Any]:
    """Public wire, private security custody, WHD-only manufacturing authority."""
    if operation not in ("prepare", "export") or request.get("operation") != operation:
        raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "public operation mismatch")
    definition = json.loads(
        (resource_root / "integration_cli" / "schemas" /
         "request_v1_1.schema.json").read_text(encoding="utf-8")
    )
    try:
        Draft202012Validator(definition).validate(request)
    except ValidationError as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "invalid public v1.1 request") from exc
    require_matching_wire_request_digest(request)
    # 'client_installation_id' only SELECTS a protected installation;
    # knowing the string grants neither source/output authority nor any job.
    context = load_private_authorized_execution(
        request["client_installation_id"], request,
        engine_sha256=engine_sha256,
    )
    result = execute_private_worker(
        operation, request, context, engine_commit=engine_commit, build_id=build_id,
    )
    if operation == "export":
        result = _public_export_receipt(
            request, context, result, engine_commit=engine_commit, build_id=build_id,
        )
    response_schema = json.loads(
        (resource_root / "integration_cli" / "schemas" /
         "response_v1_1.schema.json").read_text(encoding="utf-8")
    )
    try:
        Draft202012Validator(response_schema).validate(result)
    except ValidationError as exc:
        raise PrepareEvidenceError(
            "WHD_JOB_RECOVERY_REQUIRED", "WHD cannot certify public result schema",
        ) from exc
    return result
