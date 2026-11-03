"""#2517: Engine owns the standard/CustomFold physical default router."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest
from ae_engine import manufacturing_api as api
from ae_engine import build_operator_default_part_fold_profiles as package_api
from ae_engine import operator_settings_fold_plan as planner
import phase6_settings_profile_projection as gui


def _snapshot(model):
    return {"model": model, "w": 400, "h": 600, "d": 250, "t": 2, "fw": 25,
            "part_dimensions": {"door": {"width": 300, "height": 500},
                                "base_plate": {"width": 250, "height": 450}}}


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("key", ["door", "base_plate", "indicator_box"])
def test_standard_family_fold_routes_without_a_gui_formula(family, key):
    snapshot = _snapshot(family)
    original = deepcopy(snapshot)
    expected = api.build_standard_part_fold_profiles(snapshot, key)
    assert api.build_operator_default_part_fold_profiles(snapshot, key) == expected
    assert gui.build_standard_part_profiles(snapshot, key) == expected
    assert package_api(snapshot, key) == expected
    assert snapshot == original


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("axis", ["X", "Y"])
def test_registered_custom_physical_id_uses_canonical_saved_fold(family, axis):
    catalog = api.CustomPartCatalog()
    key = catalog.add(display_name="加強板", fold_axis=axis,
                      transverse_length=123.456, per_box_count=2)
    snapshot = {**_snapshot(family), "custom_parts": catalog.snapshot()}
    before = deepcopy(snapshot)
    expected = api.build_custom_part_profiles(snapshot, key)
    actual = api.build_operator_default_part_fold_profiles(snapshot, key)
    assert actual == expected == gui.build_standard_part_profiles(snapshot, key)
    assert package_api(snapshot, key) == expected
    assert expected[axis][0]["len"] == pytest.approx(15.)
    assert snapshot == before
    actual[axis][0]["len"] = 999.
    assert api.build_operator_default_part_fold_profiles(snapshot, key) == expected


def test_unregistered_custom_fold_must_not_fall_back_to_standard_profile():
    with pytest.raises((ValueError, KeyError)):
        api.build_operator_default_part_fold_profiles(_snapshot("受電箱"), "custom:97")


def test_full_settings_plan_reuses_exact_operator_part_default_route(monkeypatch):
    original = planner.build_operator_default_part_fold_profiles
    calls = []
    def spy(snapshot, part_key):
        calls.append(part_key)
        return original(snapshot, part_key)
    monkeypatch.setattr(planner, "build_operator_default_part_fold_profiles", spy)
    result = api.plan_operator_settings_fold_profiles(
        settings_values={}, input_snapshot=_snapshot("金庫型"),
        available_parts=("box_body", "head", "door", "base_plate"),
        active_part="door",
    )
    assert calls == ["door", "base_plate"]
    assert result["part_profiles"]["head"] and result["part_profiles"]["door"]
    monkeypatch.setattr(api, "build_operator_default_part_fold_profiles", spy)
    assert gui.build_standard_part_profiles(_snapshot("金庫型"), "door")
    assert calls[-1] == "door"


def test_gui_has_no_branch_on_manufacturing_custom_identity():
    source = inspect.getsource(gui.build_standard_part_profiles)
    assert "manufacturing_api.build_operator_default_part_fold_profiles" in source
    assert "is_custom_part" not in source
    assert "build_custom_part_profiles" not in source
    assert "build_standard_part_fold_profiles" not in source
    engine_source = inspect.getsource(planner)
    assert "from phase6_" not in engine_source
    assert "tkinter" not in engine_source
