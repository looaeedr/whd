"""#2517: only Engine may turn CADSplit source dimensions into physical PartSpecs."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)

REPO = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _build(outside, **kwargs):
    return manufacturing_api.build_receiving_factory_confirmed_parts(
        outside, **kwargs
    )


def test_fresh_confirmed_p1_source_to_five_physical_dxf_roundtrips(tmp_path):
    source = deepcopy(SOURCE)
    parts = _build(source, confirmation="fresh_family_confirmed")
    assert source == SOURCE
    assert [key for key, _ in parts] == ["box_body", "head", "tail"]
    body, head, tail = (item for _, item in parts)
    assert body.model_name == head.model_name == tail.model_name == "受電箱"
    assert (body.width, body.height, body.depth, body.thickness) == (
        800, 1600, 350, 2
    )
    assert (body.frame_width, body.zl1, body.zl2, body.zr2) == (
        29, -24, 24, 18
    )
    assert body.zr1 is None and body.z_comp is None
    assert body.fold_profile and body.back_panel_contract
    assert head.depth_comp_t == tail.depth_comp_t == 2.0
    assert (head.fold_left, head.fold_right, head.fold_top, head.fold_bottom) == (
        15, 15, 16, 15
    )

    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            panel_key="P1", source_revision="verified-p1", set_id="Set1", bay_id="Bay1"
        ),
        confirmed_parts=parts,
    )
    checks = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "manufactured",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checks.append("source-rechecked"),
    )
    assert checks == ["source-rechecked", "source-rechecked"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 5
    for output in result.output_files.values():
        drawing = ezdxf.readfile(output)
        layers = {entity.dxf.layer for entity in drawing.modelspace()}
        assert "CUTTING" in layers
        if "back" not in Path(output).stem:
            assert "BEND" in layers


def test_fresh_nondefault_source_dimensions_override_family_nominal_geometry():
    dimensions = {"w": 920.0, "h": 1770.0, "d": 410.0, "t": 2.5}
    parts = _build(dimensions, confirmation="fresh_family_confirmed")
    assert len(parts) == 3
    for _, spec in parts:
        assert (spec.width, spec.height, spec.depth, spec.thickness) == (
            920.0, 1770.0, 410.0, 2.5
        )
    assert parts[1][1].depth_comp_t == 2.0
    assert parts[0][1].model_name == "受電箱"


def test_saved_confirmed_engine_state_uses_actual_physical_profiles_not_fresh_fallback():
    source = deepcopy(SOURCE)
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(source)
    saved["fw"] = 31.0
    saved["model"] = "受電箱"
    saved["box_body_structure_state"] = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = manufacturing_api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        part: manufacturing_api.build_endcap_xy_fold_profiles(
            {**saved, "yl1": 19.0, "yr1": 21.0, "ytop1": 18.0},
            part_key=part,
        )
        for part in ("head", "tail")
    }
    before = deepcopy(saved)
    parts = _build(source, confirmation="saved_operator_confirmed", operator_snapshot=saved)
    assert saved == before
    assert parts[0][1].frame_width == 31.0
    assert parts[1][1].fold_left == 19.0
    assert parts[2][1].fold_right == 21.0
    assert parts[1][1].fold_top == 18.0


@pytest.mark.parametrize("invalid", [
    {},
    {"w": 800, "h": 1600, "d": 350},
    {"w": 800, "h": 1600, "d": 350, "t": float("nan")},
    {"w": 800, "h": 1600, "d": 350, "t": False},
    {"w": 800, "h": 1600, "d": -350, "t": 2},
    {"w": 800, "h": 1600, "d": 350, "t": 2, "yl1": 15},
])
def test_reject_untrusted_or_manufacturing_source_fields(invalid):
    with pytest.raises((TypeError, ValueError), match="RECEIVING_SOURCE_DIMENSIONS_INVALID"):
        _build(invalid, confirmation="fresh_family_confirmed")


def test_source_only_does_not_authorize_manufacture_or_invent_state():
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        _build(SOURCE)
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        _build(SOURCE, confirmation="unconfirmed")
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_AMBIGUOUS"):
        _build(
            SOURCE, confirmation="fresh_family_confirmed",
            operator_snapshot={"model": "受電箱"},
        )


def test_saved_state_must_match_source_and_contain_all_physical_authority():
    saved = {**SOURCE, "model": "受電箱", "fw": 29.0}
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        _build(
            SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=saved
        )
    mismatch = {**saved, "w": 801.0}
    with pytest.raises(ValueError, match="RECEIVING_SOURCE_SAVED_DIMENSIONS_CONFLICT"):
        _build(
            SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=mismatch
        )


def test_fresh_factory_confirmation_cannot_change_vault_or_export_source_only(tmp_path):
    from ae_engine.integration_api import (
        ManufacturingIntegrationRequest, dispatch_manufacturing_integration,
    )
    source = ManufacturingSourceIdentity("P1", "verified-p1", "Set1", "Bay1")
    response = dispatch_manufacturing_integration(ManufacturingIntegrationRequest(
        operation="export", family="受電箱", source=source,
    ))
    assert response.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert not response.manufacturing_authorized
    assert not (tmp_path / "manufactured").exists()
