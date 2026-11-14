"""#2517: cabinet Family runtime GUI is a public Engine boolean client."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as gui


class OperatorVar:
    def __init__(self, raw):
        self.value = raw
        self.writes = 0

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes += 1


def _host(raw_multi="false", raw_stock="false"):
    events = []
    multi_var = OperatorVar(raw_multi)
    workspace = SimpleNamespace(
        box_body_profile=lambda: [{"phase6_key": "stock", "len": 45}],
        box_body_structure_state=lambda: {},
        set_box_body_structure_state=lambda state: events.append(("structure", state)),
        set_box_body_profile=lambda profile: events.append(("profile", profile)),
    )
    host = SimpleNamespace(
        workspace_controller=workspace,
        _setting_var_map=lambda: {"draw_stock": OperatorVar(raw_stock)},
        _serialize_manual_corner_state=lambda: {},
        manual_corner_pair_same={},
        multi_door_enabled_var=multi_var,
        door_layout_columns=[],
        _apply_fold_designer_live_settings=lambda values, *, recalculate: events.append(
            ("settings", dict(values), recalculate)
        ),
        _apply_manual_corner_snapshot=lambda *args: events.append(("corner", args)),
        _current_cabinet_type_name=lambda: "金庫型",
    )
    return host, events, multi_var


@pytest.mark.parametrize("raw,expected", (
    ("false", False), ("FALSE", False), ("0", False), ("off", False),
    ("no", False), ("", False), (0, False), (False, False),
    ("true", True), ("YES", True), ("1", True), (1, True), (True, True),
))
def test_capture_and_restore_multi_door_switch_use_public_engine(raw, expected):
    host, events, multi_var = _host(raw_multi=raw)
    captured = gui._capture_cabinet_family_runtime(host)
    assert captured["multi_door_enabled"] is expected
    assert api.normalize_operator_settings_boolean(raw) is expected
    source = {
        "settings": {"draw_stock": "false", "w": "450.5"},
        "multi_door_enabled": raw,
    }
    saved = json.loads(json.dumps(source))
    original = deepcopy(saved)
    gui._restore_cabinet_family_runtime(host, saved)
    assert multi_var.get() is expected
    assert multi_var.writes == 1
    assert ("settings", {"draw_stock": False, "w": 450.5}, False) in events
    assert saved == original


@pytest.mark.parametrize("raw,expected", (
    ("false", False), ("0", False), (False, False),
    ("true", True), ("on", True), (1, True),
))
def test_restored_stock_control_preserves_engine_boolean(raw, expected):
    host, events, _ = _host()
    gui._restore_cabinet_family_runtime(
        host, {"multi_door_enabled": False, "settings": {"draw_stock": raw}},
    )
    assert ("settings", {"draw_stock": expected}, False) in events


def test_absent_legacy_multi_door_defaults_off_and_is_not_inferred_from_stock():
    host, events, multi_var = _host(raw_multi=True)
    gui._restore_cabinet_family_runtime(host, {"settings": {"draw_stock": True}})
    assert multi_var.get() is False
    assert ("settings", {"draw_stock": True}, False) in events


@pytest.mark.parametrize("field,bad", (
    ("multi_door_enabled", None), ("multi_door_enabled", "invalid"),
    ("multi_door_enabled", 2), ("multi_door_enabled", []),
    ("multi_door_enabled", float("inf")),
    ("draw_stock", None), ("draw_stock", "nonsense"),
    ("draw_stock", 1.5), ("draw_stock", {}),
))
def test_invalid_serialized_flags_reject_atomically_before_any_gui_mutation(
    field, bad,
):
    host, events, multi_var = _host(raw_multi=False)
    source = {"multi_door_enabled": False, "settings": {"draw_stock": False}}
    if field == "draw_stock":
        source["settings"][field] = bad
    else:
        source[field] = bad
    before = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        gui._restore_cabinet_family_runtime(host, source)
    assert events == []
    assert multi_var.writes == 0
    assert source == before


@pytest.mark.parametrize("bad", (None, 2, "maybe", [], float("inf")))
def test_invalid_live_family_switch_cannot_be_captured_as_enabled(bad):
    host, _, _ = _host(raw_multi=bad)
    with pytest.raises(ValueError, match="布林值"):
        gui._capture_cabinet_family_runtime(host)


def test_gui_family_preset_has_no_python_truthiness_manufacturing_switch():
    capture = inspect.getsource(gui._capture_cabinet_family_runtime)
    restore = inspect.getsource(gui._restore_cabinet_family_runtime)
    assert "manufacturing_api.normalize_operator_settings_boolean(" in capture
    assert "manufacturing_api.normalize_operator_settings_boolean(" in restore
    assert 'bool(self.multi_door_enabled_var.get())' not in capture
    assert 'bool(state.get("multi_door_enabled"' not in restore
    assert 'bool(raw) if key == "draw_stock"' not in restore
