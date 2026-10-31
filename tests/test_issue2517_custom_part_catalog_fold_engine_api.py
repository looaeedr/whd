"""#2517: custom physical identity and X/Y Fold manufacturing originate in Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import CustomFoldPartSpec
from phase6_custom_parts import CustomPartCatalog as LegacyCatalog, custom_part_only_change
from phase6_custom_fold_profiles import (
    build_custom_part_profiles as legacy_profiles, custom_part_spec as legacy_spec,
)


def _saved(axis="X", span=123.456):
    catalog = manufacturing_api.CustomPartCatalog()
    key = catalog.add(display_name="加強板", fold_axis=axis,
                      transverse_length=span, per_box_count=2)
    return catalog, key, {"model": "金庫型", "t": 2,
                          "custom_parts": catalog.snapshot()}


def test_public_api_and_legacy_facades_are_same_engine_code():
    assert manufacturing_api.CustomPartCatalog is LegacyCatalog
    assert manufacturing_api.build_custom_part_profiles is legacy_profiles
    assert manufacturing_api.custom_part_spec is legacy_spec
    assert manufacturing_api.custom_part_only_change is custom_part_only_change
    assert manufacturing_api.is_custom_part("custom:9")
    for module_name in ("ae_engine.custom_part_catalog", "ae_engine.custom_fold_api"):
        module = __import__(module_name, fromlist=("__file__",))
        content = inspect.getsource(module)
        assert "from phase6_" not in content
        assert "import phase6_" not in content
        assert "tkinter" not in content


@pytest.mark.parametrize("axis", ("X", "Y"))
@pytest.mark.parametrize("thickness", (1, 2, 2.5, 3))
def test_real_custom_fold_material_segments_and_formed_face(axis, thickness):
    catalog, key, snap = _saved(axis)
    snap["t"] = thickness
    before = deepcopy(snap)
    profiles = manufacturing_api.build_custom_part_profiles(snap, key)
    other = "Y" if axis == "X" else "X"
    assert [row["len"] for row in profiles[axis]] == pytest.approx(
        [17 - thickness, 100 - thickness]
    )
    assert [row.get("phase6_key") for row in profiles[axis]] == [
        "custom_flange", "custom_face"
    ]
    assert profiles[other] == [{
        "len": 123.456, "core": "CUSTOM_SPAN", "phase6_key": "custom_span",
    }]
    spec = manufacturing_api.custom_part_spec(snap, key, profiles=profiles)
    assert isinstance(spec, CustomFoldPartSpec)
    assert spec.physical_id == key and spec.fold_axis == axis
    assert spec.transverse_length == pytest.approx(123.456)
    assert [row.length for row in spec.fold_profile] == pytest.approx(
        [17 - thickness, 100 - thickness]
    )
    assert [row.formed_length for row in spec.fold_profile] == [17, 100]
    assert legacy_profiles(snap, key) == profiles
    assert legacy_spec(snap, key, profiles=profiles) == spec
    assert snap == before


def test_nonrecycled_custom_identity_metadata_and_immutable_snapshot():
    cat = manufacturing_api.CustomPartCatalog()
    first = cat.add(display_name="A", fold_axis="X", transverse_length=100)
    assert cat.remove(first)
    second = cat.add(display_name="B", fold_axis="Y", transverse_length=150)
    assert (first, second) == ("custom:1", "custom:2")
    assert cat.get(second)["physical_id"] == second
    item = cat.get(second)
    item["transverse_length"] = 999
    assert cat.get(second)["transverse_length"] == 150
    assert cat.snapshot()["next_id"] == 3


@pytest.mark.parametrize("bad", (True, 0, -1, float("nan"), float("inf"), 17))
def test_invalid_custom_thickness_refused_by_public_engine(bad):
    _, key, saved = _saved()
    with pytest.raises(ValueError):
        manufacturing_api.build_custom_part_profiles({**saved, "t": bad}, key)


def test_custom_fold_missing_descriptor_and_mismatched_flat_span_fail_closed():
    _, key, saved = _saved()
    with pytest.raises(ValueError, match="metadata"):
        manufacturing_api.custom_part_spec({"t": 2}, key)
    bad = manufacturing_api.build_custom_part_profiles(saved, key)
    bad["Y"][0]["len"] = 900
    with pytest.raises(ValueError, match="metadata"):
        manufacturing_api.custom_part_spec(saved, key, profiles=bad)


def test_custom_only_change_is_pure_and_does_not_hide_main_box_edits():
    _, key, saved = _saved()
    before = {"w": 800, "h": 1600, "workspace": {
        "custom_parts": saved["custom_parts"], "part_profiles": {}
    }}
    after = deepcopy(before)
    after["workspace"]["custom_parts"]["items"][key]["display_name"] = "new"
    assert manufacturing_api.custom_part_only_change(before, after)
    assert before["workspace"]["custom_parts"]["items"][key]["display_name"] == "加強板"
    after["w"] += 10
    assert not manufacturing_api.custom_part_only_change(before, after)
