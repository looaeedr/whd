"""#2517 Door nameplate top datum raw source uses one public Engine owner."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import door_operator_part_spec as owner
from gui_modules.application import cabinet_controller as gui
from gui_modules.application import manufacturing_adapter as manufacturing_gui


class Var:
    def __init__(self, value, events=None):
        self.value = value
        self.events = events

    def get(self):
        return self.value

    def set(self, value):
        if self.events is not None:
            self.events.append(("var", value))
        self.value = value


def _host(datum, *, profile=None):
    events = []
    workspace = SimpleNamespace(
        box_body_profile=lambda: profile,
        box_body_structure_state=lambda: {},
        set_box_body_profile=lambda value: events.append(("profile", value)),
        set_box_body_structure_state=lambda value: events.append(("structure", value)),
    )
    app = SimpleNamespace(
        workspace_controller=workspace,
        _setting_var_map=lambda: {"w": Var("800.125"), "h": Var("1600.5")},
        _current_cabinet_type_name=lambda: "金庫型",
        _serialize_manual_corner_state=lambda: {},
        manual_corner_pair_same={},
        multi_door_enabled_var=Var("false", events),
        door_layout_columns=[],
        door_nameplate_center_datum_top=datum,
        _apply_fold_designer_live_settings=lambda values, **kw:
            events.append(("settings", dict(values))),
        _apply_manual_corner_snapshot=lambda *args:
            events.append(("corners", args)),
    )
    return app, events


@pytest.mark.parametrize("raw,expected", [
    (None, None), ("140.125", 140.125), (140.125, 140.125),
    ("-2.5", -2.5), (0, 0.0), ("0", 0.0),
])
def test_public_alias_is_same_door_owner_and_preserves_exact_saved_datum(raw, expected):
    assert api.normalize_operator_door_nameplate_center_datum_top is (
        owner.normalize_operator_door_nameplate_center_datum_top
    )
    assert ae_engine.normalize_operator_door_nameplate_center_datum_top is (
        owner.normalize_operator_door_nameplate_center_datum_top
    )
    saved = json.loads(json.dumps({"datum": raw}))
    assert api.normalize_operator_door_nameplate_center_datum_top(saved["datum"]) == expected
    host, events = _host(raw, profile=[{"phase6_key": "box"}])
    captured = gui._capture_cabinet_family_runtime(host)
    assert captured["door_nameplate_center_datum_top"] == expected
    assert events == []
    restored, writes = _host(None, profile=[{"phase6_key": "box"}])
    gui._restore_cabinet_family_runtime(restored, captured)
    assert restored.door_nameplate_center_datum_top == expected
    assert captured["door_nameplate_center_datum_top"] == expected
    assert writes[0][0] == "settings"


@pytest.mark.parametrize("bad", [
    True, False, float("nan"), float("inf"), float("-inf"),
    "nan", "inf", "1e309", "bad", [], {},
])
def test_bad_datum_fails_before_box_profile_capture_or_restore_commit(bad, monkeypatch):
    before = deepcopy({"nameplate": bad})
    app, events = _host(bad, profile=None)
    monkeypatch.setattr(api, "build_box_body_fold_profile",
                        lambda *args, **kw: pytest.fail("invalid datum reached BoxBody profile"))
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        gui._capture_cabinet_family_runtime(app)
    assert events == []
    restore, writes = _host(None, profile=[])
    incoming = {"door_nameplate_center_datum_top": bad,
                "settings": {"w": "800.125", "draw_stock": "false"}}
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        gui._restore_cabinet_family_runtime(restore, incoming)
    assert writes == []
    assert restore.door_nameplate_center_datum_top is None
    assert str(before["nameplate"]) == str(bad)


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_gui_door_part_spec_matches_direct_engine_nameplate_source(model):
    values = {
        "w": 800, "h": 1600, "t": 2, "fw": 29 if model == "受電箱" else 25,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19, "door_fold_r": 19,
        "door_fold_t": 19, "door_fold_b": 19,
    }
    raw = "140.375"
    direct = api.build_door_operator_part_spec(
        values, model_name=model, nameplate_center_datum_top=raw,
    )
    host = SimpleNamespace(door_nameplate_center_datum_top=raw)
    via_gui = manufacturing_gui._door_part_spec_from_values(
        host, values, model_name=model, features=(),
    )
    assert via_gui == direct
    assert direct.nameplate_center_datum_top == 140.375
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        api.build_door_operator_part_spec(
            values, model_name=model, nameplate_center_datum_top=True,
        )


def test_gui_no_local_float_datum_and_engine_uses_single_helper():
    capture = inspect.getsource(gui._capture_cabinet_family_runtime)
    restore = inspect.getsource(gui._restore_cabinet_family_runtime)
    receiving = inspect.getsource(gui._apply_cabinet_family_for_current_model)
    engine = inspect.getsource(owner.build_door_operator_part_spec)
    assert "normalize_operator_door_nameplate_center_datum_top(" in capture
    assert "normalize_operator_door_nameplate_center_datum_top(" in restore
    assert "normalize_operator_door_nameplate_center_datum_top(" in receiving
    assert "normalize_operator_door_nameplate_center_datum_top(" in engine
    assert "float(datum)" not in restore
    assert 'float(values["door_nameplate_center_datum_top"])' not in receiving
