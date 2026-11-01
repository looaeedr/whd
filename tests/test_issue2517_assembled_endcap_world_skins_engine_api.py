"""#2517: assembled EndCap world skins have one Engine authority."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api as api
from ae_engine import receiving_settings_assembly_mesh as engine
from ae_engine.assembly_geometry import (
    place_endcap_against_box_body, thicken_triangle_surface,
)
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene


BODY = (((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 600.0, 0.0)),)
LOCAL = (((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 50.0, 0.0)),)


@pytest.mark.parametrize("placement", ("top", "head", "bottom", "tail"))
@pytest.mark.parametrize("preserve_core_origin", (False, True))
def test_true_t_endcap_head_tail_matches_existing_canonical_mating(
    placement, preserve_core_origin,
):
    kwargs = {"sheet_thickness": 2.0, "preserve_core_origin": preserve_core_origin}
    source = tuple(tuple(p for p in tri) for tri in LOCAL)
    expected_surface = place_endcap_against_box_body(
        LOCAL, placement, BODY, (5, 3, 7), **kwargs,
    )
    result = api.resolve_assembled_endcap_world_skins(
        LOCAL, placement=placement, box_body_world=BODY, thickness=2.0,
        offset=(5, 3, 7), preserve_core_origin=preserve_core_origin,
    )
    assert isinstance(result, api.AssembledEndcapWorldSkins)
    assert result.formed_surface == expected_surface
    assert result.solid_triangles == thicken_triangle_surface(expected_surface, 2.0)
    assert LOCAL == source
    assert len(result.solid_triangles) > len(LOCAL)
    with pytest.raises(FrozenInstanceError):
        result.solid_triangles = ()


def test_missing_body_or_invalid_orientation_cannot_forge_world_sheet():
    empty = api.resolve_assembled_endcap_world_skins(
        LOCAL, placement="head", box_body_world=(), thickness=2.0,
    )
    assert empty.formed_surface == () and empty.solid_triangles == ()
    with pytest.raises(ValueError, match="Unsupported EndCap assembly placement"):
        api.resolve_assembled_endcap_world_skins(
            LOCAL, placement="diagonal", box_body_world=BODY, thickness=2.0,
        )


def _part(key, *, placement="offset"):
    data = PartRenderData(scene=DrawingScene(), material=box(0, 0, 100, 70))
    return SimpleNamespace(
        part_key=key, render_data=data,
        x_profile=({"len": 100.0, "core": "W"},),
        y_profile=({"len": 70.0, "core": "H"},),
        placement=placement, offset=(0, 0, 0),
    )


def test_receiving_2d_delegates_endcap_world_geometry_to_shared_engine(monkeypatch):
    original = engine.resolve_assembled_endcap_world_skins
    calls = []

    def spy(local, **kw):
        calls.append(kw)
        return original(local, **kw)

    monkeypatch.setattr(engine, "resolve_assembled_endcap_world_skins", spy)
    rows = api.resolve_receiving_settings_assembly_world_meshes(
        (_part("box_body"), _part("head", placement="top")),
        finished_dimensions=(800, 600, 350), thickness=2.0,
        preserve_endcap_core_origin=True,
    )
    assert {key for _, key, _ in rows} == {"box_body", "head"}
    assert all(mesh for _, _, mesh in rows)
    assert len(calls) == 1 and calls[0]["placement"] == "top"
    assert calls[0]["preserve_core_origin"] is True
    assert calls[0]["thickness"] == 2.0


def test_3d_renderer_endcap_display_and_probe_only_call_public_engine():
    source = inspect.getsource(Phase6FinalSceneRenderer)
    assert source.count("manufacturing_api.resolve_assembled_endcap_world_skins(") == 2
    assert "place_endcap_against_box_body(" not in source
    assert "formed_surface_for_edges = skins.formed_surface" in source
    assert "placed = skins.solid_triangles" in source
    assert "collision_target = (" in source
