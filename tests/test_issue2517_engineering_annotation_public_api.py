# -*- coding: utf-8 -*-
"""#2517 canonical Engineering Drawing readback uses the public Engine."""
from inspect import getsource
from types import SimpleNamespace

import ae_engine
import pytest
from shapely.geometry import box
from ae_engine import manufacturing_api as api
from ae_engine.engineering_drawing import build_engineering_drawing_projection as owner
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive, TextPrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2


def _canonical_part():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        "CUTTING", closed=True,
    ))
    scene.add(CirclePrimitive(
        Vec2(30, 20), 4, "CUTTING", source_type="mounting_hole",
        source_id="verified-hole",
    ))
    return SimpleNamespace(scene=scene, material=box(0, 0, 100, 60))


def test_root_facade_are_exact_original_engine_callable():
    assert api.project_operator_engineering_drawing is owner
    assert ae_engine.project_operator_engineering_drawing is owner
    assert "project_operator_engineering_drawing" in ae_engine.__all__


@pytest.mark.parametrize("part_key", ["door", "box_body"])
def test_canonical_projection_parity_and_manufacturing_immutability(part_key):
    render = _canonical_part()
    primitives = tuple(render.scene.primitives)
    material = bytes(render.material.wkb)
    public = api.project_operator_engineering_drawing(render, part_key=part_key)
    direct = owner(render, part_key=part_key)
    assert public == direct
    assert public.part_key == part_key
    assert public.primitives
    assert any(c.source_id == "verified-hole" for c in public.annotation_plan.feature_callouts)
    assert all(
        isinstance(p, (LinePrimitive, TextPrimitive)) and p.layer in {"DIMENSION", "TEXT"}
        for p in public.primitives
    )
    assert tuple(render.scene.primitives) == primitives
    assert bytes(render.material.wkb) == material


def test_gui_2d_preview_delegates_to_original_engine_through_public_facade(monkeypatch):
    import gui
    observed = []
    sentinel = object()

    def preview(_canvas, _data, _transform, *, part_key, strict, projection_builder):
        observed.append((part_key, strict, projection_builder))
        return sentinel

    monkeypatch.setattr(gui, "_draw_phase6_annotation_projection_impl", preview)
    assert gui._draw_phase6_annotation_projection(
        None, _canonical_part(), None, part_key="door", strict=True,
    ) is sentinel
    assert observed == [("door", True, api.project_operator_engineering_drawing)]
    assert "from ae_engine.engineering_drawing import" not in getsource(gui)


@pytest.mark.parametrize("bad", [
    None,
    SimpleNamespace(scene=None, material=box(0, 0, 1, 1)),
    SimpleNamespace(scene=DrawingScene(), material=None),
])
def test_invalid_canonical_render_data_fails_without_fallback(bad):
    with pytest.raises(ValueError, match="canonical PartRenderData"):
        api.project_operator_engineering_drawing(bad)
