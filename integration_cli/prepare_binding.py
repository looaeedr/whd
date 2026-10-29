# -*- coding: utf-8 -*-
"""Opaque, authenticated W-03 preparation binding; *not* a job journal.

A trusted Worker-owned installation secret is required. Never accept the key
from CADSplit's JSON body and never create a user-config/config.ini secret.
W-06 must own durable identity, key custody, and replay/collision semantics.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
from typing import Any, Mapping, Sequence

from integration_cli.prepare_evidence import (
    PrepareEvidenceError, _pure_json, evidence_digest,
)

_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TOKEN_RE = re.compile(r"^w3\.([0-9a-f]{64})\.([0-9a-f]{64})$")


def _validate_identity(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", f"invalid {name}")


def _binding_payload(
    *, client_installation_id: str, job_id: str, environment_fingerprint: str,
    prepared_items: Sequence[Mapping[str, Any]], coordinate_contract_revision: str = "1",
) -> dict[str, Any]:
    _validate_identity(client_installation_id, "client_installation_id")
    _validate_identity(job_id, "job_id")
    if not isinstance(environment_fingerprint, str) or not _HASH.fullmatch(environment_fingerprint):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "invalid environment fingerprint")
    if coordinate_contract_revision != "1" or not isinstance(prepared_items, (tuple, list)) or not prepared_items:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "unsupported Frame or empty prepared batch")
    if len(prepared_items) > 20:
        raise PrepareEvidenceError("WHD_BATCH_TOO_LARGE", "too many preparation items")
    checked = []
    seen_items, seen_physical, seen_frames = set(), set(), set()
    for part in prepared_items:
        if not isinstance(part, Mapping):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "invalid prepared item")
        item_id = part.get("item_id")
        physical = part.get("physical_part_id")
        frame = part.get("target_frame")
        if not isinstance(item_id, str) or not (1 <= len(item_id) <= 256):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "invalid item_id")
        _validate_identity(physical, "physical_part_id")
        if not isinstance(frame, Mapping):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "missing authoritative Frame")
        frame_id = frame.get("frame_id")
        # W-03 certifies only the WHD-issued front Door-local frame.
        # A caller-supplied arbitrary frame ID must not become a signed receipt.
        if frame_id != f"door:{physical}:front:local-v1":
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Frame identity is not WHD Door-local")
        if (item_id in seen_items or physical in seen_physical or frame_id in seen_frames):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "duplicate item or frame identity")
        seen_items.add(item_id)
        seen_physical.add(physical)
        seen_frames.add(frame_id)
        if frame.get("coordinate_contract_revision") != "1" or frame.get("units") != "mm":
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unsupported Frame units/revision")
        checked.append({
            "item_id": item_id,
            "physical_part_id": physical,
            "target_frame": _pure_json(frame),
            "locked_dimensions_mm": _pure_json(part.get("locked_dimensions_mm")),
            "source_document_sha256": part.get("source_document_sha256"),
            "source_part_ref": part.get("source_part_ref"),
        })
        if not isinstance(checked[-1]["source_part_ref"], str) or not checked[-1]["source_part_ref"]:
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "source part ownership required")
        if not isinstance(checked[-1]["locked_dimensions_mm"], dict) or not checked[-1]["locked_dimensions_mm"]:
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "locked dimensions required")
        if not isinstance(checked[-1]["source_document_sha256"], str) or not _HASH.fullmatch(checked[-1]["source_document_sha256"]):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "source evidence required")
    return {
        "binding_revision": "WHD_PREPARE_BINDING_V1",
        "protocol_version": "1.1.0",
        "client_installation_id": client_installation_id,
        "job_id": job_id,
        "environment_fingerprint": environment_fingerprint,
        "coordinate_contract_revision": coordinate_contract_revision,
        "items": checked,
    }


def create_preparation_binding(
    *, worker_key: bytes, client_installation_id: str, job_id: str,
    environment_fingerprint: str, prepared_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(worker_key, bytes) or len(worker_key) < 32:
        raise PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", "trusted installation key unavailable")
    payload = _binding_payload(
        client_installation_id=client_installation_id,
        job_id=job_id,
        environment_fingerprint=environment_fingerprint,
        prepared_items=prepared_items,
    )
    digest = evidence_digest(payload)
    tag = hmac.new(worker_key, ("WHD-W03-v1:" + digest).encode("ascii"), hashlib.sha256).hexdigest()
    item_digests = {
        item["item_id"]: evidence_digest({"binding_revision": "WHD_PREPARE_ITEM_V1",
            "environment_fingerprint": environment_fingerprint,
            "item": item})
        for item in payload["items"]
    }
    return {
        "prepare_token": f"w3.{digest}.{tag}",
        "preparation_digest": digest,
        "item_preparation_digests": item_digests,
        "environment_fingerprint": environment_fingerprint,
    }


def verify_preparation_binding(
    token: str, *, worker_key: bytes, client_installation_id: str, job_id: str,
    environment_fingerprint: str, prepared_items: Sequence[Mapping[str, Any]],
) -> None:
    if not isinstance(worker_key, bytes) or len(worker_key) < 32:
        raise PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", "trusted installation key unavailable")
    match = _TOKEN_RE.fullmatch(token) if isinstance(token, str) else None
    if match is None:
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "malformed prepare token")
    payload = _binding_payload(
        client_installation_id=client_installation_id,
        job_id=job_id,
        environment_fingerprint=environment_fingerprint,
        prepared_items=prepared_items,
    )
    digest = evidence_digest(payload)
    expected = hmac.new(worker_key, ("WHD-W03-v1:" + digest).encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(match.group(1), digest) or not hmac.compare_digest(match.group(2), expected):
        raise PrepareEvidenceError("WHD_PREPARE_STALE", "prepare binding does not match exact job, Frame or environment")
