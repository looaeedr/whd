# -*- coding: utf-8 -*-
"""W-03 trusted recheck seam before W-04 export render and before commit.

NOT a public CLI/verify operation, transaction journal, or manufacturing gate.
W-06 must retrieve both arguments from a durable *trusted* job record, own the
installation HMAC key and recheck job identity. Untrusted caller JSON must never
be supplied as the saved prepare record. W-04 must call this on both sides of
its canonical Save->Reload acceptance, with locks and atomicity owned by W-06.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import hmac
import rfc8785
from jsonschema import Draft202012Validator, ValidationError

from integration_cli.prepare_batch import prepare_trusted_door_batch
from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json


def revalidate_trusted_door_preparation(
    *, prepare_request: Mapping[str, Any], prepared_receipt: Mapping[str, Any],
    resource_root: Path, engine_commit: str, engine_sha256: str,
    build_id: str, worker_key: bytes,
) -> None:
    """Fail closed unless a saved prepare receipt still matches live WHD inputs.

    No output is emitted and this function does not authorize manufacturing.
    The caller is responsible for a trusted, durable, job-bound original
    request/receipt; the two objects MUST NOT be taken from export caller JSON.
    Re-running the owning preparation recreates current Policy, dimensions,
    Frame, Registry and baseline hashes and validates actual resource parsers.
    """
    if not isinstance(prepare_request, Mapping) or not isinstance(prepared_receipt, Mapping):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "trusted prepare record unavailable")
    try:
        # Validate the stored receipt independently: Python == treats True and 1
        # as equal, and a free-form receipt could otherwise hide extra fields.
        schema_path = Path(__file__).resolve().parent / "schemas" / "response_v1_1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(prepared_receipt)
        if (prepared_receipt.get("operation") != "prepare" or
                prepared_receipt.get("status") != "success" or
                prepared_receipt.get("manufacturing_verified") is not False):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "not a successful trusted prepare record")
        current = prepare_trusted_door_batch(
            prepare_request, resource_root=resource_root,
            engine_commit=engine_commit, engine_sha256=engine_sha256,
            build_id=build_id, worker_key=worker_key,
        )
        # Transport correlation is excluded, per W-02. Every other response
        # field, including each physical ID, frame, digest, and HMAC, is bound.
        def canonical_receipt(record: Mapping[str, Any]) -> bytes:
            return rfc8785.dumps(_pure_json({
                key: value for key, value in record.items() if key != "request_id"
            }))
        saved = canonical_receipt(prepared_receipt)
        live = canonical_receipt(current)
        if not hmac.compare_digest(saved, live):
            raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepared job, token or WHD resources changed")
    except PrepareEvidenceError as exc:
        if exc.code == "WHD_PREPARE_KEY_UNAVAILABLE":
            raise
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepare receipt cannot be revalidated") from exc
    except (ValidationError, rfc8785.CanonicalizationError, TypeError, ValueError,
            OSError, KeyError) as exc:
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepare receipt cannot be revalidated") from exc
