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


def test_issue1359_corner_policy_owner_is_reexported_one_way():
    from ae_engine import sheetmetal_corner_policy
    assert sheetmetal_geometry.FourCornerTypePolicy is sheetmetal_corner_policy.FourCornerTypePolicy
    assert sheetmetal_geometry.resolve_corner_relief is sheetmetal_corner_policy.resolve_corner_relief
    assert sheetmetal_geometry.box_body_vertical_offsets is sheetmetal_corner_policy.box_body_vertical_offsets
    assert sheetmetal_geometry.VAULT_ENDCAP_CORNER_POLICY is sheetmetal_corner_policy.VAULT_ENDCAP_CORNER_POLICY
    assert len(inspect.getsource(sheetmetal_geometry).splitlines()) < 900
    owner = inspect.getsource(sheetmetal_corner_policy)
    assert "from .sheetmetal_geometry import" not in owner
    assert "import ae_engine.sheetmetal_geometry" not in owner


def test_issue1359_four_side_and_shared_owners_are_one_way():
    from ae_engine import sheetmetal_geometry_shared
    from ae_engine import sheetmetal_four_side_geometry
    assert sheetmetal_geometry.placed_corner_cut_polygons is sheetmetal_geometry_shared.placed_corner_cut_polygons
    assert sheetmetal_geometry.FourSideFlangeGeometry is sheetmetal_four_side_geometry.FourSideFlangeGeometry
    assert sheetmetal_geometry.build_four_side_outline is sheetmetal_four_side_geometry.build_four_side_outline
    assert sheetmetal_geometry.build_four_side_bend_segments is sheetmetal_four_side_geometry.build_four_side_bend_segments
    assert len(inspect.getsource(sheetmetal_geometry).splitlines()) < 650
    for owner in (inspect.getsource(sheetmetal_geometry_shared), inspect.getsource(sheetmetal_four_side_geometry)):
        assert "from .sheetmetal_geometry import" not in owner
        assert "import ae_engine.sheetmetal_geometry" not in owner
