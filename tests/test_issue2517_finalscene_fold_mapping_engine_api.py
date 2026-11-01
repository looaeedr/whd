"""#2517: FinalScene Fold mapping must reuse canonical Engine world geometry."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry_folded_mesh import (
    _profile_base_index, _profile_geometry, _profile_map,
    _profile_flat_map, _fold_mask_for_cross_coordinate,
    _profile_map_with_guides,
)
import phase6_final_scene_projection as gui


PROFILE = [
    {"len": 20.0, "angle": -90.0},
    {"len": 60.0, "core": "W"},
    {"len": 20.0, "angle": 90.0},
]


@pytest.mark.parametrize("profile", [
    PROFILE,
    [{"len": 22.0, "core": "D"}, {"len": 78.0, "core": "W_BACK"}],
    [{"len": 20.0, "core": "D"}, {"len": 60.0, "core": "W_PART"},
     {"len": 20.0, "core": "D"}],
    [],
])
def test_physical_base_and_folded_material_chain_match_engine(profile):
    assert api.fold_profile_base_index(profile) == _profile_base_index(profile)
    assert gui._phase6_profile_base_index(profile) == _profile_base_index(profile)
    for mask in (None, [False, True], [True, False]):
        expected = _profile_geometry(profile, enabled_folds=mask)
        assert api.fold_profile_geometry(profile, enabled_folds=mask) == expected
        assert gui._phase6_profile_geometry(profile, enabled_folds=mask) == expected
        bounds, folded = expected
        for position in (0.0, 10.0, 50.0, 110.0):
            assert api.fold_profile_map(position, bounds, folded) == pytest.approx(
                _profile_map(position, bounds, folded)
            )
            assert gui._phase6_profile_map(position, bounds, folded) == pytest.approx(
                _profile_map(position, bounds, folded)
            )
            assert api.fold_profile_flat_map(
                position, bounds, profile=profile,
            ) == _profile_flat_map(position, bounds, profile=profile)
            assert gui._phase6_profile_flat_map(
                position, bounds, profile=profile,
            ) == _profile_flat_map(position, bounds, profile=profile)


def test_partial_bend_spans_affect_only_correct_cross_section():
    fold = SimpleNamespace(axis="X", position=20.0, span_start=5.0, span_end=25.0)
    for cross, wanted in ((10.0, (True, True)), (40.0, (False, True))):
        original = _fold_mask_for_cross_coordinate(
            PROFILE, "X", cross, (fold,),
        )
        assert original == wanted
        assert api.fold_profile_bend_mask(PROFILE, "X", cross, (fold,)) == original
        assert gui._phase6_fold_mask_for_cross_coordinate(
            PROFILE, "X", cross, (fold,),
        ) == original
        for position in (0.0, 20.0, 35.0, 70.0):
            expected = _profile_map_with_guides(
                position, cross, PROFILE, axis="X", fold_guides=(fold,),
            )
            assert api.fold_profile_map_with_guides(
                position, cross, PROFILE, axis="X", fold_guides=(fold,),
            ) == pytest.approx(expected)
            assert gui._phase6_profile_map_with_guides(
                position, cross, PROFILE, axis="X", fold_guides=(fold,),
            ) == pytest.approx(expected)


def test_receiving_source_owned_formed_length_uses_real_formed_leg_not_cut_length():
    profile = [
        {"len": 33.0, "formed_length": 35.0,
         "phase6_key": "receiving_left_second", "angle": -90.0},
        {"len": 60.0, "core": "W"},
    ]
    expected = _profile_geometry(profile)
    assert expected[0] == (0.0, 33.0, 93.0)
    assert api.fold_profile_geometry(profile) == expected
    assert gui._phase6_profile_geometry(profile) == expected
    with pytest.raises(ValueError, match="RECEIVING_NFB_FORMED_LENGTH_INVALID"):
        api.fold_profile_geometry([
            {"len": 33.0, "formed_length": 32.0,
             "phase6_key": "receiving_left_second", "angle": -90.0},
            {"len": 60.0, "core": "W"},
        ])


def test_gui_is_adapter_only_not_a_duplicate_folding_or_angle_owner(monkeypatch):
    calls = []
    original = api.fold_profile_geometry
    def spy(profile, *, enabled_folds=None):
        calls.append(enabled_folds)
        return original(profile, enabled_folds=enabled_folds)
    monkeypatch.setattr(api, "fold_profile_geometry", spy)
    assert gui._phase6_profile_geometry(PROFILE, enabled_folds=[False, True])
    assert calls == [[False, True]]
    for name in (
        "_phase6_profile_base_index", "_phase6_profile_geometry",
        "_phase6_fold_mask_for_cross_coordinate", "_phase6_profile_map_with_guides",
        "_phase6_profile_map", "_phase6_profile_flat_map",
    ):
        source = inspect.getsource(getattr(gui, name))
        assert "manufacturing_api.fold_profile_" in source
        assert "math.sin(" not in source and "math.cos(" not in source
        assert "current_angle" not in source and "float(_num(" not in source
