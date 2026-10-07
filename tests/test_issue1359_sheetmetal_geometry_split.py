from __future__ import annotations

import inspect

from ae_engine import sheetmetal_geometry
from ae_engine import sheetmetal_geometry_core
from ae_engine import sheetmetal_strip_geometry


def test_issue1359_core_values_are_reexported():
    assert sheetmetal_geometry.Vec2 is sheetmetal_geometry_core.Vec2
    assert sheetmetal_geometry.CornerTypeSelection is sheetmetal_geometry_core.CornerTypeSelection
    assert sheetmetal_geometry.ReliefConfig is sheetmetal_geometry_core.ReliefConfig


def test_issue1359_strip_owner_is_reexported_one_way():
    assert sheetmetal_geometry.StripFoldChain is sheetmetal_strip_geometry.StripFoldChain
    assert sheetmetal_geometry.build_strip_outline is sheetmetal_strip_geometry.build_strip_outline
    assert sheetmetal_geometry.build_strip_bend_segments is sheetmetal_strip_geometry.build_strip_bend_segments
    facade = inspect.getsource(sheetmetal_geometry)
    assert len(facade.splitlines()) < 1200
    for owner in (inspect.getsource(sheetmetal_geometry_core), inspect.getsource(sheetmetal_strip_geometry)):
        assert "from .sheetmetal_geometry import" not in owner
        assert "import ae_engine.sheetmetal_geometry" not in owner
