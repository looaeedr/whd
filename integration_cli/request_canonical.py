# -*- coding: utf-8 -*-
"""Exact RFC 8785 semantic request identity, independent of transport request_id.

The current W-01 CLI does NOT enable manufacturing; this is the W-03/W-06
request identity owner and must be used before any authenticated preparation.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Mapping

import rfc8785

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_HASH = re.compile(r"^[a-f0-9]{64}$")


def compute_wire_request_digest(request: Mapping[str, Any]) -> str:
    if not isinstance(request, Mapping):
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "request must be JSON object")
    # Only these two transport fields are excluded, per W-02 wire contract.
    semantic = {key: value for key, value in request.items()
                if key not in ("request_id", "request_digest")}
    checked = _pure_json(semantic)
    try:
        canonical = rfc8785.dumps(checked)
    except (rfc8785.CanonicalizationError, ValueError, TypeError) as exc:
        raise PrepareEvidenceError("WHD_SCHEMA_INVALID", "request cannot be canonicalized") from exc
    return hashlib.sha256(canonical).hexdigest()


def require_matching_wire_request_digest(request: Mapping[str, Any]) -> str:
    declared = request.get("request_digest") if isinstance(request, Mapping) else None
    if not isinstance(declared, str) or _HASH.fullmatch(declared) is None:
        raise PrepareEvidenceError("WHD_REQUEST_DIGEST_INVALID", "missing or malformed canonical request SHA256")
    actual = compute_wire_request_digest(request)
    if not hmac.compare_digest(actual, declared):
        raise PrepareEvidenceError("WHD_REQUEST_DIGEST_MISMATCH", "request semantic payload differs from declared digest")
    return actual
