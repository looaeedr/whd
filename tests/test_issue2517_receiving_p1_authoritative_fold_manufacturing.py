"""#2517: Receiving's authored physical Fold, not CADSplit legacy scalars, drives DXF."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)

REPO = Path(__file__).resolve().parents[1]


def _p1_factory_snapshot():
    # Real CADSplit P1 W/H/D/T. The remaining fields are Engine's *fresh*
    # Receiving Family preset, never dimensions inferred from the DXF bbox.
    state = family_policy.apply_fresh_family_defaults(
        {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}, "受電箱"
    )
    assert (state["w"], state["h"], state["d"], state["t"]) == (
        800.0, 1600.0, 350.0, 2.0
    )
    return state


def _box_body(snapshot):
    state = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    state = manufacturing_api.set_side_back_back_panel_mode(state, "FULL")
    # The Receiving Family's real side/back Fold intentionally omits zr1.
    # z_comp is irrelevant to this canonical split physical topology.
    assert "zr1" not in snapshot and "z_comp" not in snapshot
    rows = manufacturing_api.build_box_body_fold_profile(snapshot)
    return manufacturing_api.build_box_body_operator_part_spec(
        snapshot, model_name="受電箱", fold_profile=rows, structure_state=state
    )


def _endcap(snapshot, *, tail):
    # Authored operator Fold state from current EndCap contract (CURRENT 07).
    # The derived PartSpec receives only the source/cabinet context and Fold,
    # never a duplicate scalar yl1/yr1/ytop1 or removed BoxBody zr1.
    authored = {**snapshot, "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0}
    key = "tail" if tail else "head"
    rows = manufacturing_api.build_endcap_xy_fold_profiles(authored, part_key=key)
    sparse = {
        k: snapshot[k] for k in ("w", "h", "d", "t", "fw", "zl1")
    }
    structure = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    corner = family_policy.endcap_corner_policy(
        "受電箱", frame_width=snapshot["fw"],
        thickness=snapshot["t"], state=structure,
    )
    return manufacturing_api.build_endcap_operator_part_spec(
        sparse, model_name="受電箱", is_tail=tail, holes=(),
        fold_profiles=rows, corner_policy=corner,
        box_body_structure_state=structure,
    )


def test_p1_source_and_confirmed_fold_generate_real_receiving_dxf_roundtrip(tmp_path):
    snapshot = _p1_factory_snapshot()
    body = _box_body(snapshot)
    head = _endcap(snapshot, tail=False)
    tail = _endcap(snapshot, tail=True)
    assert body.zr1 is None and body.z_comp is None
    assert body.back_panel_contract and body.fold_profile
    assert head.box_fold_right is None and tail.box_fold_right is None
    assert (head.fold_left, head.fold_right, head.fold_top, head.fold_bottom) == (
        15.0, 15.0, 16.0, 15.0
    )
    assert head.depth_comp_t == tail.depth_comp_t == 2.0

    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "confirmed-source-revision", "Set1", "Bay1"),
        confirmed_parts=(("box_body", body), ("head", head), ("tail", tail)),
    )
    checks = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "p1_manufactured",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checks.append("source-unchanged"),
    )
    assert checks == ["source-unchanged", "source-unchanged"]
    assert result.physical_dxf_roundtrip_verified
    # Three independent BoxBody sheets plus Head and Tail. This *does not*
    # certify a full cabinet or authorize unconfirmed Source-only export.
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 5
    for output in result.output_files.values():
        doc = ezdxf.readfile(output)
        layers = {entity.dxf.layer for entity in doc.modelspace()}
        assert "CUTTING" in layers and "BEND" in layers


def test_missing_receiving_authored_fold_never_invents_factory_geometry():
    snapshot = _p1_factory_snapshot()
    with pytest.raises(KeyError, match="zr1"):
        manufacturing_api.build_box_body_operator_part_spec(
            snapshot, model_name="受電箱", fold_profile=(),
        )
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_AUTHORED_FOLD_REQUIRED"):
        manufacturing_api.build_endcap_operator_part_spec(
            {k: snapshot[k] for k in ("w", "h", "d", "t", "fw", "zl1")},
            model_name="受電箱", is_tail=False, holes=(),
        )
    with pytest.raises(KeyError, match="zr1"):
        manufacturing_api.build_box_body_operator_part_spec(
            snapshot, model_name="金庫型", fold_profile=(),
        )


def test_receiving_endcap_rejects_conflicting_confirmed_profile_dimensions():
    snapshot = _p1_factory_snapshot()
    authored = {**snapshot, "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0}
    rows = manufacturing_api.build_endcap_xy_fold_profiles(authored, part_key="head")
    # A complete profile cannot override the confirmed original W/H/D/T.
    source = {k: snapshot[k] for k in ("w", "h", "d", "t", "fw", "zl1")}
    source["d"] = 360.0
    structure = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    corner = family_policy.endcap_corner_policy(
        "受電箱", frame_width=snapshot["fw"],
        thickness=snapshot["t"], state=structure,
    )
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FOLD_CONFLICT"):
        manufacturing_api.build_endcap_operator_part_spec(
            source, model_name="受電箱", is_tail=False, holes=(),
            fold_profiles=rows, corner_policy=corner,
        )
