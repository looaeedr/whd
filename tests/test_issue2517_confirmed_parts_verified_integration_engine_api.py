"""#2517 confirmed source PartSpecs resolve via existing Engine verified DXF path."""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest, ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity, dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)


def _source():
    return ManufacturingSourceIdentity(
        panel_key="P1", source_revision="trusted-sha",
        set_id="Set1", bay_id="Bay1",
    )


def _door():
    return DoorPartSpec(
        width=800.0, height=1600.0, thickness=2.0, frame_width=29.0,
        model_name="受電箱", gap_w=3.5, gap_h=3.5,
        fold_left=19.0, fold_right=19.0, fold_top=19.0,
        fold_bottom=19.0, feature_space="finished_face",
    )


def _bay(*parts):
    return ManufacturingResolvedBayInput(
        family="受電箱", source=_source(), confirmed_parts=tuple(parts),
    )


def test_confirmed_receiving_part_reaches_actual_engine_dxf_roundtrip(tmp_path):
    source_only = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", family="受電箱", source=_source()),
    )
    assert source_only.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert source_only.manufacturing_authorized is False

    checks = []
    result = export_verified_resolved_integration_bays(
        (_bay(("door", _door())),), tmp_path / "export",
        context=ManufacturingContext(resource_root=tmp_path),
        pre_commit_guard=lambda: checks.append("checked"),
    )
    assert checks == ["checked", "checked"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert not result.external_cli_enabled
    assert set(result.output_files) == {"Set1__Bay1:door"} or len(result.output_files) == 1
    exported = [Path(p) for p in result.output_files.values()]
    assert len(exported) == 1
    assert exported[0].name == "Set1__Bay1__door.dxf"
    drawing = ezdxf.readfile(exported[0])
    layers = {e.dxf.layer for e in drawing.modelspace()}
    assert "CUTTING" in layers and "BEND" in layers


def test_confirmed_part_uses_existing_engine_render_resolver(monkeypatch, tmp_path):
    observed = []
    real = manufacturing_api.build_part_render_data
    def recorded(spec, ctx):
        observed.append(spec)
        return real(spec, ctx)
    monkeypatch.setattr(manufacturing_api, "build_part_render_data", recorded)
    export_verified_resolved_integration_bays(
        (_bay(("door", _door())),), tmp_path / "export",
        context=ManufacturingContext(resource_root=tmp_path),
        pre_commit_guard=lambda: None,
    )
    assert observed == [_door()]


@pytest.mark.parametrize("invalid,expected", [
    (("unreleased_nfb", _door()), "RECEIVING_CONFIRMED_PART_SCOPE_UNSUPPORTED"),
    (("door", replace(_door(), model_name="金庫型")), "RECEIVING_CONFIRMED_PART_FAMILY_MISMATCH"),
    (("door", replace(_door(), feature_space="legacy_unfolded")), "RECEIVING_DOOR_AUTHORED_VALUES_REQUIRED"),
    (("door", replace(_door(), fold_top=None)), "RECEIVING_DOOR_AUTHORED_VALUES_REQUIRED"),
    (("head", _door()), "RECEIVING_CONFIRMED_PART_SCOPE_UNSUPPORTED"),
])
def test_invalid_or_incomplete_source_never_makes_dxf(invalid, expected, tmp_path):
    output = tmp_path / "out"
    with pytest.raises(ValueError, match=expected):
        export_verified_resolved_integration_bays(
            (_bay(invalid),), output, pre_commit_guard=lambda: None,
        )
    assert not output.exists()


def test_resolved_and_confirmed_inputs_cannot_be_combined(tmp_path):
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
    from types import SimpleNamespace
    legacy_resolved = ResolvedManufacturingGeometry(
        parts=(ResolvedManufacturingPart(
            part_key="door", render_data=SimpleNamespace(scene=object()),
        ),),
    )
    bay = replace(_bay(("door", _door())), resolved_geometry=legacy_resolved)
    with pytest.raises(ValueError, match="RECEIVING_AMBIGUOUS_MANUFACTURING_INPUT"):
        export_verified_resolved_integration_bays(
            (bay,), tmp_path / "out", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


def test_source_only_and_missing_authoritative_parts_still_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="RECEIVING_ENGINE_RESOLVED_GEOMETRY_REQUIRED"):
        export_verified_resolved_integration_bays(
            (_bay(),), tmp_path / "out", pre_commit_guard=lambda: None,
        )
    with pytest.raises(ValueError, match="WHD_PRECOMMIT_GUARD_REQUIRED"):
        export_verified_resolved_integration_bays(
            (_bay(("door", _door())),), tmp_path / "out", pre_commit_guard=None,
        )
    assert not (tmp_path / "out").exists()
