"""#2517: source-only refusal cannot gate an existing Receiving manufacturing API.

These are real in-process Engine/DXF tests, not a CADSplit Worker certification.
Only the supplied trusted physical PartSpec/FinalScene is manufactured.
"""
from __future__ import annotations

from pathlib import Path

import ezdxf

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    DoorPartSpec, ManufacturingContext, ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest, ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity, dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)


def _receiving_door() -> DoorPartSpec:
    # Explicit trusted operator/family values, not inferred from a source DXF.
    return DoorPartSpec(
        width=800.0, height=1600.0, thickness=2.0, frame_width=29.0,
        model_name="受電箱",
        gap_w=3.5, gap_h=3.5,
        fold_left=19.0, fold_right=19.0,
        fold_top=19.0, fold_bottom=19.0,
        feature_space="finished_face",
    )


def _source() -> ManufacturingSourceIdentity:
    return ManufacturingSourceIdentity(
        panel_key="P1", source_revision="confirmed-source-revision",
        set_id="confirmed-set", bay_id="confirmed-bay",
    )


def _assert_real_dxf(path: Path) -> None:
    assert path.is_file()
    drawing = ezdxf.readfile(path)
    layers = {entity.dxf.layer for entity in drawing.modelspace()}
    assert "CUTTING" in layers
    assert "BEND" in layers


def test_source_only_refusal_does_not_block_existing_receiving_single_part_api(tmp_path):
    # The source-identity-only request is deliberately NOT manufacturing-ready.
    refusal = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", family="受電箱", source=_source()),
    )
    assert refusal.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert refusal.manufacturing_authorized is False
    assert refusal.dxf_roundtrip_verified is False

    # The already supported public Engine API is a different, authoritative
    # operation. It must remain callable with a complete typed PartSpec.
    output = tmp_path / "receiving-door.dxf"
    result = manufacturing_api.generate_part(
        _receiving_door(), output,
        ManufacturingContext(resource_root=tmp_path, draw_stock=False),
    )
    assert result.part_kind == "door"
    assert result.output_path == str(output)
    _assert_real_dxf(output)


def test_source_only_refusal_does_not_block_verified_receiving_bay_api(tmp_path):
    refusal = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", family="RECEIVING", source=_source()),
    )
    assert refusal.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"

    # Engine itself resolves the real material/FinalScene. A source name is
    # never converted into a guessed manufacturing physical-part identity.
    ctx = ManufacturingContext(resource_root=tmp_path, draw_stock=False)
    real_render_data = manufacturing_api.build_part_render_data(_receiving_door(), ctx)
    bay = ManufacturingResolvedBayInput(
        family="受電箱", source=_source(),
        resolved_geometry=ResolvedManufacturingGeometry(parts=(
            ResolvedManufacturingPart(part_key="door", render_data=real_render_data),
        )),
    )
    checks: list[str] = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        pre_commit_guard=lambda: checks.append("source-current"),
    )
    assert checks == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified is True
    assert result.complete_assembly_certified is False
    assert result.external_cli_enabled is False
    assert len(result.output_files) == 1
    for path in result.output_files.values():
        _assert_real_dxf(Path(path))
