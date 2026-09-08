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
        "manufacturing_resolver",
    }
    assert required <= set(contract), (
        "DM1 guard: the base Divider physical contract must carry stable core/FW "
        "physical semantics plus the canonical manufacturing resolver identity"
    )

    from ae_engine.divider_manufacturing import ResolvedDividerFinalGeometry
    final_fields = set(getattr(ResolvedDividerFinalGeometry, "__dataclass_fields__", {}))
    assert {"final_material", "relief_evidence", "placement_evidence", "verified"} <= final_fields, (
        "DM1/DM3 guard: final material and relief evidence belong to the canonical "
        "resolved manufacturing result, not placeholder fields on the base part"
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


def test_dm2_render_metadata_publishes_semantics_without_raw_indexes():
    from ae_engine.manufacturing_api import build_box_body_divider_render_data

    render_data = build_box_body_divider_render_data(_receiving_divider())
    metadata = dict(render_data.metadata or {})
    contract = metadata.get("physical_geometry_contract")
    assert isinstance(contract, Mapping)
    assert "frame_width_segment_index" not in metadata
    assert "core_segment_index" not in metadata
    fw_face = contract["fw_physical_face"]
    assert tuple(float(v) for v in fw_face["flat_band"]) == (16.0, 41.0)
    assert float(fw_face["outside_dimension"]) == 29.0


def test_dm1_family_fold_topology_change_keeps_same_sink_contract(monkeypatch):
    """Changing family fold topology must not change the sink-facing interface."""
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    def variant_family_contract(
        source,
        *,
        depth,
        thickness,
        handle_side,
        frame_width=None,
    ):
        del source, depth, handle_side
        t = float(thickness)
        fw = float(29.0 if frame_width is None else frame_width)
        # Deliberately change Receiving from 4 to 5 segments and move the FW
        # implementation identity from index 1 to index 2.  A sink must not
        # notice this topology/index change: it should consume the same semantic
        # physical contract.
        return {
            "material_lengths": (
                16.0,
                5.0,
                fw - 2.0 * t,
                106.0 - 2.0 * t,
                15.0,
            ),
            "signed_fold_chain": (18.0, 7.0, fw, 106.0, 17.0),
            "formed_core_depth": 106.0,
            "core_segment_index": 3,
            "frame_width_segment_index": 2,
        }

    monkeypatch.setattr(
        cabinet_family_policy,
        "divider_fold_contract",
        variant_family_contract,
    )

    contract = _physical_contract(_receiving_divider(frame_width=29.0))
    assert {
        "core_physical_segment",
        "fw_physical_face",
        "placement_datum",
        "manufacturing_resolver",
    } <= set(contract)
    assert float(contract["fw_physical_face"]["outside_dimension"]) == 29.0
    assert "segment_index" not in contract["fw_physical_face"]
