"""#2517 linked Head/Tail live W/H/D source belongs to the Engine Family."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.linked_endcap_fold import (
    build_linked_endcap_xy_fold_profiles as original_linked,
)
import fold_designer_bridge


def _source(model="受電箱"):
    return {
        "model": model, "w": 800.0, "h": 1000.0, "d": 250.0,
        "t": 2.0, "fw": 25.0, "zl1": 15.0, "zl2": 16.0,
        "zr1": 15.0, "zr2": 16.0, "ytop1": 16.0, "ybottom1": 15.0,
    }


def _plan(model="受電箱", *, live=None, settings=None):
    source = _source(model)
    seeded = dict(source)
    seeded.update(settings or {})
    profile = manufacturing_api.build_box_body_fold_profile(seeded)
    return manufacturing_api.plan_operator_linked_endcap_live_profiles(
        source, settings or {},
        {"w": 820.0, "h": 1000.0, "d": 255.0} if live is None else live,
        profile,
        corner_state={}, corner_pair_same={}, assembly_type="INSERT_OVERLAY",
        endcap_fw_state=None,
    )


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_aliases_use_same_live_box_body_dimensions(model):
    plan = _plan(model)
    assert plan.snapshot["w"] == 820.0
    assert plan.snapshot["h"] == 1000.0
    assert plan.snapshot["d"] == 255.0
    assert plan.snapshot["assembly_type"] == "INSERT_OVERLAY"
    assert plan.profiles == original_linked(
        plan.snapshot, manufacturing_api.build_box_body_fold_profile(_source(model)),
    )
    assert ae_engine.plan_operator_linked_endcap_live_profiles is (
        manufacturing_api.plan_operator_linked_endcap_live_profiles
    )
    assert ae_engine.OperatorLinkedEndcapLivePlan is manufacturing_api.OperatorLinkedEndcapLivePlan


def test_vault_does_not_borrow_unrelated_live_box_dimensions():
    plan = _plan("金庫型", live={"w": 860, "h": 1200, "d": 270})
    assert plan.snapshot["w"] == 800
    assert plan.snapshot["h"] == 1000
    assert plan.snapshot["d"] == 250
    assert plan.profiles == original_linked(
        plan.snapshot, manufacturing_api.build_box_body_fold_profile(_source("金庫型")),
    )


def test_receiving_partial_live_fields_are_overlaid_only_when_present():
    plan = _plan("受電箱", live={"w": 815.25})
    assert plan.snapshot["w"] == 815.25
    assert plan.snapshot["h"] == 1000
    assert plan.snapshot["d"] == 250


@pytest.mark.parametrize("invalid", [True, False, 0, -10, float("nan"), float("inf"), "garbage"])
@pytest.mark.parametrize("axis", ["w", "h", "d"])
def test_invalid_receiving_live_physical_value_fails_without_mutating_any_source(axis, invalid):
    source = _source()
    settings = {"fw": 28.0}
    box = {"w": 820.0, "h": 1000.0, "d": 255.0}
    box[axis] = invalid
    original = deepcopy(source), deepcopy(settings), deepcopy(box)
    profile = manufacturing_api.build_box_body_fold_profile(_source())
    before_profile = deepcopy(profile)
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.plan_operator_linked_endcap_live_profiles(
            source, settings, box, profile,
            corner_state={}, corner_pair_same={}, assembly_type="INSERT_OVERLAY",
        )
    assert (source, settings, box) == original
    assert profile == before_profile


def test_missing_live_receiving_w_h_d_does_not_fabricate_defaults():
    plan = _plan("受電箱", live={})
    assert plan.snapshot["w"] == _source()["w"]
    assert plan.snapshot["h"] == _source()["h"]
    assert plan.snapshot["d"] == _source()["d"]


def test_real_saved_snapshot_reopen_preserves_linked_part_profiles():
    source = _source("受電箱")
    source["assembly_type"] = "OVERLAY"
    profile = manufacturing_api.build_box_body_fold_profile(source)
    params = dict(
        corner_state={},
        corner_pair_same={},
        assembly_type=None,
        endcap_fw_state=None,
    )
    plan = manufacturing_api.plan_operator_linked_endcap_live_profiles(
        source, {"fw": 27.0},
        {"w": 835.0, "h": 1020.0, "d": 265.0},
        profile, **params,
    )
    persisted = json.loads(json.dumps({
        "source": source, "box_body_profile": profile,
        "settings": {"fw": 27.0},
        "box_whd": {"w": 835.0, "h": 1020.0, "d": 265.0},
        "linked": plan.profiles,
    }))
    reloaded = manufacturing_api.plan_operator_linked_endcap_live_profiles(
        persisted["source"], persisted["settings"], persisted["box_whd"],
        persisted["box_body_profile"], **params,
    )
    assert reloaded.profiles == plan.profiles
    assert reloaded.snapshot == plan.snapshot
    assert persisted["linked"] == reloaded.profiles


def test_gui_rebuild_linked_endcaps_only_publishes_engine_plan(monkeypatch):
    original = _source("ReCeIvInG")
    box_profile = manufacturing_api.build_box_body_fold_profile(original)
    host = SimpleNamespace(
        state=SimpleNamespace(profiles_vault={"箱身": deepcopy(box_profile)}),
        _phase6_input_snapshot=deepcopy(original),
        _settings_values={"fw": 26.0},
        _phase6_box_whd={"w": 825.0, "h": 1010.0, "d": 265.0},
        _phase6_corner_state={},
        _phase6_corner_pair_same={},
        _phase6_assembly_type="INSERT_OVERLAY",
        designer_workspace=SimpleNamespace(
            available_parts=("head", "tail"),
            active_part=None,
        ),
    )
    saved = {}
    host.designer_workspace.stash_profiles = lambda key, rows: saved.__setitem__(key, deepcopy(rows))
    calls = []
    original_api = manufacturing_api.plan_operator_linked_endcap_live_profiles

    def spy(*args, **kwargs):
        calls.append(True)
        return original_api(*args, **kwargs)

    monkeypatch.setattr(manufacturing_api, "plan_operator_linked_endcap_live_profiles", spy)
    result = fold_designer_bridge._phase6_rebuild_linked_endcaps(host)
    assert calls == [True]
    assert saved == result
    assert result["head"]["Y"] and result["tail"]["Y"]
    assert host._phase6_input_snapshot == original
    assert host.state.profiles_vault["箱身"] == box_profile


def test_gui_no_longer_dispatches_manufacturing_family_by_label():
    source = inspect.getsource(fold_designer_bridge._phase6_rebuild_linked_endcaps)
    assert "manufacturing_api.plan_operator_linked_endcap_live_profiles(" in source
    assert 'in {"受電箱", "RECEIVING"}' not in source
    assert 'snapshot.update(' not in source
    assert 'build_linked_endcap_xy_profiles(snapshot' not in source
