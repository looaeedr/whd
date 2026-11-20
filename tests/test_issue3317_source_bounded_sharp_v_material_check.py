"""#3317: actual CUTTING-bound sharp V candidate, with T from the original source.

CHECK only: no absent inside R, BA, radius-to-T ratio, manufacturing
CUTTING/BEND/MARKING or fabricated stock is synthesized.
"""
from __future__ import annotations

from copy import deepcopy

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _source(angle, second_height=30, first_height=20):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    args = dict(
        thickness_mm=2, first_flange_height_mm=first_height,
        second_flange_height_mm=second_height,
        second_fold_angle_deg=angle, relief_mode="ROUND_R",
    )
    ideal = api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **args,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    original_cut = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y),
        Vec2(b.x, 100), Vec2(-100, 100),
    ), layer="CUTTING", closed=True)
    return DrawingScene([original_cut, first, second]), ideal


@pytest.mark.parametrize("angle", (60, 90, 120))
@pytest.mark.parametrize("heights", ((20, 20), (20, 30)))
def test_sharp_v_full_closed_cut_bound_to_actual_source_without_any_r_ba(
    angle, heights,
):
    scene, ideal = _source(angle, second_height=heights[1],
                           first_height=heights[0])
    original = deepcopy(scene.primitives)
    result = api.project_v_miter_sharp_source_perimeter_check(scene, ideal)
    assert result.manufacturing_status.endswith("UNCERTIFIED")
    assert result.removed_material_area_mm2 > 0
    assert result.remaining_material_area_mm2 > 0
    assert result.source_material_area_mm2 == pytest.approx(
        result.removed_material_area_mm2 + result.remaining_material_area_mm2,
    )
    removed = Polygon((v.x, v.y) for v in result.removed_corner_outline)
    remaining = Polygon((v.x, v.y) for v in result.remaining_outline)
    assert removed.is_valid and remaining.is_valid
    assert removed.intersection(remaining).area == pytest.approx(0, abs=1e-7)
    assert tuple(scene.primitives) == tuple(original)
    assert len([p for p in scene.primitives if p.layer == "CUTTING"]) == 1


def test_original_cutting_perimeter_is_never_overwritten_even_if_rays_extend():
    scene, ideal = _source(90)
    cut = scene.primitives[0]
    expanded = PolylinePrimitive(tuple(
        Vec2(v.x + 10, v.y) if v.x > 0 else v for v in cut.points
    ), layer="CUTTING", closed=True)
    original = DrawingScene([expanded, *scene.primitives[1:]])
    result = api.project_v_miter_sharp_source_perimeter_check(original, ideal)
    assert result.removed_material_area_mm2 > 0
    assert any(
        abs(factor - 1) > 1e-6 for factor in (
            result.first_perimeter_to_ideal_reach_ratio,
            result.second_perimeter_to_ideal_reach_ratio,
        )
    )
    assert original.primitives[0] is expanded
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_real_perimeter_validation_rejects_missing_or_duplicated_cutting():
    scene, ideal = _source(90)
    with pytest.raises(GeometryError, match="exactly one"):
        api.project_v_miter_sharp_source_perimeter_check(
            DrawingScene([*scene.primitives, scene.primitives[0]]), ideal,
        )
    with pytest.raises(GeometryError, match="exactly one"):
        api.project_v_miter_sharp_source_perimeter_check(
            DrawingScene(scene.primitives[1:]), ideal,
        )


def test_candidate_is_only_check_layer_in_dxf_roundtrip(tmp_path):
    scene, ideal = _source(120)
    check = api.project_v_miter_sharp_source_perimeter_check(scene, ideal)
    preview = DrawingScene([
        PolylinePrimitive(
            check.remaining_outline, layer="CHECK", closed=True,
        )
    ])
    path = tmp_path / "unverified_v_corner.dxf"
    save_scene_dxf(path, preview)
    actual = list(ezdxf.readfile(path).modelspace())
    assert len(actual) == 1 and actual[0].dxf.layer == "CHECK"
    assert actual[0].dxftype() == "LWPOLYLINE"
    coords = tuple(actual[0].get_points("xy"))
    expected = tuple((p.x, p.y) for p in check.remaining_outline)
    assert len(coords) == len(expected)
    for point, wanted in zip(coords, expected):
        assert point == pytest.approx(wanted)
    assert not any(e.dxf.layer in {"CUTTING", "BEND", "MARKING"} for e in actual)
