# -*- coding: utf-8 -*-
"""#2517 original Receiving Door marks are recognized by Engine, not GUI."""
from __future__ import annotations

from copy import deepcopy
import inspect

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, PolylinePrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import receiving_multi_settings_window as window


def _poly(points, layer="CUTTING", closed=True):
    return PolylinePrimitive(
        tuple(Vec2(float(x), float(y)) for x, y in points),
        layer=layer, closed=closed,
    )


def _source():
    return DrawingScene([
        _poly(((0, 0), (200, 0), (200, 100), (0, 100))),
        _poly(((30, 30), (50, 30), (50, 50), (30, 50))),
        CirclePrimitive(
            center=Vec2(80, 60), radius=2, layer="CUTTING",
            source_type="nameplate_mount",
        ),
        CirclePrimitive(
            center=Vec2(150, 50), radius=6, layer="CUTTING",
            source_type="unidentified_hole",
        ),
    ])


def test_same_source_geometry_and_identity_for_engine_and_gui():
    original = _source()
    previous = deepcopy(original)
    expected = {
        "nameplate": ((0.4, 0.4, 0.01, 0.02),),
        "handle": ((0.15, 0.7), (0.25, 0.7), (0.25, 0.5), (0.15, 0.5)),
    }
    assert api.project_receiving_original_door_marks(original) == expected
    assert window.extract_original_door_marks(original) == expected
    assert original == previous


def test_missing_or_unidentified_source_never_fabricates_preview_holes():
    assert api.project_receiving_original_door_marks(None) == {"nameplate": (), "handle": ()}
    assert api.project_receiving_original_door_marks(DrawingScene([])) == {
        "nameplate": (), "handle": (),
    }
    # A non-CUTTING outline cannot be treated as an original Door blank.
    scene = DrawingScene([_poly(((0, 0), (200, 0), (200, 100)), layer="CHECK")])
    assert api.project_receiving_original_door_marks(scene) == {
        "nameplate": (), "handle": (),
    }


def test_ambiguous_original_handle_keeps_nameplate_identity_but_no_handle():
    scene = _source()
    scene.add(_poly(((70, 20), (90, 20), (90, 40), (70, 40))))
    result = api.project_receiving_original_door_marks(scene)
    assert result["nameplate"] == ((0.4, 0.4, 0.01, 0.02),)
    assert result["handle"] == ()


def test_gui_has_no_secondary_cutting_geometry_recognition():
    source = inspect.getsource(window.extract_original_door_marks)
    assert "manufacturing_api.project_receiving_original_door_marks(scene)" in source
    assert "CirclePrimitive" not in source
    assert "PolylinePrimitive" not in source
    assert "CUTTING" not in source
    assert "nameplate_mount" not in source
    assert "from ae_engine.sheetmetal_drawing import" not in inspect.getsource(window)
