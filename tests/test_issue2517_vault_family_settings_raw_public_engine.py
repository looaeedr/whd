"""#2517 saved Vault-family Settings must be Engine validated before GUI restore."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as gui


class Var:
    def __init__(self, value):
        self.value = value
        self.set_calls = []

    def get(self):
        return self.value

    def set(self, value):
        self.set_calls.append(value)
        self.value = value


class Settings:
    def __init__(self):
        self.values = {
            "w": 800.0, "h": 1600.0, "d": 350.0,
            "t": 2.0, "fw": 25.0, "draw_stock": True,
            "zl1": 15.0, "door_fold_l": 19.0,
            "base_plate_shrink_left": 55.0, "ui_text_size": "small",
        }

    def snapshot(self):
        return SimpleNamespace(as_dict=lambda: dict(self.values))


def host():
    side_effects = []
    settings = Settings()
    multi = Var(False)
    workspace = SimpleNamespace(
        set_box_body_structure_state=lambda value: side_effects.append(("structure", value)),
        set_box_body_profile=lambda value: side_effects.append(("profile", value)),
    )
    app = SimpleNamespace(
        settings_service=settings,
        _apply_fold_designer_live_settings=lambda values, **kwargs:
            side_effects.append(("settings", dict(values), kwargs)),
        _apply_manual_corner_snapshot=lambda state, pairs:
            side_effects.append(("corners", state, pairs)),
        _current_cabinet_type_name=lambda: "金庫型",
        multi_door_enabled_var=multi,
        workspace_controller=workspace,
    )
    return app, side_effects, multi


def saved(**overrides):
    raw = {
        "w": "800.125", "h": "1600.5", "d": "350.75",
        "t": "2", "fw": "25.5", "draw_stock": "false",
        "zl1": "-3.125", "door_fold_l": "-1.625",
        "base_plate_shrink_left": "-0.75",
        "ui_text_size": "大", "unrecognized_legacy": "unused",
    }
    raw.update(overrides)
    return {
        "settings": raw,
        "multi_door_enabled": "false",
        "corner_state": {}, "corner_pair_same": {},
    }


def test_valid_saved_vault_settings_equal_public_engine_and_json_reload():
    raw = json.loads(json.dumps(saved(), ensure_ascii=False))
    before = deepcopy(raw)
    app, effects, multi = host()
    gui._restore_cabinet_family_runtime(app, raw)
    entered = effects[0]
    physical = {
        key: api.normalize_operator_source_dimension(raw["settings"][key], field=key)
        for key in ("w", "h", "d", "t", "fw")
    }
    other_raw = {
        key: raw["settings"][key]
        for key in ("zl1", "door_fold_l", "base_plate_shrink_left", "draw_stock")
    }
    other = api.normalize_operator_settings_updates(
        app.settings_service.snapshot().as_dict(), other_raw,
    )
    assert entered == ("settings", {**physical, **other}, {"recalculate": False})
    assert entered[1]["draw_stock"] is False
    assert entered[1]["zl1"] == -3.125
    assert entered[1]["base_plate_shrink_left"] == -0.75
    assert "unrecognized_legacy" not in entered[1]
    assert "ui_text_size" not in entered[1]
    assert multi.get() is False
    assert raw == before


@pytest.mark.parametrize(("field", "bad"), [
    ("zl1", True), ("door_fold_l", False),
    ("base_plate_shrink_left", "nan"),
    ("door_fold_l", "garbage"), ("zl1", float("inf")),
    ("w", True), ("fw", "-1"), ("draw_stock", "maybe"),
])
def test_bad_saved_setting_rejects_atomically_before_any_gui_side_effect(field, bad):
    app, effects, multi = host()
    raw = saved(**{field: bad})
    prior = deepcopy(raw)
    with pytest.raises((ValueError, TypeError)):
        gui._restore_cabinet_family_runtime(app, raw)
    assert effects == []
    assert multi.set_calls == []
    assert app.settings_service.snapshot().as_dict() == Settings().values
    assert raw == prior


def test_gui_does_not_convert_saved_vault_fold_bool_to_one_mm():
    from inspect import getsource
    source = getsource(gui._restore_cabinet_family_runtime)
    assert "manufacturing_api.normalize_operator_settings_updates(current, other_raw)" in source
    assert "manufacturing_api.normalize_operator_source_dimension(raw, field=key)" in source
    assert "values[key] = float(raw)" not in source
