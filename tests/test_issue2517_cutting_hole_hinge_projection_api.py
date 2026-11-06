"""#2517: genuine Door CUTTING-hole and verified fixing hinge via Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon, MultiPolygon, box

from ae_engine import (
    manufacturing_api, project_independent_cutting_hole_rim_segments,
    project_independent_fixed_plate_hinge_segment,
)
from ae_engine.assembly_geometry import place_assembly_points
from ae_engine.independent_part_view_mesh import IndependentPartViewMesh
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _profiles():
    return (({"len": 100, "core": "W"},), ({"len": 80, "core": "D"},), ())


def _mat(hole=True):
    return Polygon(
        [(0, 0), (100, 0), (100, 80), (0, 80)],
        [[(20, 10), (40, 10), (40, 30), (20, 30)]] if hole else [],
    )


def _ref():
    return (((0, 0, 0), (100, 0, 0), (0, 80, 0)),)


def test_true_cutting_hole_local_and_assembly_world_are_source_exact():
    x, y, guides = _profiles()
    lines = project_independent_cutting_hole_rim_segments(_mat(), x, y, guides)
    assert len(lines) == 4 and isinstance(lines, tuple)
    assert lines[0] == ((-30.0, -30.0, 0.0), (-10.0, -30.0, 0.0))
    assert lines[-1][1] == lines[0][0]
    assert manufacturing_api.project_independent_cutting_hole_rim_segments is (
        project_independent_cutting_hole_rim_segments
    )
    world = project_independent_cutting_hole_rim_segments(
        _mat(), x, y, guides,
        local_reference=_ref(), placement="door",
        dimensions=(100, 80, 40), offset=(7, 8, 9),
    )
    assert world == tuple(
        place_assembly_points(line, _ref(), "door", (100, 80, 40), (7, 8, 9))
        for line in lines
    )


def test_no_cutting_or_missing_reference_never_invents_holes():
    x, y, g = _profiles()
    assert len(project_independent_cutting_hole_rim_segments(
        MultiPolygon([_mat(), box(110, 0, 130, 20)]), x, y, g,
    )) == 4
    assert project_independent_cutting_hole_rim_segments(_mat(False), x, y, g) == ()
    assert project_independent_cutting_hole_rim_segments(None, x, y, g) == ()
    assert project_independent_cutting_hole_rim_segments(
        _mat(), x, y, g, local_reference=(),
    ) == ()


def test_only_existing_engine_view_hinge_is_projected():
    x, y, guides = _profiles()
    view = IndependentPartViewMesh(
        triangles=(), x_profile=x, y_profile=y, fold_guides=guides,
        fixed_plate_hinge_y=22.0,
    )
    source = SimpleNamespace(metadata={"source_flat_dimensions": (100, 80)})
    assert project_independent_fixed_plate_hinge_segment(source, view) == (
        (-50.0, -18.0, 0.0), (50.0, -18.0, 0.0),
    )
    assert manufacturing_api.project_independent_fixed_plate_hinge_segment is (
        project_independent_fixed_plate_hinge_segment
    )
    assert project_independent_fixed_plate_hinge_segment(
        source, IndependentPartViewMesh((), x, y, guides),
    ) == ()


def test_gui_door_only_draws_engine_lines_and_retains_style(monkeypatch):
    art = pytest.importorskip("mpl_toolkits.mplot3d.art3d")
    drawn, called = [], []
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=SimpleNamespace(
        add_collection3d=lambda collection: drawn.append(collection),
    )))
    segments = (((1, 2, 3), (4, 5, 6)),)
    monkeypatch.setattr(
        manufacturing_api, "project_independent_cutting_hole_rim_segments",
        lambda *args, **kw: called.append((args, kw)) or segments,
    )
    monkeypatch.setattr(art, "Line3DCollection",
                        lambda rows, **kw: (rows, kw))
    x, y, g = _profiles()
    n = Phase6FinalSceneRenderHelpersMixin._draw_cutting_hole_rims(
        host, _mat(), x, y, g, local_reference=_ref(), placement="door",
        dimensions=(100, 80, 40), offset=(7, 8, 9),
    )
    assert n == 1 and len(called) == 1
    assert called[0][1] == dict(local_reference=_ref(), placement="door",
                                dimensions=(100, 80, 40), offset=(7, 8, 9))
    assert drawn == [(segments, dict(colors="#22d3ee", linewidths=2.2,
                                     linestyles="solid", zorder=20))]
    method = inspect.getsource(Phase6FinalSceneRenderHelpersMixin._draw_cutting_hole_rims)
    assert "manufacturing_api.project_independent_cutting_hole_rim_segments(" in method
    assert "ring.coords" not in method and "self._map_xy(" not in method


def test_engine_has_no_Tk_Matplotlib_or_Phase6_dependency():
    from ae_engine import final_scene_independent_annotations as owner
    src = inspect.getsource(owner)
    assert "tkinter" not in src and "matplotlib" not in src
    assert "phase6_final_scene" not in src
