"""#2517: assembly physical mesh Fold fallback belongs to public Engine API."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_material_mesh_profiles
from phase6_manufacturing_geometry import _phase6_request_profiles_for_material


def _input(key, x=(), y=()):
    return SimpleNamespace(part_key=key, x_profile=list(x), y_profile=list(y))


def _material(bounds):
    return SimpleNamespace(bounds=bounds)


def test_engine_is_public_and_gui_compatibility_has_no_mesh_policy(monkeypatch):
    assert manufacturing_api.resolve_material_mesh_profiles is resolve_material_mesh_profiles
    source = inspect.getsource(_phase6_request_profiles_for_material)
    assert "material.bounds" not in source
    assert 'key.startswith(' not in source
    witness = ([{"len": 8}], [{"len": 9}])
    marker = object()
    monkeypatch.setattr(manufacturing_api, "resolve_material_mesh_profiles", lambda p, m: witness if p is marker else None)
    assert _phase6_request_profiles_for_material(marker, None) is witness


@pytest.mark.parametrize("part_key", ["box_body", "box_body:divider:top", "inner_door:bay:left_frame", "door"])
def test_headless_engine_and_phase6_have_parity_and_do_not_mutate_inputs(part_key):
    part = _input(part_key, [{"len": 80.0, "phase6_key": "left"}])
    before = deepcopy(part.__dict__)
    material = _material((10.0, 20.0, 110.0, 270.0))
    expected = resolve_material_mesh_profiles(part, material)
    assert _phase6_request_profiles_for_material(part, material) == expected
    assert part.__dict__ == before
    assert expected[0] is not part.x_profile
    if part_key == "box_body":
        assert expected[1] == [{"len": 250.0}]
    elif part_key.startswith(("box_body:divider:", "inner_door:")):
        assert expected[1] == [{"len": 250.0}]
    else:
        assert expected[1] == []


def test_engine_uses_x_span_only_if_frame_x_profile_missing():
    part = _input("inner_door:bay:top_frame", y=[{"len": 46.0}])
    assert resolve_material_mesh_profiles(part, _material((10., 20., 710., 270.))) == (
        [{"len": 700.0}], [{"len": 46.0}],
    )


@pytest.mark.parametrize("bad", [(), (0., 0.), (0., 0., 50., 0.), (0., True, 50., 70.),
                                 (0., 0., float("nan"), 70.), (0., 0., float("inf"), 70.)])
def test_required_bounds_fail_closed_without_fallback_to_invented_size(bad):
    with pytest.raises(ValueError, match="physical material bounds unavailable"):
        resolve_material_mesh_profiles(_input("box_body:divider:one", x=[{"len": 10}]), _material(bad))


def test_unrelated_complete_profiles_never_inspect_irrelevant_bounds():
    class BadMaterial:
        @property
        def bounds(self):
            raise AssertionError("irrelevant physical bounds must remain lazy")
    x = [{"len": 10.0}]
    y = [{"len": 20.0}]
    assert resolve_material_mesh_profiles(_input("box_body:divider:mid", x, y), BadMaterial()) == (x, y)
    assert resolve_material_mesh_profiles(_input("door", x), BadMaterial()) == (x, [])
