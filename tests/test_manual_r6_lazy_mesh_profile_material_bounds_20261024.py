"""R6 actual request-to-assembly profile ownership: lazy material fallbacks."""
from types import SimpleNamespace

import pytest

from phase6_manufacturing_geometry import _phase6_request_profiles_for_material


def part(key, x=(), y=()):
    return SimpleNamespace(part_key=key, x_profile=list(x), y_profile=list(y))


@pytest.mark.parametrize("key", [
    "box_body:left_side", "door", "endcap_head", "box_body:back",
])
def test_r6_explicit_two_axis_profiles_do_not_depend_on_unrelated_bounds(key):
    x = [{"len": 20.0, "core": False}, {"len": 800.0, "core": True}]
    y = [{"len": 1600.0, "core": True}]
    original = part(key, x, y)
    # A malformed edge-view or empty material envelope must not prevent the
    # complete immutable source profiles from being passed to assembly.
    result_x, result_y = _phase6_request_profiles_for_material(
        original, SimpleNamespace(bounds=(0.0, 0.0))
    )
    assert (result_x, result_y) == (x, y)
    assert result_x is not original.x_profile
    assert result_y is not original.y_profile


@pytest.mark.parametrize("key", ["box_body:divider:top", "inner_door:bay:left_frame"])
def test_r6_frame_falls_back_to_y_span_only_if_y_profile_missing(key):
    result = _phase6_request_profiles_for_material(
        part(key, [{"len": 90.0}]),
        SimpleNamespace(bounds=(10.0, 20.0, 110.0, 270.0)),
    )
    assert result == ([{"len": 90.0}], [{"len": 250.0}])


def test_r6_frame_falls_back_to_x_span_only_if_x_profile_missing():
    result = _phase6_request_profiles_for_material(
        part("inner_door:bay:top_frame", y=[{"len": 46.0}]),
        SimpleNamespace(bounds=(10.0, 20.0, 710.0, 270.0)),
    )
    assert result == ([{"len": 700.0}], [{"len": 46.0}])


def test_r6_whole_body_always_uses_actual_material_height():
    result = _phase6_request_profiles_for_material(
        part("box_body", x=[{"len": 100.0}], y=[{"len": 1.0}]),
        SimpleNamespace(bounds=(-40.0, 10.0, 160.0, 330.0)),
    )
    assert result == ([{"len": 100.0}], [{"len": 320.0}])


@pytest.mark.parametrize("bounds", [
    (), (0.0, 0.0), (0.0, 0.0, 100.0, 0.0),
    (0.0, 0.0, float("nan"), 300.0),
    (0.0, 0.0, float("inf"), 300.0),
    (0.0, True, 100.0, 300.0),
])
def test_r6_required_material_fallback_fails_closed_on_invalid_bounds(bounds):
    with pytest.raises(ValueError, match="physical material bounds unavailable"):
        _phase6_request_profiles_for_material(
            part("box_body:divider:mid", x=[{"len": 80.0}]),
            SimpleNamespace(bounds=bounds),
        )


def test_r6_complete_divider_profiles_ignore_non_authoritative_bad_material_bounds():
    x = [{"len": 80.0}]
    y = [{"len": 500.0}]
    assert _phase6_request_profiles_for_material(
        part("box_body:divider:mid", x, y),
        SimpleNamespace(bounds=(0.0, 0.0)),
    ) == (x, y)
