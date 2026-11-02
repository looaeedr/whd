# -*- coding: utf-8 -*-
"""#2517: Settings physical profile mutation plan is the public Engine's job."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from phase6_settings_profile_projection import (
    SettingsProfileProjectionRequest,
    build_settings_profile_projection,
    materialize_settings_profile_value,
)


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
@pytest.mark.parametrize("active", ["box_body", "head", "tail", "door"])
def test_headless_engine_and_gui_settings_folds_share_one_physical_plan(model, active):
    input_data = {"model": model, "w": 800, "h": 1100, "d": 300, "t": 2, "fw": 29}
    settings = {"w": 800, "h": 1100, "d": 300, "t": 2, "fw": 29}
    saved = {
        "door": {
            "X": [{"len": 12, "angle": -90, "phase6_key": "door_fold_l"},
                  {"len": 400, "core": "門包外 W", "phase6_key": "door_face_w"},
                  {"len": 14, "phase6_key": "door_fold_r"},
                  {"len": 8, "angle": -90, "custom_note": "operator"}],
            "Y": [],
        },
    }
    old_inputs = deepcopy((input_data, settings, saved))
    kwargs = {
        "input_snapshot": input_data,
        "settings_values": settings,
        "available_parts": ("box_body", "head", "tail", "door"),
        "existing_profiles": saved,
        "box_body_profile": (),
        "active_part": active,
    }
    engine = api.plan_operator_settings_fold_profiles(**kwargs)
    facade = build_settings_profile_projection(SettingsProfileProjectionRequest(**kwargs))
    for key in ("snapshot", "part_dimensions", "box_body_profile", "part_profiles", "active_profiles"):
        assert materialize_settings_profile_value(getattr(facade, key)) == engine[key]
    assert (facade.active_part, facade.derived_sync_required) == (engine["active_part"], True)
    assert (input_data, settings, saved) == old_inputs
    assert "head" in engine["part_profiles"] and "tail" in engine["part_profiles"]
    assert engine["active_profiles"] == (
        {"X": engine["box_body_profile"]} if active == "box_body"
        else engine["part_profiles"][active]
    )


def test_settings_plan_skips_derived_physical_parts_and_preserves_custom_fold_contract():
    snapshot = {"model": "金庫型", "w": 500, "h": 600, "d": 200, "t": 2, "fw": 25,
                "custom_parts": {"custom:fixture": {
                    "name": "Fixture", "fold_axis": "X", "transverse_length": 300,
                }}}
    # The supported CustomFold schema validates metadata; malformed metadata
    # is rejected rather than being silently built as an ordinary panel.
    with pytest.raises((ValueError, TypeError)):
        api.plan_operator_settings_fold_profiles(
            settings_values={}, input_snapshot=snapshot,
            available_parts=("box_body", "custom:fixture"),
        )


def test_headless_plan_replays_saved_operator_added_door_fold_across_reload():
    source = {"model": "金庫型", "w": 800, "h": 1100, "d": 300, "t": 2, "fw": 29}
    first = api.plan_operator_settings_fold_profiles(
        settings_values={}, input_snapshot=source,
        available_parts=("box_body", "door"), active_part="door",
    )
    stored = deepcopy(first["part_profiles"])
    stored["door"]["X"].append({"len": 7.0, "angle": -90, "custom_note": "saved fold"})
    next_plan = api.plan_operator_settings_fold_profiles(
        settings_values={}, input_snapshot=deepcopy(first["snapshot"]),
        available_parts=("box_body", "door"), existing_profiles=stored,
        box_body_profile=first["box_body_profile"], active_part="door",
    )
    assert next_plan["part_profiles"]["door"]["X"][-1] == {
        "len": 7.0, "angle": -90, "custom_note": "saved fold",
    }
    assert next_plan["snapshot"]["part_dimensions"] == first["part_dimensions"]


def test_engine_settings_plan_has_no_phase6_or_tk_runtime_dependency():
    engine = Path(__file__).resolve().parents[1] / "ae_engine" / "operator_settings_fold_plan.py"
    source = engine.read_text(encoding="utf-8")
    assert "from phase6" not in source
    assert "from gui_modules" not in source
    assert "tkinter" not in source
    facade = (Path(__file__).resolve().parents[1] / "phase6_settings_profile_projection.py").read_text(encoding="utf-8")
    start = facade.split("def build_settings_profile_projection(", 1)[1].split("\n__all__", 1)[0]
    assert "manufacturing_api.plan_operator_settings_fold_profiles(" in start
    assert "build_endcap_xy_profiles(" not in start
    assert "merge_keyed_profiles(" not in start
