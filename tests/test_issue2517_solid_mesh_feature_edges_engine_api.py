"""#2517: physical formed mesh feature edges belong to public Engine API."""
from copy import deepcopy
import inspect

import pytest
from shapely.geometry import box
from ae_engine import manufacturing_api as api, physical_solid_mesh_feature_segments
from ae_engine.assembly_geometry import folded_mesh_from_polygon, thicken_triangle_surface
import phase6_final_scene_projection as gui


def unordered(segments):
    return {
        tuple(sorted((tuple(round(float(x), 6) for x in a),
                      tuple(round(float(x), 6) for x in b))))
        for a, b in segments
    }


def test_coplanar_diagonal_is_not_a_physical_feature_edge():
    triangles = (
        ((0, 0, 0), (1, 0, 0), (1, 1, 0)),
        ((0, 0, 0), (1, 1, 0), (0, 1, 0)),
    )
    original = deepcopy(triangles)
    edges = api.physical_solid_mesh_feature_segments(triangles)
    assert len(edges) == 4
    assert unordered(edges) == unordered((
        ((0, 0, 0), (1, 0, 0)),
        ((1, 0, 0), (1, 1, 0)),
        ((1, 1, 0), (0, 1, 0)),
        ((0, 1, 0), (0, 0, 0)),
    ))
    assert edges == gui._phase6_mesh_feature_segments(triangles)
    assert triangles == original


def test_noncoplanar_real_fold_edge_kept_and_degenerate_ignored():
    triangles = (
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ((1, 0, 0), (0, 0, 0), (0, 0, 1)),
        ((0, 0, 0), (0, 0, 0), (0, 0, 0)),
    )
    edges = physical_solid_mesh_feature_segments(triangles)
    assert len(edges) == 5
    assert ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) in unordered(edges)


def test_canonical_real_thickened_sheet_keeps_hole_rims_on_both_skins():
    material = box(0, 0, 100, 60).difference(box(40, 20, 60, 40))
    surface = folded_mesh_from_polygon(
        material, [{"len": 100, "core": "W"}],
        [{"len": 60, "core": "D"}], fold_guides=(),
    )
    triangles = thicken_triangle_surface(surface, 2.0)
    edges = api.physical_solid_mesh_feature_segments(triangles)
    assert edges == gui._phase6_mesh_feature_segments(triangles)
    assert edges == physical_solid_mesh_feature_segments(triangles)
    rims = [
        (a,b) for a,b in edges
        if abs(abs(float(a[2])) - 1) < 1e-6
        and abs(float(a[2]) - float(b[2])) < 1e-6
        and max(abs(float(a[0])), abs(float(b[0]))) <= 10.000001
        and max(abs(float(a[1])), abs(float(b[1]))) <= 10.000001
    ]
    assert len(rims) >= 8
    assert {round(a[2], 3) for a,_ in rims} == {-1.0, 1.0}


def test_gui_only_displays_public_engine_projection(monkeypatch):
    called = []
    original = api.physical_solid_mesh_feature_segments
    def spy(triangles, *, tolerance=1e-6):
        called.append((triangles, tolerance))
        return original(triangles, tolerance=tolerance)
    monkeypatch.setattr(api, "physical_solid_mesh_feature_segments", spy)
    tris = [((0, 0, 0), (1, 0, 0), (0, 1, 0))]
    assert gui._phase6_mesh_feature_segments(tris, tolerance=0.00001)
    assert called == [(tris, 0.00001)]
    source = inspect.getsource(gui._phase6_mesh_feature_segments)
    assert "manufacturing_api.physical_solid_mesh_feature_segments" in source
    assert "math.sqrt" not in source and "normal(" not in source
    assert "defaultdict" not in source
