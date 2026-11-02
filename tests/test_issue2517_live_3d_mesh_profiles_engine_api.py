"""#2517: interactive Fold Designer 3D profile physical source is Engine-owned."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest
from ae_engine import manufacturing_api as api
from ae_engine.box_body_structure import project_side_back_3d_input_fold_to_physical
from ae_engine.cabinet_types import policy as family
import fold_designer_bridge as bridge


def project(key, *, active=None, current=None, saved=None, vault=None, model="受電箱", material=None):
    return api.project_operator_3d_mesh_profiles(
        key, material=material if material is not None else
        SimpleNamespace(bounds=(10., 20., 210., 330.)),
        active_part=active, active_profiles=current or {},
        saved_profiles=saved or {}, vault_profiles=vault or {},
        snapshot={"model": model}, thickness=2.0,
    )


def test_vault_box_body_keeps_source_x_and_uses_material_y():
    vault = {"箱身": [{"len": 28.0, "phase6_key": "zl1"}]}
    old = deepcopy(vault)
    assert project("box_body", active="box_body", vault=vault,
                   current={"X": [{"len": 900}], "Y": [{"len": 1}]}) == (
                       vault["箱身"], [{"len": 310.0}])
    assert vault == old


@pytest.mark.parametrize("model", ["金庫型", "受電箱", "RECEIVING"])
@pytest.mark.parametrize("role", ["left_side", "right_side", "back"])
def test_side_back_matches_original_family_one_way_projection(model, role):
    key = "box_body:" + role
    source = {"X": [
        {"len": 20., "angle": 90., "phase6_key": "zl1", "ui_len_add": 2.},
        {"len": 100., "angle": -90., "phase6_key": "d_left", "core": "D"},
        {"len": 25., "phase6_key": "rear"},
    ], "Y": [{"len": 1600.}]}
    saved = deepcopy(source)
    physical = project_side_back_3d_input_fold_to_physical(
        source["X"], role=role,
        receiving=family.box_body_profile_uses_outside_dimensions({"model": model}),
        thickness=2.0,
    )
    assert project(key, active=key, current=source, model=model) == (physical, source["Y"])
    assert source == saved


def test_active_vs_saved_navigation_source_remains_distinct():
    current = {"X": [{"len": 44.}], "Y": [{"len": 65.}]}
    saved = {"X": [{"len": 9.}], "Y": [{"len": 8.}]}
    assert project("door", active="door", current=current, saved=saved) == (
        current["X"], current["Y"])
    assert project("door", active="head", current=current, saved=saved) == (
        saved["X"], saved["Y"])


@pytest.mark.parametrize("key,axis", [
    ("box_body:divider:top", "y"),
    ("inner_door:bay:left_frame", "y"),
    ("inner_door:bay:top_frame", "x"),
])
def test_partial_frame_uses_only_missing_material_span(key, axis):
    current = {"X": [{"len": 34.}]} if axis == "y" else {"Y": [{"len": 37.}]}
    x, y = project(key, active=key, current=current)
    if axis == "y":
        assert x == current["X"] and y == [{"len": 310.}]
    else:
        assert x == [{"len": 200.}] and y == current["Y"]


@pytest.mark.parametrize("bounds", [
    (), (0., 0.), (0., 0., 100., 0.), (0., 0., float("nan"), 50.),
    (0., 0., 100., float("inf")), (0., False, 100., 50.),
])
def test_missing_axis_rejects_unphysical_material_bounds(bounds):
    with pytest.raises(ValueError, match="physical material bounds unavailable"):
        project("box_body:divider:test", active="box_body:divider:test",
                current={"X": [{"len": 34.}]}, material=SimpleNamespace(bounds=bounds))


def test_complete_profiles_never_read_unrelated_material_bounds():
    class Invalid:
        @property
        def bounds(self):
            raise AssertionError("unrelated physical bounds read")
    src = {"X": [{"len": 20.}], "Y": [{"len": 30.}]}
    assert project("door", active="door", current=src, material=Invalid()) == (
        src["X"], src["Y"])


def test_gui_physical_fold_is_public_engine_only_and_registry_reuses_it():
    source = inspect.getsource(bridge._phase6_mesh_profiles_for_part)
    assert "manufacturing_api.project_operator_3d_mesh_profiles(" in source
    for bad in ("project_side_back_3d_input_fold_to_physical(",
                "box_body_profile_uses_outside_dimensions(", "material.bounds"):
        assert bad not in source
    assert "_phase6_mesh_profiles_for_part(" in inspect.getsource(
        bridge._phase6_registry_validate_candidate_3d)
    import ae_engine.assembly_mesh_profiles as owner
    assert "from gui_modules" not in inspect.getsource(owner)
    assert "from phase6_" not in inspect.getsource(owner)
