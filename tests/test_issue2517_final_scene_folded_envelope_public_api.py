# -*- coding: utf-8 -*-
"""#2517: FinalScene outside-envelope physical readback uses a public Engine seam."""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.display_dimensions import folded_outside_envelope as owner
from phase6_final_scene_projection import _phase6_folded_outside_envelope as gui


def _formed_face():
    # A formed material triangle in the XY plane, with normal +Z.
    return [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 20.0, 0.0))]


def test_public_api_and_root_export_original_engine_owner():
    assert api.project_operator_folded_outside_envelope is owner
    assert ae_engine.project_operator_folded_outside_envelope is owner
    assert "project_operator_folded_outside_envelope" in ae_engine.__all__


def test_finalscene_mesh_outside_dimensions_match_engine_and_gui():
    source = _formed_face()
    before = deepcopy(source)
    canonical = owner(source, 2.0)
    # The input is the physical MID-surface: T=2 means two +/-1 mm skins.
    # The old 4-mm expectation compensated T on BOTH sides a second time.
    assert canonical == ((10.0, 20.0, 2.0), (
        (0.0, 10.0), (0.0, 20.0), (-1.0, 1.0),
    ))
    assert api.project_operator_folded_outside_envelope(source, 2.0) == canonical
    assert gui(source, 2.0) == canonical
    assert api.resolve_operator_finished_dimensions(
        "box_body", triangles=source, thickness=2.0,
    ) == canonical[0]
    assert api.resolve_operator_finished_dimensions(
        "door", triangles=source, thickness=2.0,
    ) == canonical[0][:2]
    assert source == before


def test_folded_outside_envelope_matches_real_engine_t_solid_not_blank_or_double_t():
    """A real 90-degree L has different skin normals at its outside extrema."""
    from ae_engine.assembly_geometry_primitives import (
        thicken_triangle_surface, triangle_bounds,
    )

    # A single connected L mid-surface, first leg in XY, second in YZ.
    # Material lengths are 10 and 10, but the formed outside X/Z spans
    # include one outward physical T/2 where material actually exists.
    folded_mid = (
        ((0., 0., 0.), (10., 0., 0.), (0., 20., 0.)),
        ((0., 0., 0.), (0., 20., 0.), (0., 0., 10.)),
    )
    source_copy = deepcopy(folded_mid)
    dims, bounds = owner(folded_mid, 2.0)
    # The old global-normal AABB also added T to the remote extremum,
    # inventing extra width beyond the real 3D skin.
    assert dims == pytest.approx((11., 20., 11.))
    for observed, expected in zip(bounds, ((-1., 10.), (0., 20.), (-1., 10.))):
        assert observed == pytest.approx(expected)
    # Independent physical-world witness: the Engine's actual two skins
    # and shared-edge sidewalls, not a second implementation of Fold/BA.
    thickened = thicken_triangle_surface(folded_mid, 2.0)
    solid_bounds = triangle_bounds(thickened)
    for observed, expected in zip(solid_bounds, bounds):
        assert observed == pytest.approx(expected)
    # A pre-thickened physical shell is already outside: no extra T.
    assert owner(thickened, 0.0) == (dims, bounds)
    assert folded_mid == source_copy
    assert api.project_operator_folded_outside_envelope(folded_mid, 2.0) == (dims, bounds)
    assert gui(folded_mid, 2.0) == (dims, bounds)


def test_real_fold_crease_zero_area_tessellation_does_not_invent_outside():
    # A legal formed viewer can emit a collapsed tessellation helper at a
    # finite crease; only its positive-area physical faces own the AABB.
    valid = _formed_face()[0]
    collapsed = ((0., 0., 0.), (10., 0., 0.), (5., 0., 0.))
    plain = owner((valid,), 2.)
    assert owner((valid, collapsed), 2.) == plain
    # Without a single physical face, no outside envelope is certified.
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        owner((collapsed,), 2.)


def test_forming_90_degree_L_outside_readback_does_not_depend_on_flat_length():
    from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon
    from shapely.geometry import box

    # Real Engine Fold Profile mid mesh: 20-mm flat X includes a 5-mm
    # upright leg; formed outside is measured AFTER the fold, not by
    # treating the unfolded blank's 20 mm as an outside dimension.
    x_profile = (
        {"length": 5.0, "angle": 90.0, "core": False},
        {"length": 15.0, "angle": None, "core": True},
    )
    y_profile = ({"length": 30.0, "angle": None, "core": True},)
    mid = folded_mesh_from_polygon(box(0, 0, 20, 30), x_profile, y_profile)
    assert mid
    formed = owner(mid, 2.0)
    assert formed is not None
    dims, bounds = formed
    # Neither the raw 20-mm blank width nor 20+2T is a valid readback.
    assert dims[0] < 20.0
    assert dims[2] > 2.0
    assert all(lo < hi for lo, hi in bounds)


def test_empty_finalscene_mesh_remains_absent_not_zero_size():
    assert api.project_operator_folded_outside_envelope([], 2.0) is None
    assert gui([], 2.0) is None


@pytest.mark.parametrize("invalid_mesh", (
    [[(0, 0, 0), (10, 0, 0)]],  # missing third vertex
    [[(0, 0, 0), (10, 0, 0), (0, True, 0)]],
    [[(0, 0, 0), (10, 0, 0), (0, float("nan"), 0)]],
    [[(0, 0, 0), (10, 0, 0), (0, float("inf"), 0)]],
    [[(0, 0, 0), (10, 0, 0), (0, 20)]],
    [[(0, 0, 0), (10, 0, 0), (0, 20, 10**1000)]],
))
def test_invalid_mesh_fails_closed_without_source_changes(invalid_mesh):
    original = repr(deepcopy(invalid_mesh))
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        api.project_operator_folded_outside_envelope(invalid_mesh, 2.0)
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        gui(invalid_mesh, 2.0)
    assert repr(invalid_mesh) == original


@pytest.mark.parametrize("invalid_thickness", (True, -2, float("nan"), float("inf"), "bad", 10**1000))
def test_invalid_thickness_fails_closed_without_source_changes(invalid_thickness):
    source = _formed_face()
    before = deepcopy(source)
    with pytest.raises(ValueError, match="FOLDED_ENVELOPE_INVALID_WORLD_MESH"):
        api.project_operator_folded_outside_envelope(source, invalid_thickness)
    assert source == before


def test_finalscene_gui_calls_only_public_engine_envelope():
    import phase6_final_scene_projection as projection
    assert "manufacturing_api.project_operator_folded_outside_envelope(" in getsource(gui)
    assert "from ae_engine.display_dimensions import" not in getsource(projection)
