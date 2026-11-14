"""#2517: Fold Designer Head/Tail raw FW source is qualified by Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_endcap_settings_transactions as owner
from ae_engine.endcap_factory_fold import (
    commit_endcap_fw, resolve_endcap_fw,
)


def snapshot(model="金庫型", fw=25.0):
    return {"model": model, "fw": fw}


def follows(box_fw=25.0):
    return {
        "mode": "FOLLOW_BODY",
        "head": {"follow_box": True, "value": box_fw},
        "tail": {"follow_box": True, "value": box_fw},
    }


def test_head_tail_edit_and_split_follow_original_engine_four_mode_policy():
    state = follows()
    prior = deepcopy(state)
    head_ref, tail_ref = state["head"], state["tail"]
    returned = api.commit_operator_endcap_fw_profile_save(
        snapshot(), state, "head", {"len": "32.125"},
    )
    expected = deepcopy(prior)
    # Fold editor displays integer whole-mm manual fold values.
    commit_endcap_fw(expected, "head", 32.0, box_fw=25.0)
    assert returned is state
    assert state == expected
    assert state["head"] is head_ref and state["tail"] is tail_ref
    assert resolve_endcap_fw(snapshot(), "head", state=state) == 32.0

    api.commit_operator_endcap_fw_profile_save(
        snapshot(), state, "tail", {"len": "31"},
    )
    commit_endcap_fw(expected, "tail", 31.0, box_fw=25.0)
    assert state == expected
    assert state["mode"] == "INDEPENDENT"
    assert state["head"]["value"] == 32.0
    assert state["tail"]["value"] == 31.0
    assert ae_engine.commit_operator_endcap_fw_profile_save is (
        api.commit_operator_endcap_fw_profile_save
    )


def test_receiving_material_fw_uses_existing_engine_adjacent_bend_readback():
    # Receiving Y profile stores a material length and an outside addendum.
    state = follows(29.0)
    raw = {"len": "24", "ui_len_add": "8"}
    before = deepcopy(raw)
    api.commit_operator_endcap_fw_profile_save(
        snapshot("受電箱", 29.0), state, "head", raw,
    )
    assert state["mode"] == "FOLLOW_HEAD"
    assert state["head"]["value"] == 32.0
    assert state["tail"]["value"] == 32.0
    assert raw == before
    reloaded = json.loads(json.dumps(state, ensure_ascii=False))
    assert api.resolve_endcap_fw(snapshot("受電箱", 29.), "tail", state=reloaded) == 32.


def test_equal_edit_keeps_original_leader_and_does_not_steal_follow_state():
    state = follows(25.0)
    old = deepcopy(state)
    api.commit_operator_endcap_fw_profile_save(
        snapshot(), state, "head", {"len": "25"},
    )
    assert state == old
    split = {
        "mode": "INDEPENDENT",
        "head": {"follow_box": False, "value": 30.},
        "tail": {"follow_box": False, "value": 28.},
    }
    before = deepcopy(split)
    api.commit_operator_endcap_fw_profile_save(
        snapshot(), split, "head", {"len": 30.0},
    )
    assert split == before


def test_missing_legacy_fw_segment_uses_only_authoritative_box_fw():
    original = {}
    result = api.commit_operator_endcap_fw_profile_save(
        snapshot(fw=28.375), original, "head", None,
    )
    assert result is original
    assert result == {"head": {"follow_box": True, "value": 28.375}}


@pytest.mark.parametrize("bad", [
    True, False, "nan", "inf", None, "broken", float("nan"), float("inf"),
    {}, [],
])
def test_bad_segment_material_length_does_not_mutate_head_tail_state(bad):
    state = follows(29.)
    before = deepcopy(state)
    with pytest.raises((TypeError, ValueError, OverflowError)):
        api.commit_operator_endcap_fw_profile_save(
            snapshot("受電箱", 29.), state, "head",
            {"len": bad, "ui_len_add": 3.0},
        )
    assert state == before


@pytest.mark.parametrize("bad", [True, False, "nan", "inf", "wrong", None])
def test_bad_explicit_material_addendum_does_not_mutate_source(bad):
    state = follows(29.)
    before = deepcopy(state)
    with pytest.raises((TypeError, ValueError, OverflowError)):
        api.commit_operator_endcap_fw_profile_save(
            snapshot("受電箱", 29.), state, "head",
            {"len": 24, "ui_len_add": bad},
        )
    assert state == before


@pytest.mark.parametrize("bad", [True, "nan", "inf", -1, 0, None, "invalid"])
def test_invalid_original_box_fw_never_falls_back_to_factory_25mm(bad):
    state = follows()
    old = deepcopy(state)
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        api.commit_operator_endcap_fw_profile_save(
            snapshot(fw=bad), state, "head", {"len": 30.},
        )
    assert state == old


@pytest.mark.parametrize("invalid_row", [
    {"follow_box": "unknown", "value": 29.0},
    {"follow_box": False, "value": float("nan")},
    True, [],
])
def test_bad_opposite_saved_row_rejected_before_mutating_active_head(invalid_row):
    state = follows(29.)
    state["tail"] = invalid_row
    old = deepcopy(state)
    with pytest.raises(ValueError):
        api.commit_operator_endcap_fw_profile_save(
            snapshot("受電箱", 29.), state, "head", {"len": 24, "ui_len_add": 5},
        )
    assert state == old


def test_gui_head_tail_save_uses_engine_raw_segment_without_prior_mutation():
    from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner
    code = inspect.getsource(Phase6PartSessionOwner.save_current_part)
    assert "manufacturing_api.commit_operator_endcap_fw_profile_save(" in code
    assert "key, y.get('fw')" in code
    assert "_phase6_endcap_fw_state.setdefault(" not in code
    assert "abs(float(edited_fw) - float(effective_before))" not in code
    assert "bridge._num(app._phase6_input_snapshot.get('fw', 25), 25)" not in code
    # Actual Head/Tail profile persistence follows successful W/D and FW gates.
    start = code.index("if key in bridge.ENDCAP_FW_PARTS:")
    end = code.index("else:\n", start)
    portion = code[start:]
    assert portion.index("commit_operator_endcap_fw_profile_save(") < portion.index(
        "app.designer_workspace.stash_profiles(key, profiles)"
    )
    assert "from gui_modules" not in inspect.getsource(owner)
    assert "from phase6_" not in inspect.getsource(owner)
