"""#2517: FinalScene boundary and crease projection belongs only to Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest
from ae_engine import manufacturing_api as api
from ae_engine import project_physical_solid_mesh_display_segments as package_api
from ae_engine.solid_mesh_feature_edges import project_physical_solid_mesh_display_segments as source
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _identity(segments):
    return {tuple(sorted((tuple(a), tuple(b)))) for a, b in segments}


def _square():
    return (
        ((0., 0., 0.), (1., 0., 0.), (1., 1., 0.)),
        ((0., 0., 0.), (1., 1., 0.), (0., 1., 0.)),
    )


def _fold():
    return (
        ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        ((1., 0., 0.), (0., 0., 0.), (0., 0., 1.)),
    )


def test_flat_sheet_displays_outline_without_coplanar_tessellation_diagonal():
    mesh = _square()
    old = deepcopy(mesh)
    boundary = api.project_physical_solid_mesh_display_segments(mesh, mode="boundary")
    assert len(boundary) == 4
    assert api.project_physical_solid_mesh_display_segments(mesh, mode="crease") == ()
    assert _identity(boundary) == _identity(api.physical_solid_mesh_feature_segments(mesh))
    assert mesh == old


def test_fold_crease_matches_existing_engine_edges_with_no_duplicates():
    tris = _fold()
    boundary = api.project_physical_solid_mesh_display_segments(tris, mode="boundary")
    crease = api.project_physical_solid_mesh_display_segments(tris, mode="crease")
    combined = api.project_physical_solid_mesh_display_segments(tris, mode="boundary_and_crease")
    assert (len(boundary), len(crease), len(combined)) == (4, 1, 5)
    assert _identity(crease).isdisjoint(_identity(boundary))
    assert _identity(combined) == _identity(boundary) | _identity(crease)
    assert combined == api.physical_solid_mesh_feature_segments(tris)
    assert combined == source(tris, mode="boundary_and_crease")
    assert combined == package_api(tris, mode="boundary_and_crease")


@pytest.mark.parametrize("mode", [None, "", True, "phantom", ("boundary",)])
def test_unsupported_mesh_mode_fails_closed(mode):
    with pytest.raises(ValueError, match="unknown physical mesh display mode"):
        api.project_physical_solid_mesh_display_segments(_fold(), mode=mode)


def test_zero_area_triangle_does_not_create_physical_edge():
    fake = (((0., 0., 0.), (0., 0., 0.), (0., 0., 0.)),)
    for mode in ("boundary", "crease", "boundary_and_crease"):
        assert api.project_physical_solid_mesh_display_segments(fake, mode=mode) == ()


def test_gui_uses_only_public_engine_projection_for_both_legacy_views(monkeypatch):
    calls = []
    segments = (((0., 0., 0.), (1., 0., 0.)),)
    def spy(triangles, *, mode, tolerance=1e-6):
        calls.append((triangles, mode))
        return segments
    monkeypatch.setattr(api, "project_physical_solid_mesh_display_segments", spy)
    collections = []
    helper = Phase6FinalSceneRenderHelpersMixin()
    helper.renderer = SimpleNamespace(ax3d=SimpleNamespace(add_collection3d=collections.append))
    tri = _fold()
    helper._add_mesh_boundary_lines(tri, "#112233")
    helper._add_mesh_boundary_and_crease_lines(tri, "#445566", creases_only=True)
    helper._add_mesh_boundary_and_crease_lines(tri, "#778899", creases_only=False)
    assert [mode for _, mode in calls] == ["boundary", "crease", "boundary_and_crease"]
    assert len(collections) == 3
    for name in ("_add_mesh_boundary_lines", "_add_mesh_boundary_and_crease_lines"):
        body = inspect.getsource(getattr(Phase6FinalSceneRenderHelpersMixin, name))
        assert "manufacturing_api.project_physical_solid_mesh_display_segments" in body
        for forbidden in ("Counter(", "defaultdict(", "math.sqrt(", "def normal(", "round(float("):
            assert forbidden not in body


def test_engine_edge_classifier_does_not_import_gui_or_matplotlib():
    body = inspect.getsource(source)
    assert not any(w in body for w in ("phase6_", "gui_modules", "tkinter", "matplotlib"))
