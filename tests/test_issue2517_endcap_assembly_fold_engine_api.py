"""#2517: EndCap X/Y Fold assembly topology reconciled only by public Engine."""
from copy import deepcopy
from enum import Enum
import inspect

import pytest

from ae_engine import manufacturing_api, endcap_profiles_for_assembly
from gui_modules.application import manufacturing_adapter as adapter


def _values(family):
    return {
        "model": family, "w": 500.0, "h": 600.0, "d": 200.0,
        "t": 2.0, "fw": 29.0, "yl1": 15.0, "yr1": 15.0,
        "ytop1": 16.0, "ybottom1": 15.0,
    }


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("part", ("head", "tail"))
def test_overlay_without_stored_fold_builds_only_engine_flat_x(family, part):
    assert endcap_profiles_for_assembly is manufacturing_api.endcap_profiles_for_assembly
    data = _values(family)
    actual = endcap_profiles_for_assembly(data, None, "OVERLAY", part)
    expected = manufacturing_api.build_endcap_xy_fold_profiles(
        {**data, "assembly_type": "OVERLAY"}, part_key=part,
    )
    assert actual == expected
    assert tuple(row["phase6_key"] for row in actual["X"]) == ("endcap_w_flat",)
    assert not any("angle" in row for row in actual["X"])


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_non_overlay_without_stored_profiles_preserves_legacy_none(family):
    data = _values(family)
    assert endcap_profiles_for_assembly(data, None, "INSERT", "head") is None


@pytest.mark.parametrize("part", ("head", "tail"))
def test_overlay_preserves_custom_y_and_replaces_only_x(part):
    data = _values("受電箱")
    custom = {"X": [{"len": 40, "angle": -90, "phase6_key": "yl1"}],
              "Y": [{"len": 123.0, "phase6_key": "custom_y", "metadata": {"slot": 1}}]}
    original = deepcopy(custom)
    actual = endcap_profiles_for_assembly(data, custom, "OVERLAY", part)
    assert actual["X"][0]["phase6_key"] == "endcap_w_flat"
    assert actual["Y"] == custom["Y"]
    assert custom == original
    actual["Y"][0]["metadata"]["slot"] = 99
    assert custom == original


@pytest.mark.parametrize("part", ("head", "tail"))
def test_switch_overlay_back_to_insert_restores_engine_x_not_stale_flat_x(part):
    data = _values("金庫型")
    y = [{"len": 77, "phase6_key": "operator_y"}]
    stored = {"X": [{"len": 500, "phase6_key": "endcap_w_flat"}], "Y": y}
    result = endcap_profiles_for_assembly(data, stored, "INSERT", part)
    defaults = manufacturing_api.build_endcap_xy_fold_profiles(
        {**data, "assembly_type": "INSERT"}, part_key=part,
    )
    assert result["X"] == defaults["X"]
    assert result["Y"] == y


def test_custom_nonflat_x_and_y_survive_unchanged():
    source = _values("金庫型")
    rows = {"X": [{"len": 111, "angle": 90, "phase6_key": "custom_x"}],
            "Y": [{"len": 222, "phase6_key": "custom_y"}]}
    result = endcap_profiles_for_assembly(source, rows, "INSERT_OVERLAY", "head")
    assert result == rows
    assert result is not rows
    assert result["X"] is not rows["X"]


def test_missing_y_is_supplied_by_existing_engine_family_builder():
    values = _values("受電箱")
    stored = {"X": [{"len": 111, "phase6_key": "custom_x"}]}
    result = endcap_profiles_for_assembly(values, stored, "INSERT", "tail")
    defaults = manufacturing_api.build_endcap_xy_fold_profiles(
        {**values, "assembly_type": "INSERT"}, part_key="tail",
    )
    assert result["X"] == stored["X"]
    assert result["Y"] == defaults["Y"]


def test_gui_forwards_assembly_profiles_without_manufacturing_topology(monkeypatch):
    calls = []
    sentinel = object()
    def engine(values, stored, assembly_type, key):
        calls.append((values, stored, assembly_type, key))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "endcap_profiles_for_assembly", engine)
    values = _values("受電箱")
    stored = {"X": []}
    assert adapter._endcap_profiles_for_assembly(values, stored, "OVERLAY", "head") is sentinel
    assert calls == [(values, stored, "OVERLAY", "head")]
    source = inspect.getsource(adapter._endcap_profiles_for_assembly)
    assert "manufacturing_api.endcap_profiles_for_assembly(" in source
    for forbidden in ("build_endcap_xy_profiles(", "CornerTypeId.",
                      "endcap_w_flat", "deepcopy(", "assembly_intent_value("):
        assert forbidden not in source
