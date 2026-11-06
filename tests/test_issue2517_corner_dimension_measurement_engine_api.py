"""#2517: Engine selects canonical physical material before UI labels."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from ae_engine import manufacturing_api
from ae_engine.assembly_collision_corner import measure_material_corner_reliefs
from phase6_corner_dimension_display import render_data_corner_dimension_text
import phase6_corner_dimension_display as gui_display


def _render(material):
    return SimpleNamespace(material=material, pieces=())


def test_headless_public_api_resolves_single_canonical_corner_not_gui_speculation():
    blank = box(0, 0, 100, 80)
    cut = unary_union((box(0, 60, 20, 80), box(0, 50, 10, 60)))
    material = blank.difference(cut)
    source = _render(material)
    groups = manufacturing_api.project_render_corner_relief_measurements(source)
    assert isinstance(groups, tuple) and len(groups) == 1
    assert isinstance(groups[0], manufacturing_api.RenderCornerDimensionGroup)
    assert groups[0].role is None
    assert groups[0].measurements == measure_material_corner_reliefs(material)
    assert groups[0].measurements[0].corner_name == "top_left"
    assert groups[0].measurements[0].secondary_depth == pytest.approx(10)
    assert render_data_corner_dimension_text(source) == "截角尺寸：左上 20×20 + 10×10"


def test_engine_projects_each_actual_physical_piece_in_order_not_parent_preview():
    a = _render(box(0, 0, 100, 80).difference(box(0, 60, 20, 80)))
    b = _render(box(0, 0, 100, 80))
    c = _render(box(0, 0, 100, 80).difference(box(85, 65, 100, 80)))
    bundle = SimpleNamespace(
        material=box(0, 0, 1000, 1000),
        pieces=(
            SimpleNamespace(role="left_side", render_data=a),
            SimpleNamespace(role="back", render_data=b),
            SimpleNamespace(key="right_side", render_data=c),
        ),
    )
    groups = manufacturing_api.project_render_corner_relief_measurements(bundle)
    assert tuple(g.role for g in groups) == ("left_side", "right_side")
    assert tuple(g.measurements[0].corner_name for g in groups) == ("top_left", "top_right")
    assert render_data_corner_dimension_text(bundle) == (
        "截角尺寸：left_side：左上 20×20；right_side：右上 15×15"
    )


def test_blank_or_absent_physical_material_does_not_fabricate_corner_dimensions():
    assert manufacturing_api.project_render_corner_relief_measurements(_render(box(0, 0, 100, 80))) == ()
    assert manufacturing_api.project_render_corner_relief_measurements(_render(None)) == ()
    assert render_data_corner_dimension_text(_render(None)) == "截角尺寸：無"


def test_gui_display_only_delegates_physical_geometry_selection_to_public_engine():
    source = inspect.getsource(gui_display.render_data_corner_dimension_text)
    assert "manufacturing_api.project_render_corner_relief_measurements(" in source
    assert "measure_material_corner_reliefs" not in source
    assert "render_data.pieces" not in source
    assert "render_data.material" not in source
