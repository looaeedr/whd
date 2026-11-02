"""#2517: Receiving BasePlate Family aliases share the real Engine DXF owner."""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import BasePlatePartSpec, ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest,
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)


def _base_plate(model_name="受電箱", *, pattern="LEFT_FLAT_SIDE"):
    return BasePlatePartSpec(
        width=800.0, height=340.0, thickness=2.0,
        shrink_top=20.0, shrink_bottom=20.0,
        shrink_left=45.0, shrink_right=45.0,
        bend=20.0, model_name=model_name,
        receiving_bend_pattern=pattern,
    )


def _bay(spec):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "source-sha", "Set-A", "Bay-1"),
        confirmed_parts=(("base_plate", spec),),
    )


def _real_dxf(path):
    assert Path(path).is_file()
    document = ezdxf.readfile(path)
    layers = {entity.dxf.layer for entity in document.modelspace()}
    assert {"CUTTING", "BEND"} <= layers


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  "])
def test_receiving_family_alias_exports_real_base_plate_dxf(family, tmp_path):
    spec = _base_plate(family)
    path = tmp_path / "ordinary-base-plate.dxf"
    result = manufacturing_api.generate_part(
        spec, path, ManufacturingContext(resource_root=tmp_path),
    )
    assert result.part_kind == "base_plate"
    assert result.exporter_name == "final_scene_base_plate_structure_export"
    _real_dxf(path)


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_missing_pattern_alias_is_blocked_by_render_and_export(family, tmp_path):
    spec = _base_plate(family, pattern=None)
    rendered = manufacturing_api.build_part_render_data(
        spec, ManufacturingContext(resource_root=tmp_path),
    )
    assert rendered.metadata.get("receiving_base_plate_unconfigured") is True
    out = tmp_path / "must-not-write.dxf"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING"):
        manufacturing_api.save_part_render_data_dxf(rendered, out)
    assert not out.exists()


def test_confirmed_receiving_base_plate_uses_existing_verified_batch_dxf(tmp_path):
    source = _bay(_base_plate("receiving")).source
    refused = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", family="受電箱", source=source),
    )
    assert refused.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    guards = []
    result = export_verified_resolved_integration_bays(
        (_bay(_base_plate("receiving")),), tmp_path / "manufactured",
        pre_commit_guard=lambda: guards.append("source-check"),
        context=ManufacturingContext(resource_root=tmp_path),
    )
    assert guards == ["source-check", "source-check"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 1
    _real_dxf(next(iter(result.output_files.values())))


@pytest.mark.parametrize("change", [
    {"receiving_bend_pattern": None},
    {"receiving_bend_pattern": "CENTER_DOUBLE_SIDE_FOLD"},
    {"receiving_nfb_depth_pair_mm": (107.0, 72.0)},
    {"physical_id": "base_plate:nfb_layer:0"},
])
def test_unverified_base_plate_cannot_use_ordinary_verified_bay_role(tmp_path, change):
    spec = replace(_base_plate(), **change)
    output = tmp_path / "blocked"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_SOURCE_UNVERIFIED"):
        export_verified_resolved_integration_bays(
            (_bay(spec),), output, pre_commit_guard=lambda: None,
        )
    assert not output.exists()


def test_unknown_part_role_stays_unavailable(tmp_path):
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_PART_SCOPE_UNSUPPORTED"):
        export_verified_resolved_integration_bays(
            (ManufacturingResolvedBayInput(
                family="受電箱",
                source=ManufacturingSourceIdentity("P1", "source-sha", "Set-A", "Bay-1"),
                confirmed_parts=(("nfb_pad", _base_plate()),),
            ),), tmp_path / "blocked",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "blocked").exists()
