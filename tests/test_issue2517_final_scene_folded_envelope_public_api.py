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
    assert canonical == ((10.0, 20.0, 4.0), (
        (0.0, 10.0), (0.0, 20.0), (-2.0, 2.0),
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
