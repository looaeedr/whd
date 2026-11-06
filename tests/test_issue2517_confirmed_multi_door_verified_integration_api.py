"""#2517: confirmed multi-Door cells use the existing verified Engine DXF."""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine.contracts import BoxBodyPartSpec, DoorPartSpec, ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest, ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity, dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)
from ae_engine.manufacturing_api import door_part_projections


COLUMNS = ((420.0, (760.0, 840.0)), (380.0, (760.0, 840.0)))


def _doors():
    projections = door_part_projections({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": COLUMNS, "t": 2.0, "fw": 29.0,
    })
    return tuple((cell.part_key, DoorPartSpec(
        width=cell.start_width, height=cell.start_height,
        thickness=2.0, frame_width=29.0, model_name="受電箱",
        gap_w=3.5, gap_h=3.5, fold_left=19.0, fold_right=19.0,
        fold_top=19.0, fold_bottom=19.0,
        frame_edges=cell.frame_edges, feature_space="finished_face",
    )) for cell in projections)


def _bay(parts=None, *, columns=COLUMNS):
    return ManufacturingResolvedBayInput(
        family="RECEIVING",
        source=ManufacturingSourceIdentity(
            "P1", "confirmed-source-revision", "set-A", "bay-1",
        ),
        confirmed_parts=_doors() if parts is None else tuple(parts),
        door_layout_columns=columns,
    )


def test_confirmed_multi_door_reuses_real_engine_verified_dxfs(tmp_path):
    refused = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", "受電箱", _bay().source),
    )
    assert refused.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    guards = []
    result = export_verified_resolved_integration_bays(
        (_bay(),), tmp_path / "manufactured",
        context=ManufacturingContext(resource_root=tmp_path),
        pre_commit_guard=lambda: guards.append("source-current"),
    )
    assert guards == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 4
    expected = {"door_c1_r1", "door_c1_r2", "door_c2_r1", "door_c2_r2"}
    for filename in result.output_files.values():
        path = Path(filename)
        assert path.is_file()
        assert any(path.name.endswith(role + ".dxf") for role in expected)
        layers = {entity.dxf.layer for entity in ezdxf.readfile(path).modelspace()}
        assert {"CUTTING", "BEND"} <= layers


@pytest.mark.parametrize("edit,code", [
    (lambda xs: xs[:-1], "RECEIVING_DOOR_TOPOLOGY_INCOMPLETE"),
    (lambda xs: xs + (("door", xs[0][1]),), "RECEIVING_DOOR_TOPOLOGY_INCOMPLETE"),
    (lambda xs: ((xs[0][0], replace(xs[0][1], width=421.0)),) + xs[1:],
     "RECEIVING_DOOR_TOPOLOGY_MISMATCH"),
    (lambda xs: ((xs[0][0], replace(xs[0][1], frame_edges=xs[-1][1].frame_edges)),) + xs[1:],
     "RECEIVING_DOOR_TOPOLOGY_MISMATCH"),
    (lambda xs: ((xs[0][0], replace(xs[0][1], gap_w=4.0)),) + xs[1:],
     "RECEIVING_DOOR_TOPOLOGY_MISMATCH"),
    (lambda xs: ((xs[0][0], replace(xs[0][1], model_name="金庫型")),) + xs[1:],
     "RECEIVING_CONFIRMED_PART_FAMILY_MISMATCH"),
])
def test_incomplete_or_mismatched_grid_cannot_create_dxf(tmp_path, edit, code):
    output = tmp_path / "out"
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (_bay(edit(_doors())),), output, pre_commit_guard=lambda: None,
        )
    assert not output.exists()


def test_grid_requires_confirmed_layout(tmp_path):
    with pytest.raises(ValueError, match="RECEIVING_DOOR_LAYOUT_REQUIRED"):
        export_verified_resolved_integration_bays(
            (_bay(columns=()),), tmp_path / "out",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


def test_layout_must_match_box_body_total_width(tmp_path):
    box = BoxBodyPartSpec(
        width=799.0, height=1600.0, depth=350.0, thickness=2.0,
        frame_width=29.0, model_name="受電箱",
    )
    with pytest.raises(ValueError, match="RECEIVING_DOOR_LAYOUT_INVALID"):
        export_verified_resolved_integration_bays(
            (_bay(_doors() + (("box_body", box),)),), tmp_path / "out",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


def test_existing_single_door_still_works(tmp_path):
    spec = replace(_doors()[0][1], width=800.0, height=1600.0)
    result = export_verified_resolved_integration_bays(
        (_bay((("door", spec),), columns=()),), tmp_path / "out",
        context=ManufacturingContext(resource_root=tmp_path),
        pre_commit_guard=lambda: None,
    )
    assert len(result.output_files) == 1
    assert all(Path(path).is_file() for path in result.output_files.values())
