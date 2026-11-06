"""#2517 final manufactured BEND/CUTTING Fold projection owner must be Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest
from shapely.geometry import box

from ae_engine import (
    manufacturing_api,
    scene_fold_boundaries,
    profile_to_scene_boundaries,
    fold_ownership_exemptions,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_projection import (
    _phase6_scene_fold_boundaries,
    _phase6_profile_to_scene_boundaries,
    _phase6_fold_ownership_exemptions,
)


def _source():
    drawing = DrawingScene()
    drawing.add_line((10, 0), (10, 80), layer="BEND")
    drawing.add_line((90, 0), (90, 80), layer="BEND")
    drawing.add_line((0, 20), (100, 20), layer="BEND")
    drawing.add_line((0, 20.0000001), (100, 20.0000001), layer="BEND")
    drawing.add_line((40, 10), (60, 40), layer="BEND")  # diagonal is not a BEND station
    drawing.add_line((40, 0), (40, 80), layer="MARKING")
    return drawing


def test_headless_fold_source_matches_original_BEND_stations_and_UI_delegation():
    scene, material = _source(), box(0, 0, 100, 80)
    actual = scene_fold_boundaries(scene, material)
    assert manufacturing_api.scene_fold_boundaries is scene_fold_boundaries
    assert actual == ((0.0, 10.0, 90.0, 100.0), (0.0, 20.0, 80.0))
    assert _phase6_scene_fold_boundaries(scene, material) == actual
    empty = scene_fold_boundaries(DrawingScene(), material)
    assert empty == ((0.0, 100.0), (0.0, 80.0))


def test_material_segment_lengths_use_final_BEND_not_old_ui_compensation():
    operator = [
        {"len": 11.0, "angle": -90, "ui_len_add": 2.0},
        {"len": 78.0, "core": "W", "ui_len_add": 4.0},
        {"len": 11.0, "angle": 90, "ui_len_add": 2.0},
    ]
    old = deepcopy(operator)
    actual = profile_to_scene_boundaries(operator, (0, 10, 90, 100))
    assert actual == [
        {"len": 10.0, "angle": -90},
        {"len": 80.0, "core": "W"},
        {"len": 10.0, "angle": 90},
    ]
    assert operator == old
    assert _phase6_profile_to_scene_boundaries(operator, (0, 10, 90, 100)) == actual
    assert profile_to_scene_boundaries(operator, (0, 100)) == old


def test_cut_polygon_owns_the_correct_side_of_each_corner_fold():
    x_bounds, y_bounds = (0, 10, 90, 100), (0, 10, 90, 100)
    horizontal_only = box(2, 0, 8, 8)
    vertical_only = box(0, 2, 8, 8)
    both = box(0, 0, 100, 100)
    for material, expected in ((horizontal_only, "x"), (vertical_only, "y")):
        result = fold_ownership_exemptions(material, x_bounds, y_bounds)
        assert len(result) == 1 and result[0][0] == expected
        assert result[0][1].equals(material)
        old = _phase6_fold_ownership_exemptions(material, x_bounds, y_bounds)
        assert old[0][0] == expected and old[0][1].equals(material)
    assert fold_ownership_exemptions(both, x_bounds, y_bounds) == []
    assert fold_ownership_exemptions(both, (0, 100), y_bounds) == []


def test_phase6_contains_no_second_material_source_logic():
    for old, name in (
        (_phase6_scene_fold_boundaries, "scene_fold_boundaries"),
        (_phase6_profile_to_scene_boundaries, "profile_to_scene_boundaries"),
        (_phase6_fold_ownership_exemptions, "fold_ownership_exemptions"),
    ):
        src = inspect.getsource(old)
        assert f"manufacturing_api.{name}(" in src
        for forbidden in ("material.intersection(", "segment.len =", "primitive.p1.x",
                          "LineString(", "float(boundaries[i"):
            assert forbidden not in src
    from ae_engine import final_scene_fold_source as owner
    source = inspect.getsource(owner)
    assert "phase6_" not in source and "tkinter" not in source
    assert "matplotlib" not in source
