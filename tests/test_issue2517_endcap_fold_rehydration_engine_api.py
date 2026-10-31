"""#2517: Engine owns saved EndCap Y Fold rehydration and supported axes."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import endcap_editor_fold_tabs, normalize_endcap_profile_order
from ae_engine import manufacturing_api
from ae_engine import endcap_factory_fold as owner
import phase6_fold_profiles as legacy


SNAPSHOT = {
    "w": 500, "d": 200, "t": 2, "fw": 25,
    "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15,
}


def test_public_api_legacy_tail_order_rehydration_is_engine_owned_and_immutable():
    assert normalize_endcap_profile_order is manufacturing_api.normalize_endcap_profile_order
    assert normalize_endcap_profile_order is owner.normalize_endcap_profile_order
    canonical = manufacturing_api.build_endcap_xy_fold_profiles(SNAPSHOT, part_key="tail")
    old_y = deepcopy(list(reversed(canonical["Y"])))
    # Legacy Head-oriented serialized Y order can retain an operator-edit length
    # that must not be replaced by fresh factory defaults.
    next(seg for seg in old_y if seg["phase6_key"] == "ytop1")["len"] = 31
    old_y[0]["operator_note"] = "persisted"
    saved = {"X": deepcopy(canonical["X"]), "Y": old_y}
    original = deepcopy(saved)

    result = normalize_endcap_profile_order(saved, SNAPSHOT, "tail")
    assert saved == original
    assert [row["phase6_key"] for row in result["Y"]] == [
        row["phase6_key"] for row in canonical["Y"]
    ]
    assert next(row for row in result["Y"] if row["phase6_key"] == "ytop1")["len"] == 31
    assert next(row for row in result["Y"] if row["phase6_key"] == "ytop1")["operator_note"] == "persisted"
    for actual, default in zip(result["Y"], canonical["Y"]):
        for attr in ("angle", "core", "ui_len_add"):
            assert actual.get(attr) == default.get(attr)
    assert legacy._phase6_normalize_endcap_profile_order(saved, SNAPSHOT, "tail") == result


@pytest.mark.parametrize("part", ("head", "other", "tail"))
def test_noncanonical_or_nontail_fold_is_not_reconstructed(part):
    canonical = manufacturing_api.build_endcap_xy_fold_profiles(SNAPSHOT, part_key="tail")
    source = {"X": canonical["X"], "Y": list(reversed(canonical["Y"]))}
    if part == "tail":
        source["Y"].append({"phase6_key": "custom", "len": 7, "angle": 30})
    copied = deepcopy(source)
    result = normalize_endcap_profile_order(source, SNAPSHOT, part)
    assert result == copied
    assert source == copied
    assert result is not source and result["Y"] is not source["Y"]


@pytest.mark.parametrize("part", ("head", "tail"))
def test_overlay_fold_tabs_from_engine_not_gui(part):
    overlay = {**SNAPSHOT, "assembly_type": "OVERLAY"}
    assert endcap_editor_fold_tabs is manufacturing_api.endcap_editor_fold_tabs
    assert endcap_editor_fold_tabs(overlay, part) == ["Y"]
    assert legacy._phase6_fold_tabs_for_part(overlay, part) == ["Y"]
    assert endcap_editor_fold_tabs(SNAPSHOT, part) is None
    assert endcap_editor_fold_tabs(overlay, "box_body") is None


def test_phase6_only_forwards_public_engine_fold_contract():
    source = inspect.getsource(legacy._phase6_normalize_endcap_profile_order)
    tabs = inspect.getsource(legacy._phase6_fold_tabs_for_part)
    assert "manufacturing_api.normalize_endcap_profile_order(" in source
    assert "manufacturing_api.endcap_editor_fold_tabs(" in tabs
    assert "by_key" not in source and "reordered" not in source
    assert "CornerTypeId.OVERLAY" not in tabs
    engine = inspect.getsource(owner)
    assert "from phase6_" not in engine
