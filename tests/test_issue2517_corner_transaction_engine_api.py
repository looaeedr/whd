"""#2517 CornerType edits belong to Engine, not Phase6 state semantics."""
from __future__ import annotations
from copy import deepcopy
import inspect
import json
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import corner_state_transactions as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CrossCornerMode, CornerDirection
import phase6_settings_transitions as phase6


def test_engine_public_ownership_and_phase6_adapter():
    for name in ("ensure_corner_part", "corner_selection", "corner_targets",
                 "commit_corner_pair", "commit_corner_type", "commit_corner_mode",
                 "commit_corner_parameters", "apply_corner_preset"):
        assert getattr(api, name) is getattr(owner, name)
        assert f"manufacturing_api.{name}(" in inspect.getsource(getattr(phase6, name))
    assert phase6.CornerStateTransition is owner.CornerStateTransition
    assert "from phase6_" not in inspect.getsource(owner)


def test_engine_manual_pair_edit_split_rejoin_and_save_reload():
    raw = {"head": {"bottom_right": {"type_id": "CROSS", "rotation_quadrants": 0}}}
    saved = deepcopy(raw)
    state = api.ensure_corner_part(raw, None, "head")
    assert raw == saved
    assert state.corner_pair_same["head"] == {"top": True, "bottom": True}
    assert len(state.corner_state["head"]) == 4
    state = api.commit_corner_type(state.corner_state, state.corner_pair_same, "head", "top", CornerTypeId.OVERLAY)
    assert all(state.corner_state["head"][k]["type_id"] == "OVERLAY" for k in ("top_left", "top_right"))
    state = api.commit_corner_pair(state.corner_state, state.corner_pair_same, "head", "top", False)
    state = api.commit_corner_type(state.corner_state, state.corner_pair_same, "head", "top_right", CornerTypeId.CROSS)
    state = api.commit_corner_mode(state.corner_state, state.corner_pair_same, "head", "top_right", CrossCornerMode.EXTRA_CUT)
    state = api.commit_corner_parameters(state.corner_state, state.corner_pair_same, "head", "top_right", amount_t=1.5, direction=CornerDirection.WIDTH)
    assert state.corner_state["head"]["top_left"]["type_id"] == "OVERLAY"
    assert state.corner_state["head"]["top_right"]["type_id"] == "CROSS"
    assert state.corner_state["head"]["top_right"]["cross_mode"] == "extra_cut"
    assert state.corner_state["head"]["top_right"]["amount_t"] == 1.5
    reload = json.loads(json.dumps({"corner_state": state.corner_state, "corner_pair_same": state.corner_pair_same}))
    state = api.commit_corner_pair(reload["corner_state"], reload["corner_pair_same"], "head", "top", True)
    assert state.corner_state["head"]["top_left"] == state.corner_state["head"]["top_right"]
    assert state.corner_pair_same["head"]["top"] is True


def test_fixed_family_preset_is_engine_owned_and_gui_matches():
    raw = {"door": {"top_left": {"type_id": "CROSS", "rotation_quadrants": 0}}}
    fixed = {"head": {"top_left": {"type_id": "OVERLAY", "amount_t": 1.0}}}
    pairs = {"head": {"top": False, "bottom": False}}
    result = api.apply_corner_preset(raw, pairs, fixed)
    assert raw["door"]["top_left"]["type_id"] == "CROSS"
    assert result.corner_pair_same["head"] == {"top": True, "bottom": True}
    assert result.corner_state["head"]["top_left"]["type_id"] == "OVERLAY"
    assert result == phase6.apply_corner_preset(raw, pairs, fixed)
    assert json.loads(json.dumps(result.corner_state)) == result.corner_state


def test_invalid_corner_edits_fail_closed_and_cannot_mutate_inputs():
    raw = {"door": {"top_left": {"type_id": "CROSS", "rotation_quadrants": 0}}}
    pairs = {"door": {"top": True, "bottom": True}}
    original = deepcopy(raw)
    for fn, args in (
        (api.commit_corner_pair, ("door", "unknown", True)),
        (api.commit_corner_type, ("door", "top_left", "BAD_TYPE")),
        (api.commit_corner_mode, ("door", "top_left", "BAD_MODE")),
    ):
        with pytest.raises(ValueError):
            fn(raw, pairs, *args)
        assert raw == original
        assert pairs["door"]["top"] is True


def test_compatibility_commits_match_headless_api_after_json_reload():
    raw = {"tail": {"top_left": {"type_id": "INSERT", "amount_t": 1.0}}}
    pairs = {"tail": {"top": True, "bottom": True}}
    for name, args, kwargs in (
        ("commit_corner_type", ("tail", "top", CornerTypeId.INSERT_OVERLAY), {}),
        ("commit_corner_parameters", ("tail", "top"), {"amount_t": 1.75, "secondary_retain_t": 0.5, "secondary_depth_t": 2.0}),
    ):
        assert getattr(phase6, name)(raw, pairs, *args, **kwargs) == getattr(api, name)(raw, pairs, *args, **kwargs)
