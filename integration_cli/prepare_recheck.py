# -*- coding: utf-8 -*-
"""#2378 W-03 export-time prepare recheck, not a public export handler.

The trusted_prepare_request and trusted_prepare_response are **Worker-owned
persisted state**, never values accepted from an external CADSplit JSON request.
W-06 must provide durable, authenticated custody and serialize cross-process
jobs. This guard performs no output writes, manufactures no DXF, and does not
validate feature geometry (owned by W-04). Call it again before final commit
unless a proven immutable snapshot is held throughout export.
"""
from __future__ import annotations

import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError

from integration_cli.prepare_batch import prepare_trusted_door_batch
from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json
from integration_cli.feature_preflight import validate_wire_features_against_prepared_frame
from integration_cli.source_circle_verification import verify_trusted_original_dxf_circles
from integration_cli.request_canonical import require_matching_wire_request_digest


def _stale_if_different(actual: Any, expected: Any, what: str) -> None:
    if _pure_json(actual) != _pure_json(expected):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", f"prepared {what} changed")


def _compare_token(actual: Any, expected: Any, what: str) -> None:
    if (not isinstance(actual, str) or not isinstance(expected, str) or
            not hmac.compare_digest(actual, expected)):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", f"prepared {what} changed")


def recheck_trusted_door_export(
    trusted_prepare_request: Mapping[str, Any],
    trusted_prepare_response: Mapping[str, Any],
    export_request: Mapping[str, Any],
    *,
    resource_root: Path,
    engine_commit: str,
    engine_sha256: str,
    build_id: str,
    worker_key: bytes,
    source_documents: Mapping[str, Path] | None = None,
) -> None:
    """Fail entire batch on any stale binding before W-04 stages outputs.

    The *only* permissible prepare authority is the original Worker-persisted
    request+receipt, authenticated by the current Worker-owned HMAC key.
    Neither token nor claimed environment in an export body is sufficient by
    itself. Output/transaction/feature correctness is a separate W-04/W-06 gate.
    This check also must run immediately before commit.
    """
    if not all(isinstance(obj, Mapping) for obj in
               (trusted_prepare_request, trusted_prepare_response, export_request)):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "trusted original prepare record missing")

    schema_dir = Path(__file__).resolve().parent / "schemas"
    for schema_file, obj in (
        ("request_v1_1.schema.json", trusted_prepare_request),
        ("response_v1_1.schema.json", trusted_prepare_response),
        ("request_v1_1.schema.json", export_request),
    ):
        schema = json.loads((schema_dir / schema_file).read_text(encoding="utf-8"))
        try:
            Draft202012Validator(schema).validate(obj)
        except ValidationError as exc:
            raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "invalid W-03 versioned request/receipt") from exc

    if (trusted_prepare_request.get("operation") != "prepare" or
            trusted_prepare_response.get("operation") != "prepare" or
            trusted_prepare_response.get("status") != "success" or
            export_request.get("operation") != "export" or
            trusted_prepare_request.get("protocol_version") != "1.1.0" or
            export_request.get("protocol_version") != "1.1.0"):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "wrong operation/prepare record")

    # Each semantic payload is separately canonicalized, and its own digest
    # must match. request_id changes for a timeout retry are excluded.
    require_matching_wire_request_digest(trusted_prepare_request)
    require_matching_wire_request_digest(export_request)

    prepare_items = trusted_prepare_request["items"]
    export_items = export_request["items"]
    receipt_items = trusted_prepare_response.get("items")
    if not isinstance(receipt_items, list) or not (
        len(prepare_items) == len(export_items) == len(receipt_items)
    ):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepared batch length/order changed")
    for field in ("client_installation_id", "job_id"):
        _stale_if_different(export_request.get(field), trusted_prepare_request.get(field), field)
        _stale_if_different(trusted_prepare_response.get(field), trusted_prepare_request.get(field), field)
    _compare_token(trusted_prepare_response.get("request_digest"),
                   trusted_prepare_request.get("request_digest"), "request digest")
    _compare_token(export_request.get("prepare_token"),
                   trusted_prepare_response.get("prepare_token"), "prepare token")
    _compare_token(export_request.get("environment_fingerprint_expected"),
                   trusted_prepare_response.get("environment_fingerprint"), "environment")

    for prepared, exported, result in zip(prepare_items, export_items, receipt_items):
        for field in ("item_id", "part", "source_document_sha256"):
            _stale_if_different(exported.get(field), prepared.get(field), f"item {field}")
        _stale_if_different(result.get("item_id"), prepared.get("item_id"), "receipt item identity")
        _stale_if_different(exported.get("physical_part_id"),
                           result.get("physical_part_id"), "physical part identity")
        _compare_token(exported.get("preparation_digest"),
                       result.get("preparation_digest"), "per-item preparation digest")
        frame_rows = result.get("target_frames")
        if not isinstance(frame_rows, list) or len(frame_rows) != 1:
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "unverified target face set")
        expected_frames = [frame_rows[0].get("frame_id")] if isinstance(frame_rows[0], Mapping) else []
        _stale_if_different(exported.get("target_frame_ids"), expected_frames, "target frame IDs")
        for feature in exported.get("features", ()):
            if not isinstance(feature, Mapping):
                raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "invalid exported feature")
            if (feature.get("target_frame_id") != expected_frames[0] or
                    feature.get("face_role") != frame_rows[0].get("face_role") or
                    feature.get("viewed_from") != frame_rows[0].get("viewed_from") or
                    feature.get("units") != frame_rows[0].get("units")):
                raise PrepareEvidenceError("WHD_PREPARE_STALE", "feature target frame changed")
        validate_wire_features_against_prepared_frame(
            exported.get("features", ()), frame_rows[0],
        )
        # Worker-owned source path is never accepted from wire JSON. Missing
        # custody fails closed rather than trusting feature/source assertions.
        if exported.get("features"):
            source = (source_documents.get(prepared["item_id"])
                      if isinstance(source_documents, Mapping) else None)
            verify_trusted_original_dxf_circles(
                exported["features"], source_path=source,
                expected_document_sha256=prepared["source_document_sha256"],
            )

    # Re-enter the WHD manufacturing owners, real parsers and content hashes
    # for this exact original batch. This is not a version-string comparison.
    try:
        fresh = prepare_trusted_door_batch(
            trusted_prepare_request, resource_root=resource_root,
            engine_commit=engine_commit, engine_sha256=engine_sha256,
            build_id=build_id, worker_key=worker_key,
        )
    except PrepareEvidenceError as exc:
        # A resource that existed at prepare and is now missing, corrupt,
        # symlinked or no longer certified is an export-time stale snapshot.
        # Do not degrade this into a new prepare or use last-known-good data.
        if exc.code in {
            "WHD_RESOURCE_UNVERIFIED", "WHD_RESOURCE_PATH_INVALID",
            "WHD_FRAME_UNVERIFIED", "WHD_PREPARE_INPUT_INVALID",
        }:
            raise PrepareEvidenceError(
                "WHD_PREPARE_STALE", "prepared WHD resource or Frame is no longer verifiable"
            ) from exc
        raise
    for field in ("engine_commit", "build_id"):
        _stale_if_different(trusted_prepare_response.get(field), fresh.get(field), field)
    for field in ("prepare_token", "environment_fingerprint"):
        _compare_token(trusted_prepare_response.get(field), fresh.get(field), field)
    for earlier, current in zip(receipt_items, fresh["items"]):
        for field in ("physical_part_id", "item_id", "preparation_digest", "target_frames"):
            _stale_if_different(earlier.get(field), current.get(field), f"receipt {field}")
    # Protect all remaining receipt assertions too (status flags, required
    # source evidence, scope and diagnostics). A transport-only correlation
    # request_id may differ on authenticated timeout readback.
    immutable = lambda value: {k: v for k, v in value.items() if k != "request_id"}
    _stale_if_different(
        immutable(trusted_prepare_response), immutable(fresh),
        "complete immutable prepare receipt",
    )
