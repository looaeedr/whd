"""#2517: actual AE runtime manufacturing Settings commits belong to public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
from ae_engine.sheetmetal_geometry import ReliefConfig, Vec2
from ae_engine.sheetmetal_features import VaultEndCapFeaturePolicy
from phase6_settings_center import apply_settings_to_ae


def _runtime():
    return SimpleNamespace(
        W=800.0, H=1600.0, D=350.0, T=2.0, FW=25.0, DRAW_STOCK=False,
        zl1_def=15.0, yl1_def=15.0, hang_hole_r=3.2, sq_width=4.0,
        base_plate_shrink_def=55.0, RELIEF_CONFIG=ReliefConfig(),
        VAULT_ENDCAP_FEATURE_POLICY=VaultEndCapFeaturePolicy(
            hanging_hole_radius=3.2, hanging_hole_y_from_top_bend=6.0,
            square_hole_origin=Vec2(3.0, 18.0),
            square_hole_size=Vec2(4.0, 4.0),
            tail_bottom_hole_radius=2.5, tail_bottom_hole_y=5.0,
        ),
    )


def test_public_engine_runtime_commit_matches_real_gui_and_restores_same_policy():
    raw = {
        "w": "800.625", "t": "2.125", "fw": "29.375",
        "zl1": "-15.25", "draw_stock": "true",
        "hang_hole_r": "5.125", "sq_width": "7.375",
        "relief_bottom_y_factor": "0.875",
        "base_plate_shrink_top": "53.25",
        "base_plate_shrink_bottom": "53.25",
        "base_plate_shrink_left": "53.25",
        "base_plate_shrink_right": "53.25",
    }
    raw_before = deepcopy(raw)
    headless, gui = _runtime(), _runtime()
    api.apply_operator_runtime_settings_to_ae(headless, raw)
    apply_settings_to_ae(gui, raw)
    assert vars(headless) == vars(gui)
    assert (gui.W, gui.T, gui.FW, gui.zl1_def) == (800.625, 2.125, 29.375, -15.25)
    assert gui.DRAW_STOCK is True
    assert gui.RELIEF_CONFIG.bottom_y_factor == 0.875
    assert gui.VAULT_ENDCAP_FEATURE_POLICY.hanging_hole_radius == 5.125
    assert gui.VAULT_ENDCAP_FEATURE_POLICY.square_hole_size.x == 7.375
    assert gui.base_plate_shrink_def == 53.25
    assert raw == raw_before
    reloaded = json.loads(json.dumps(raw))
    c = _runtime()
    api.apply_operator_runtime_settings_to_ae(c, reloaded)
    assert vars(c) == vars(headless)
    assert ae_engine.apply_operator_runtime_settings_to_ae is (
        api.apply_operator_runtime_settings_to_ae
    )


@pytest.mark.parametrize("invalid", [
    {"w": 0}, {"t": True}, {"fw": float("inf")}, {"zl1": "nan"},
    {"yl1": True}, {"hang_hole_r": "broken"},
    {"relief_bottom_y_factor": "-Infinity"}, {"draw_stock": "maybe"},
])
def test_invalid_late_runtime_source_rejects_before_any_partial_write(invalid):
    raw = {"zl1": "17.375", "hang_hole_r": "5.5", **invalid}
    headless = _runtime()
    before = deepcopy(vars(headless))
    with pytest.raises(ValueError):
        api.apply_operator_runtime_settings_to_ae(headless, raw)
    assert vars(headless) == before
    gui = _runtime()
    with pytest.raises(ValueError):
        apply_settings_to_ae(gui, raw)
    assert vars(gui) == before


def test_partial_key_filter_preserves_runtime_and_legacy_policy_without_guessing():
    raw = {
        "w": "801.125", "yl1": "bad", "ui_text_size": "大",
        "base_plate_shrink_top": "55",
    }
    engine, gui = _runtime(), _runtime()
    api.apply_operator_runtime_settings_to_ae(engine, raw, keys=("w", "ui_text_size"))
    apply_settings_to_ae(gui, raw, keys=("w", "ui_text_size"))
    assert vars(engine) == vars(gui)
    assert engine.W == 801.125
    assert engine.yl1_def == 15.0
    assert engine.base_plate_shrink_def == 55.0
    with pytest.raises(ValueError):
        api.apply_operator_runtime_settings_to_ae(_runtime(), raw, keys=("w", "yl1"))



@pytest.mark.parametrize("edge_value", ["49.375", "bad"])
def test_filtered_runtime_does_not_apply_unselected_hole_or_base_plate_policy(edge_value):
    """Unselected legacy physical settings cannot bypass the Engine key scope."""
    raw = {
        "w": "801.125", "hang_hole_r": "6.75",
        "base_plate_shrink_top": edge_value,
        "base_plate_shrink_bottom": edge_value,
        "base_plate_shrink_left": edge_value,
        "base_plate_shrink_right": edge_value,
    }
    for commit in (api.apply_operator_runtime_settings_to_ae, apply_settings_to_ae):
        runtime = _runtime()
        policy = runtime.VAULT_ENDCAP_FEATURE_POLICY
        commit(runtime, json.loads(json.dumps(raw)), keys=("w",))
        assert runtime.W == 801.125
        assert runtime.base_plate_shrink_def == 55.0
        assert runtime.hang_hole_r == 3.2
        assert runtime.VAULT_ENDCAP_FEATURE_POLICY is policy


def test_selected_hole_runtime_policy_ignores_unselected_invalid_shrink():
    raw = {
        "hang_hole_r": "6.75",
        "base_plate_shrink_top": "malformed",
        "base_plate_shrink_bottom": "malformed",
        "base_plate_shrink_left": "malformed",
        "base_plate_shrink_right": "malformed",
    }
    for commit in (api.apply_operator_runtime_settings_to_ae, apply_settings_to_ae):
        runtime = _runtime()
        commit(runtime, raw, keys=("hang_hole_r",))
        assert runtime.hang_hole_r == 6.75
        assert runtime.VAULT_ENDCAP_FEATURE_POLICY.hanging_hole_radius == 6.75
        assert runtime.base_plate_shrink_def == 55.0


def test_explicitly_selected_invalid_shrink_rejects_before_runtime_mutation():
    raw = {"w": "801.125", "base_plate_shrink_top": "malformed"}
    for commit in (api.apply_operator_runtime_settings_to_ae, apply_settings_to_ae):
        runtime = _runtime()
        original = deepcopy(vars(runtime))
        with pytest.raises(ValueError):
            commit(runtime, raw, keys=("w", "base_plate_shrink_top"))
        assert vars(runtime) == original


def test_only_engine_knows_runtime_attributes_and_gui_is_thin_adapter():
    source = inspect.getsource(apply_settings_to_ae)
    assert "manufacturing_api.apply_operator_runtime_settings_to_ae(" in source
    assert "setattr(" not in source
    assert "relief_changes" not in source
    assert "spec.runtime_attr" not in source
    assert "spec.relief_attr" not in source
    assert owner.apply_operator_runtime_settings_to_ae is api.apply_operator_runtime_settings_to_ae
    body = inspect.getsource(owner)
    assert "from phase6_" not in body and "from gui_modules" not in body
    assert "import tkinter" not in body
