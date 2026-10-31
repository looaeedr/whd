# -*- coding: utf-8 -*-
"""#2383: all Vault/Receiving features have a versioned API request route.

A valid *wire* request for an unverified feature is NOT permission to
manufacture. The private Worker must deny it before W-06 ever claims a job.
"""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.worker_feature_catalog import (
    FAMILIES, _COMMON_OWNERS, _RECEIVING_OWNERS, _BLOCKED_REASONS,
    require_certified_feature_route,
)
from tests.test_issue2378_prepare_batch import _request


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Draft202012Validator(json.loads((
    ROOT / "integration_cli" / "schemas" / "request_v1_1.schema.json"
).read_text(encoding="utf-8")))
P0 = {"door", "end_cap_head", "end_cap_tail", "indicator_box", "indicator_small_door", "base_plate", "custom_fold", "box_body", "inner_door", "side_panel", "back_panel"}


def _feature_request(family, role):
    request = _request()
    part = request["items"][0]["part"]
    part["cabinet_family"] = family
    part["kind"] = role
    if role in ("end_cap_head", "end_cap_tail"):
        part["dimensions_mm"] = {"width": 500.0, "depth": 350.0, "thickness": 2.0}
    if role == "box_body":
        part.clear()
        part.update({
            "kind": role, "cabinet_family": family, "source_part_ref": "box_body",
            "dimension_semantics": "cabinet_outer",
            "dimensions_mm": {"width": 400, "height": 600, "depth": 250, "thickness": 2},
            "frame_width_mm": 25, "box_zl1_mm": -15, "box_zl2_mm": 20,
            "box_zr1_mm": 15, "box_zr2_mm": 20, "box_z_comp_mm": 2,
        })
    if role == "base_plate":
        part["dimensions_mm"] = {"width": 500.0, "height": 350.0, "thickness": 2.0}
        part["dimension_semantics"] = "part_formed_outer"
        part.update({key: 10.0 for key in (
            "shrink_top_mm", "shrink_bottom_mm", "shrink_left_mm",
            "shrink_right_mm", "bend_mm",
        )})
    if role == "back_panel":
        part.clear()
        part.update({
            "kind": role, "cabinet_family": family,
            "source_part_ref": "box_body:back", "dimension_semantics": "cabinet_outer",
            "dimensions_mm": {"width": 800.0, "height": 1600.0,
                              "depth": 350.0, "thickness": 2.0},
            "frame_width_mm": 29.0,
            "box_zl1_mm": -24.0, "box_zl2_mm": 24.0, "box_zr2_mm": 18.0,
            "back_panel_mode": "FULL",
        })
    if role == "side_panel":
        part.clear()
        part.update({
            "kind": role, "cabinet_family": family,
            "source_part_ref": "box_body:left_side",
            "dimension_semantics": "cabinet_outer",
            "dimensions_mm": {"width": 800, "height": 1600, "depth": 350, "thickness": 2},
            "frame_width_mm": 29, "box_zl1_mm": -24, "box_zl2_mm": 24,
            "box_zr2_mm": 18,
        })
    if role == "inner_door":
        part.clear()
        part.update({
            "kind": role, "cabinet_family": family,
            "source_part_ref": "inner_door:upper:panel",
            "dimension_semantics": "part_formed_outer",
            "inner_door_id": "upper", "inner_door_cell_key": "0:0",
            "dimensions_mm": {"width": 700, "height": 1000, "thickness": 2},
        })
    if role == "custom_fold":
        part.clear()
        part.update({
            "kind": role, "cabinet_family": family,
            "source_part_ref": "custom:17", "dimension_semantics": "part_formed_outer",
            "dimensions_mm": {"thickness": 2.0},
            "fold_axis": "X", "transverse_length_mm": 300.0,
            "fold_profile": [
                {"length_mm": 15.0, "angle_deg": -90},
                {"length_mm": 98.0, "angle_deg": None},
            ],
        })
    # Existing v1.1 shared Indicator Box/Small Door require explicit
    # grouping even for a request that will be denied by the route gate.
    if role in ("indicator_box", "indicator_small_door"):
        part["indicator_groups"] = [1]
    request["request_digest"] = compute_wire_request_digest(request)
    return request


@pytest.mark.parametrize("family", FAMILIES)
def test_all_registered_family_features_are_addressable_over_v11_wire(family):
    roles = set(_COMMON_OWNERS)
    if family == "受電箱":
        roles |= set(_RECEIVING_OWNERS)
    assert "box_body" in roles
    assert "base_plate" in roles
    assert "complete_assembly" in roles
    for role in sorted(roles):
        request = _feature_request(family, role)
        SCHEMA.validate(request)
        assert request["items"][0]["part"]["kind"] == role
        if role in P0 and not (
            family == "受電箱" and role in ("end_cap_head", "end_cap_tail", "base_plate", "box_body")
        ):
            # This passes only the routing check, NOT signed job approval,
            # source/Frame verification or real DXF manufacturing.
            require_certified_feature_route(request)
        else:
            with pytest.raises(PrepareEvidenceError) as exc:
                require_certified_feature_route(request)
            assert exc.value.code == _BLOCKED_REASONS.get(
                role, "WHD_CAPABILITY_UNSUPPORTED"
            )
    invalid = _feature_request(family, "unregistered-physical-role")
    with pytest.raises(ValidationError):
        SCHEMA.validate(invalid)


def test_unknown_family_cannot_inherit_vault_api_route():
    request = _feature_request("UNKNOWN", "door")
    SCHEMA.validate(request)
    with pytest.raises(PrepareEvidenceError) as exc:
        require_certified_feature_route(request)
    assert exc.value.code == "WHD_CAPABILITY_UNKNOWN"


@pytest.mark.parametrize("family,role", [
    ("受電箱", "box_body"),
    ("受電箱", "base_plate"),
    ("受電箱", "divider"),
    ("受電箱", "nfb_cutting"),
    ("受電箱", "multi_bay_batch"),
    ("受電箱", "end_cap_head"),
])
def test_unsupported_feature_refused_before_durable_claim(tmp_path, monkeypatch, family, role):
    from integration_cli import private_worker_dispatch as dispatch

    request = _feature_request(family, role)
    SCHEMA.validate(request)
    context = dispatch.TrustedWorkerExecution(
        resource_root=tmp_path,
        store_root=tmp_path,
        output_dir=None,
        source_documents={},
        worker_key=b"w" * 32,
        engine_sha256="f" * 64,
    )

    def no_ledger_claim(_root):
        pytest.fail("unsupported API route reached the durable W-06 ledger")

    monkeypatch.setattr(dispatch, "DurableJobIdentityLedger", no_ledger_claim)
    with pytest.raises(PrepareEvidenceError) as exc:
        dispatch.execute_private_worker(
            "prepare", request, context,
            engine_commit="a" * 40, build_id="test-only",
        )
    assert exc.value.code == _BLOCKED_REASONS.get(
        role, "WHD_CAPABILITY_UNSUPPORTED"
    )
    assert list(tmp_path.iterdir()) == []  # no source, journal or customer output
