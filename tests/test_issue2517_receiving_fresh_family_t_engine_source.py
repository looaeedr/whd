"""#2517: Receiving fresh Family raw physical T must be Engine-qualified."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy, receiving
from gui_modules.application import cabinet_controller as gui
from phase6_project_file import _decode, _encode


def test_real_public_family_entry_is_the_original_engine_owner():
    assert api.operator_apply_fresh_family_defaults is policy.apply_fresh_family_defaults
    assert ae_engine.operator_apply_fresh_family_defaults is policy.apply_fresh_family_defaults
    source = inspect.getsource(receiving.apply_family_defaults)
    assert "normalize_operator_source_dimension(" in source
    assert "thickness = float(" not in source
    assert "except (TypeError, ValueError):" not in source


@pytest.mark.parametrize("raw", [
    True, False, None, "", "invalid", "NaN", "inf",
    float("nan"), float("inf"), 0, -1, "-0.125", [], {},
])
def test_explicit_invalid_thickness_never_builds_fresh_physical_inner_doors(
    monkeypatch, raw,
):
    source = {"t": raw, "w": 620, "h": 900, "d": 240}
    before = deepcopy(source)
    calls = []
    monkeypatch.setattr(
        receiving, "default_inner_doors",
        lambda **kwargs: calls.append(kwargs),
    )
    with pytest.raises((TypeError, ValueError), match="包外尺寸"):
        api.operator_apply_fresh_family_defaults(source, "受電箱")
    assert calls == []
    assert source == before


@pytest.mark.parametrize("raw,expected", [
    (2, 2.0), ("2", 2.0), (2.125, 2.125),
    ("2.125", 2.125), (3.5, 3.5),
])
def test_valid_raw_fractional_t_reaches_original_inner_door_factory_without_rounding(
    monkeypatch, raw, expected,
):
    source = {"t": raw, "door_handle_edges": {"outer": "left"}}
    before = deepcopy(source)
    original = receiving.default_inner_doors
    arguments = []

    def observe(**kwargs):
        arguments.append(deepcopy(kwargs))
        return original(**kwargs)

    monkeypatch.setattr(receiving, "default_inner_doors", observe)
    result = api.operator_apply_fresh_family_defaults(source, "受電箱")
    assert source == before
    assert result["model"] == "受電箱"
    assert result["t"] == raw
    assert len(arguments) == 1
    assert arguments[0]["thickness"] == expected
    assert arguments[0]["depth"] == 350.0
    assert arguments[0]["frame_width"] == 29.0
    assert result["inner_doors"]
    assert result["receiving_layout"]["sets"][0]["bays"]
    assert _decode(_encode(result))["t"] == raw


def test_missing_legacy_t_uses_existing_two_mm_fresh_default_only_when_absent(
    monkeypatch,
):
    source = {"door_handle_edges": {}}
    original = receiving.default_inner_doors
    actual_t = []

    def observe(**kwargs):
        actual_t.append(kwargs["thickness"])
        return original(**kwargs)

    monkeypatch.setattr(receiving, "default_inner_doors", observe)
    result = api.operator_apply_fresh_family_defaults(source, "受電箱")
    assert "t" not in source and "t" not in result
    assert actual_t == [2.0]
    assert result["inner_doors"]


def _model_transition(raw):
    source = {
        "model": "金庫型", "w": 800, "h": 1600, "d": 350,
        "t": 2, "fw": 25,
        "factory_defaults": {
            "w": 800, "h": 1600, "d": 350, "t": raw, "fw": 25,
        },
    }
    before = deepcopy(source)
    kwargs = dict(
        new_editable=False, old_editable=False,
        input_snapshot=source,
        settings_values={"w": 800, "h": 1600, "d": 350, "t": 2, "fw": 25},
        corner_state={}, corner_pair_same={},
        endcap_bottom_wrap_state={}, assembly_type="INSERT_OVERLAY",
        available_parts=("box_body", "head", "tail"),
    )
    with pytest.raises((ValueError, TypeError), match="包外尺寸"):
        api.plan_cabinet_family_model_transition("受電箱", "金庫型", **kwargs)
    assert source == before


@pytest.mark.parametrize("raw", [True, None, 0, -2, "NaN", "invalid", float("inf")])
def test_fresh_engine_family_transition_rejects_bad_preset_t_before_any_set_bay(raw):
    _model_transition(raw)


@pytest.mark.parametrize("raw", [False, None, "NaN", -1, "invalid"])
def test_main_gui_receiving_family_switch_rejects_bad_factory_t_before_widgets(raw):
    calls = []
    host = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: "受電箱"),
        _current_cabinet_type_name=lambda: "受電箱",
        _active_cabinet_type="金庫型",
        _fold_designer_baseline_commit_guard=False,
        _cabinet_family_defaults={"金庫型": {"settings": {"t": raw}}},
        _apply_fold_designer_live_settings=lambda *a, **kw: calls.append("settings"),
        _set_box_assembly_type=lambda *a, **kw: calls.append("assembly"),
        set_door_layout_columns=lambda *a, **kw: calls.append("layout"),
    )
    with pytest.raises((ValueError, TypeError), match="包外尺寸"):
        gui._apply_cabinet_family_for_current_model(host)
    assert calls == []
    assert host._active_cabinet_type == "金庫型"


def test_json_saved_fractional_family_source_preserves_physical_t_after_reload():
    source = json.loads(json.dumps({"model": "金庫型", "t": "2.125"}))
    fresh = api.operator_apply_fresh_family_defaults(source, "受電箱")
    restored = _decode(_encode(fresh))
    assert restored["t"] == "2.125"
    assert restored["inner_doors"]
    assert api.operator_apply_fresh_family_defaults(source, "受電箱")["inner_doors"] == fresh["inner_doors"]
