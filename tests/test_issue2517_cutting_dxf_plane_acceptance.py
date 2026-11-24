"""Independent WCS plane verification of the bytes the CAM reader receives."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet


def _alter_plane(path, kind, change):
    doc = ezdxf.readfile(path)
    entity = next(e for e in doc.modelspace() if e.dxf.layer == "CUTTING"
                  and e.dxftype() == kind)
    if change == "normal":
        entity.dxf.extrusion = (0, 0, -1)
    elif kind == "LWPOLYLINE":
        entity.dxf.elevation = 6
    elif kind == "CIRCLE":
        entity.dxf.center = (entity.dxf.center.x, entity.dxf.center.y, 6)
    else:
        entity.dxf.end = (entity.dxf.end.x, entity.dxf.end.y, 6)
    doc.saveas(path)


@pytest.mark.parametrize(("kind", "change"), [
    ("LWPOLYLINE", "height"), ("LWPOLYLINE", "normal"),
    ("CIRCLE", "height"), ("CIRCLE", "normal"), ("LINE", "height"),
])
def test_legacy_planar_cutting_entities_roundtrip_then_reject_altered_plane(tmp_path, kind, change):
    scene = DrawingScene()
    outline = ((0, 0), (100, 0), (100, 60), (0, 60))
    if kind == "LINE":
        for a, b in zip(outline, (*outline[1:], outline[0])):
            scene.add_line(a, b, layer="CUTTING")
    else:
        scene.add_polyline(outline, layer="CUTTING", closed=True)
    if kind == "CIRCLE":
        scene.add_circle((50, 30), 5, layer="CUTTING")
    render = api.PartRenderData(scene=scene, material=api.material_polygon_from_final_scene(scene),
                                fold_guides=())
    path = tmp_path / "canonical.dxf"
    api.save_part_render_data_dxf(render, path, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, path).ok

    _alter_plane(path, kind, change)
    result = api.verify_saved_part_render_data_dxf(render, path)
    assert [(issue.category, issue.actual) for issue in result.issues] == [
        ("CUTTING_PLANE_MISMATCH", kind),
    ]


@pytest.mark.parametrize("route", ["single", "verified_batch"])
@pytest.mark.parametrize("change", ["height", "normal"])
def test_real_receiving_left_nonplanar_stage_cannot_replace_old_dxf(
    actual_sheet, tmp_path, monkeypatch, route, change,
):
    _, render, *_ = actual_sheet

    def export():
        if route == "single":
            return api.save_part_render_data_dxf(
                render, tmp_path / "left.dxf", overwrite=True, verify_reopen=True,
            )
        outputs = api.save_verified_final_scene_batch_dxf(
            (("base_plate", render),), tmp_path,
            overwrite=True, pre_commit_guard=lambda: None,
        )
        return outputs["base_plate"]

    destination = Path(export())
    before = destination.read_bytes()
    assert api.verify_saved_part_render_data_dxf(render, destination).ok
    original_serializer = api.save_scene_dxf
    stages = []

    def corrupt(path, scene):
        original_serializer(path, scene)
        assert Path(path) != destination
        stages.append(Path(path))
        _alter_plane(path, "LWPOLYLINE", change)

    monkeypatch.setattr(api, "save_scene_dxf", corrupt)
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        export()
    assert stages and destination.read_bytes() == before
    assert all(not path.exists() for path in stages)
    assert list(tmp_path.iterdir()) == [destination]
