"""#2517 Receiving settings 2D physical world-assembly belongs to Engine."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest
from shapely.geometry import box, Point

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene
from gui_modules.application import receiving_settings_preview_2d as gui


def _part(key, material, *, offset=(0, 0, 0), placement="offset"):
    return SimpleNamespace(
        part_key=key,
        render_data=PartRenderData(scene=DrawingScene(), material=material),
        x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 70.0, "core": "H"},),
        placement=placement,
        offset=offset,
    )


def test_headless_world_meshes_keep_holes_offsets_and_source_part_identity():
    material = box(0, 0, 100, 70).difference(
        Point(45, 35).buffer(7, resolution=12)
    )
    witness = material.wkb
    parts = (_part("door:left", material),
             _part("door:right", material, offset=(180, 0, 0)))
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        parts, finished_dimensions=(300, 200, 80), thickness=2.0,
    )
    assert [key for _, key, _ in rows] == ["door:left", "door:right"]
    assert all(len(mesh) > 4 for _, _, mesh in rows)
    mins = [min(pt[0] for tri in mesh for pt in tri) for _, _, mesh in rows]
    assert mins[1] - mins[0] == pytest.approx(180.0)
    assert material.wkb == witness


def test_real_receiving_split_box_body_uses_exact_physical_world_skins():
    from tests.test_piece_level_joint_geometry import _receiving_body_part
    body = _receiving_body_part()
    dims = (800.0, 600.0, 350.0)
    world = api.build_joint_world_geometry(
        (body,), dims, 2.0,
    )["world_triangles_by_part"]
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        (body,), finished_dimensions=dims, thickness=2.0,
    )
    keys = {key for _, key, _mesh in rows}
    assert keys == {
        "box_body:left_side", "box_body:back", "box_body:right_side",
    }
    for role, key, mesh in rows:
        assert role in {"left_side", "back", "right_side"}
        assert mesh == tuple(world[key])


def test_invalid_multisheet_outside_width_source_fails_closed():
    fake = SimpleNamespace(role="left_side", formed_w_end=True)
    data = SimpleNamespace(pieces=(fake,))
    body = SimpleNamespace(part_key="box_body", render_data=data)
    with pytest.raises(ValueError, match="BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID"):
        api.resolve_receiving_settings_assembly_world_meshes(
            (body,), finished_dimensions=(800, 600, 350), thickness=2.0,
        )


def test_receiving_gui_only_delegates_world_geometry_and_maps_display_role(monkeypatch):
    expected = (("door:left", "door:left", (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)),)
    calls = []
    def fake(parts, **kw):
        calls.append((parts, kw))
        return expected
    monkeypatch.setattr(api, "resolve_receiving_settings_assembly_world_meshes", fake)
    request = SimpleNamespace(
        render_data=SimpleNamespace(assembly_parts=("source",),
                                    preserve_endcap_core_origin=True),
        finished_dimensions=(800, 600, 350),
        thickness=2.0,
    )
    assert tuple(gui._assembly_world_meshes(request)) == (
        ("door", "door:left", expected[0][2]),
    )
    assert calls == [(("source",), {
        "finished_dimensions": (800, 600, 350),
        "thickness": 2.0,
        "preserve_endcap_core_origin": True,
    })]
    source = inspect.getsource(gui._assembly_world_meshes)
    assert "manufacturing_api.resolve_receiving_settings_assembly_world_meshes" in source
    assert "_phase6_" not in source
    assert "place_endcap_against_box_body" not in source
