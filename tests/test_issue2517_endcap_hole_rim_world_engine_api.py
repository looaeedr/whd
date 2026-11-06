"""#2517 real EndCap CUTTING-hole 3D rim projection is Engine-owned."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api, project_endcap_cutting_hole_rim_segments
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _material(hole=True):
    shell = [(0, 0), (100, 0), (100, 100), (0, 100)]
    inner = [(20, 20), (30, 20), (30, 30), (20, 30)]
    return Polygon(shell, [inner] if hole else [])


def _request():
    # A single canonical unfolded surface; no fold or ad-hoc compensation.
    return (
        [{"len": 100, "core": "W"}],
        [{"len": 100, "core": "D"}],
        (),
        [[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
        [[(8.0, 9.0, 10.0), (9.0, 9.0, 10.0), (8.0, 10.0, 10.0)]],
    )


def test_public_engine_only_projects_actual_material_holes_for_both_endcaps():
    x, y, guides, local, world = _request()
    assert manufacturing_api.project_endcap_cutting_hole_rim_segments is (
        project_endcap_cutting_hole_rim_segments
    )
    head = project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, local, world, "head",
    )
    tail = project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, local, world, "tail",
    )
    assert len(head) == len(tail) == 4
    assert all(len(point) == 3 for pair in head for point in pair)
    for (a_h, b_h), (a_t, b_t) in zip(head, tail):
        for h, t in ((a_h, a_t), (b_h, b_t)):
            assert h[0] == pytest.approx(t[0])
            assert h[1] + t[1] == pytest.approx(2 * 9.0)
            assert h[2] + t[2] == pytest.approx(2 * 10.0)
    assert head == project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, local, world, "top",
    )
    assert tail == project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, local, world, "bottom",
    )


def test_unknown_placement_and_missing_physical_holes_fail_closed():
    x, y, guides, local, world = _request()
    assert project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, local, world, "box_body",
    ) == ()
    assert project_endcap_cutting_hole_rim_segments(
        _material(False), x, y, guides, local, world, "head",
    ) == ()
    assert project_endcap_cutting_hole_rim_segments(
        _material(), x, y, guides, (), world, "head",
    ) == ()
    assert project_endcap_cutting_hole_rim_segments(
        None, x, y, guides, local, world, "head",
    ) == ()


def test_gui_draws_engine_segments_only_with_same_artist_style(monkeypatch):
    mpl = pytest.importorskip("mpl_toolkits.mplot3d.art3d")
    pair = (((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),)
    called = []
    class FakeAxis:
        def add_collection3d(self, item):
            called.append(("draw", item))
    host = SimpleNamespace(renderer=SimpleNamespace(ax3d=FakeAxis()))
    requests = []
    def port(*args):
        requests.append(args)
        return pair
    monkeypatch.setattr(
        manufacturing_api, "project_endcap_cutting_hole_rim_segments", port,
    )
    monkeypatch.setattr(
        mpl, "Line3DCollection",
        lambda segments, **kwargs: (segments, kwargs),
    )
    x, y, guides, local, world = _request()
    material = _material()
    Phase6FinalSceneRenderHelpersMixin._draw_endcap_cutting_hole_rims(
        host, material, x, y, guides, local, world, "head", "#123456",
    )
    assert requests == [(material, x, y, guides, local, world, "head")]
    assert called == [("draw", (pair, {
        "colors": "#123456", "linewidths": 1.4, "linestyles": "solid"
    }))]
    source = inspect.getsource(
        Phase6FinalSceneRenderHelpersMixin._draw_endcap_cutting_hole_rims
    )
    assert "manufacturing_api.project_endcap_cutting_hole_rim_segments(" in source
    for forbidden in ("inner_ring.coords", "self._map_xy(",
                      "placed_surface[0][0]", "sign ="):
        assert forbidden not in source


def test_headless_owner_does_not_import_gui_or_display_system():
    from ae_engine import endcap_cutting_hole_rims as owner
    source = inspect.getsource(owner)
    assert "tkinter" not in source and "matplotlib" not in source
    assert "phase6_" not in source
