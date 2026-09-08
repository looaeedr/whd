# -*- coding: utf-8 -*-
"""DM1 RED guards for the Divider Physical Geometry Contract.

These tests intentionally describe the target architecture before production
implementation exists.  They exercise runtime Divider objects rather than
searching source text.
"""
from collections.abc import Mapping

from ae_engine.door_dividers import derive_box_body_dividers


def _receiving_divider(*, frame_width=29.0):
    parts = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),),
        depth=350.0,
        thickness=2.0,
        frame_width=float(frame_width),
        layout_scope="dm1-red",
        model_name="受電箱",
    )
    assert len(parts) == 1
    return parts[0]


def _physical_contract(part):
    contract = getattr(part, "physical_geometry_contract", None)
    assert isinstance(contract, Mapping), (
        "DM1 RED: resolved Divider must expose one semantic physical geometry "
        "contract before any sink interprets fold segment indexes"
    )
    return contract


def test_dm1_resolved_divider_contract_expresses_physical_geometry_boundary():
    contract = _physical_contract(_receiving_divider())

    required = {
        "core_physical_segment",
        "fw_physical_face",
        "placement_datum",
        "final_material",
        "relief_evidence",
    }
    assert required <= set(contract), (
        "DM1 RED: the resolved Divider contract must carry core segment, FW "
        "physical face, placement datum, final material and relief evidence"
    )


def test_dm1_sink_contract_does_not_leak_raw_segment_identity():
    contract = _physical_contract(_receiving_divider())

    forbidden = {
        "frame_width_segment_index",
        "core_segment_index",
        "model_name",
        "family_name",
    }
    assert forbidden.isdisjoint(contract), (
        "DM1 RED: sink-facing Divider contract must not require raw segment "
        "indexes or cabinet-family names to understand physical geometry"
    )


def test_dm1_fw_face_is_semantic_and_tracks_live_fw_without_magic_29():
    default_contract = _physical_contract(_receiving_divider(frame_width=29.0))
    custom_contract = _physical_contract(_receiving_divider(frame_width=37.0))

    default_face = default_contract["fw_physical_face"]
    custom_face = custom_contract["fw_physical_face"]
    assert isinstance(default_face, Mapping)
    assert isinstance(custom_face, Mapping)
    assert float(default_face["outside_dimension"]) == 29.0
    assert float(custom_face["outside_dimension"]) == 37.0
    assert "segment_index" not in default_face
    assert "segment_index" not in custom_face
