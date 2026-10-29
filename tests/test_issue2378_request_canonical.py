# -*- coding: utf-8 -*-
"""W-03/W-06 RFC8785 transport digest: reject tampering, preserve Unicode."""
from copy import deepcopy
import hashlib
import pytest
import rfc8785

from integration_cli.request_canonical import (
    compute_wire_request_digest, require_matching_wire_request_digest,
)
from integration_cli.prepare_evidence import PrepareEvidenceError


def _request():
    return {
        "protocol_version": "1.0.0",
        "client_installation_id": "CAD-1",
        "request_id": "transport-a",
        "job_id": "job-1",
        "request_digest": "a" * 64,
        "operation": "prepare",
        "coordinate_contract_revision": "1",
        "items": [{
            "item_id": "門一",
            "source_document_sha256": "f" * 64,
            "part": {
                "kind": "door",
                "cabinet_family": "金庫型",
                "source_part_ref": "DXF-來源/門",
                "dimension_semantics": "cabinet_outer",
                "dimensions_mm": {"width": 500, "height": 600.0, "thickness": 2},
            },
        }],
    }


def test_wire_digest_matches_rfc8785_and_excludes_only_transport_fields():
    request = _request()
    expected_payload = {k: v for k, v in request.items()
                        if k not in ("request_id", "request_digest")}
    expected = hashlib.sha256(rfc8785.dumps(expected_payload)).hexdigest()
    assert compute_wire_request_digest(request) == expected
    request["request_digest"] = expected
    assert require_matching_wire_request_digest(request) == expected
    request["request_id"] = "transport-new-after-timeout"
    assert require_matching_wire_request_digest(request) == expected


@pytest.mark.parametrize("field", ["job_id", "items", "client_installation_id",
                                  "operation", "coordinate_contract_revision"])
def test_semantic_rewrite_changes_digest_and_fails_closed(field):
    request = _request()
    request["request_digest"] = compute_wire_request_digest(request)
    edited = deepcopy(request)
    if field == "items":
        edited["items"][0]["part"]["dimensions_mm"]["width"] = 499
    else:
        edited[field] = {
            "job_id": "job-two",
            "client_installation_id": "CAD-2",
            "operation": "export",
            "coordinate_contract_revision": "2",
        }[field]
    with pytest.raises(PrepareEvidenceError) as exc:
        require_matching_wire_request_digest(edited)
    assert exc.value.code == "WHD_REQUEST_DIGEST_MISMATCH"


def test_request_digest_rejects_nonfinite_and_malformed_hash():
    request = _request()
    request["items"][0]["part"]["dimensions_mm"]["width"] = float("nan")
    with pytest.raises(PrepareEvidenceError):
        compute_wire_request_digest(request)
    request = _request()
    request["request_digest"] = "bad"
    with pytest.raises(PrepareEvidenceError) as exc:
        require_matching_wire_request_digest(request)
    assert exc.value.code == "WHD_REQUEST_DIGEST_INVALID"


def test_wire_digest_follows_rfc_numeric_canonicalization():
    one = _request()
    two = deepcopy(one)
    one["items"][0]["part"]["dimensions_mm"]["width"] = 500
    two["items"][0]["part"]["dimensions_mm"]["width"] = 500.0
    assert compute_wire_request_digest(one) == compute_wire_request_digest(two)
