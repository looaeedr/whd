"""BEND roundtrip checks see native WCS, not merely the DXF's XY projection."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from tests.test_issue2517_receiving_confirmed_door_source import ROOT, SOURCE, UPPER_LOWER
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet


@pytest.mark.parametrize("route", ["ordinary", "integration"])
@pytest.mark.parametrize("bad_z", [(0.0, 6.0), (6.0, 6.0)], ids=["tilted", "parallel"])
def test_off_plane_bend_cannot_publish(route, bad_z, actual_sheet, tmp_path, monkeypatch):
    _, render, *_ = actual_sheet
    def request(bay_index, depth):
        plan = api.plan_receiving_factory_confirmed_door_handoff(
            {**SOURCE, "d": depth}, confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=UPPER_LOWER,
        )
        return ManufacturingResolvedBayInput(
            family="受電箱",
            source=ManufacturingSourceIdentity(
                f"P{bay_index}", f"test-source-{bay_index}", "set1", f"bay{bay_index}",
            ),
            confirmed_parts=plan.ordered_parts,
            door_layout_columns=UPPER_LOWER,
        )

    instance_prefix = api.receiving_manufacturing_instance_namespace(
        set_id="set1", bay_id="bay2",
    )

    def export():
        if route == "ordinary":
            return (api.save_part_render_data_dxf(
                render, tmp_path / "left.dxf", overwrite=True, verify_reopen=True,
            ),)
        result = export_verified_resolved_integration_bays(
            (request(1, 350.0), request(2, 400.0)), tmp_path,
            context=ManufacturingContext(resource_root=ROOT),
            pre_commit_guard=lambda: None, overwrite=True,
        )
        assert result.physical_dxf_roundtrip_verified
        return tuple(result.output_files.values())

    paths = set(map(Path, export()))
    assert len(paths) == (1 if route == "ordinary" else 14)
    if route == "integration":
        assert sum(path.name.startswith(instance_prefix) for path in paths) == 7
    normal_bends = []
    for path in paths:
        doc = ezdxf.readfile(path)
        assert not doc.audit().errors
        assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())
        normal_bends.extend(doc.modelspace().query('LINE[layer=="BEND"]'))
    assert normal_bends
    assert all(bend.dxf.start.z == bend.dxf.end.z == 0 for bend in normal_bends)
    before = {path: path.read_bytes() for path in paths}
    original_serializer = api.save_scene_dxf
    touched = []

    def corrupt_first_real_bend(path, scene):
        original_serializer(path, scene)
        if touched or (route == "integration"
                       and not Path(path).name.lstrip(".").startswith(instance_prefix)):
            return
        doc = ezdxf.readfile(path)
        bend = next(iter(doc.modelspace().query('LINE[layer=="BEND"]')), None)
        if bend is None:
            return
        assert bend.dxf.start.z == bend.dxf.end.z == 0
        bend.dxf.start = (bend.dxf.start.x, bend.dxf.start.y, bad_z[0])
        bend.dxf.end = (bend.dxf.end.x, bend.dxf.end.y, bad_z[1])
        doc.saveas(path)
        touched.append(Path(path))

    with monkeypatch.context() as injected:
        injected.setattr(api, "save_scene_dxf", corrupt_first_real_bend)
        with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
            export()
    assert touched and all(not path.exists() for path in touched)
    assert set(tmp_path.iterdir()) == paths
    assert {path: path.read_bytes() for path in paths} == before
