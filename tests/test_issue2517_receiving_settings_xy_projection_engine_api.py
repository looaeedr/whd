"""#2517: Receiving settings 2D physical world outline is Engine-owned."""
from __future__ import annotations

import inspect

from shapely.geometry import box

from ae_engine import manufacturing_api
from ae_engine.assembly_geometry import folded_mesh_from_polygon, thicken_triangle_surface
from ae_engine.receiving_settings_orthographic_projection import project_solid_mesh_xy_outline
from gui_modules.application import receiving_settings_preview_2d as gui


def test_headless_engine_world_xy_outline_preserves_old_display_contract():
    triangles = (
        ((0, 0, 0), (1, 0, 0), (1, 1, 0)),
        ((0, 0, 0), (1, 1, 0), (0, 1, 0)),
    )
    expected = (
        ((0.0, 0.0), (0.0, 1.0)),
        ((0.0, 0.0), (1.0, 0.0)),
        ((0.0, 1.0), (1.0, 1.0)),
        ((1.0, 0.0), (1.0, 1.0)),
    )
    assert manufacturing_api.project_solid_mesh_xy_outline(triangles) == expected
    assert project_solid_mesh_xy_outline(triangles) == expected
    assert gui._projected_outline(triangles) == expected


def test_real_thickened_hole_rims_survive_xy_readback_without_mutating_source():
    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    surface = folded_mesh_from_polygon(
        material, [{"len": 100, "core": "W"}],
        [{"len": 60, "core": "D"}], fold_guides=(),
    )
    solids = thicken_triangle_surface(surface, 2.0)
    source_witness = repr(solids)
    edges = manufacturing_api.project_solid_mesh_xy_outline(solids)
    holes = tuple(
        (a, b) for a, b in edges
        if all(abs(point[0]) <= 10.00001 and abs(point[1]) <= 10.00001
               for point in (a, b))
    )
    assert len(holes) >= 4
    assert edges == tuple(sorted(set(edges)))
    assert repr(solids) == source_witness


def test_z_only_edges_drop_and_xy_quantization_is_preserved():
    mesh = (((0, 0, 0), (0, 0, 1), (2.0000001, 0, 0)),)
    assert manufacturing_api.project_solid_mesh_xy_outline(mesh) == (
        ((0.0, 0.0), (2.0, 0.0)),
    )


def test_receiving_gui_is_a_thin_public_api_adapter(monkeypatch):
    calls = []
    expected = (((1.0, 2.0), (3.0, 4.0)),)

    def fake(triangles):
        calls.append(triangles)
        return expected

    monkeypatch.setattr(manufacturing_api, "project_solid_mesh_xy_outline", fake)
    mesh = (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)
    assert gui._projected_outline(mesh) == expected
    assert calls == [mesh]
    source = inspect.getsource(gui._projected_outline)
    assert "manufacturing_api.project_solid_mesh_xy_outline" in source
    assert "round(" not in source
    assert "_phase6_mesh_feature_segments" not in source


def test_settings_preview_consumes_headless_projection_without_tk(monkeypatch):
    mesh = (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)
    monkeypatch.setattr(
        gui, "_assembly_world_meshes",
        lambda _request: iter((("left_side", "box_body:left_side", mesh),)),
    )
    expected = manufacturing_api.project_solid_mesh_xy_outline(mesh)
    assert gui.projected_assembly_parts(object()) == (
        ("left_side", "box_body:left_side", expected),
    )
