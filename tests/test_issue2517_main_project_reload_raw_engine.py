"""#2517: saved .p6fold Door manufacturing source uses Engine at Open/Reload."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import lifecycle as gui


class Var:
    def __init__(self, raw, events=None):
        self.raw, self.events = raw, events

    def get(self):
        return self.raw

    def set(self, value):
        if self.events is not None:
            self.events.append(("variable", value))
        self.raw = value


def host():
    events = []
    app = SimpleNamespace(
        settings_service=SimpleNamespace(snapshot=lambda: {"w": 800.0}),
        multi_door_enabled_var=Var(True, events),
        door_layout_columns=[["old", ["old"]]],
        door_nameplate_center_datum_top=99.0,
        is_box_dist_var=None,
        _apply_fold_designer_live_settings=lambda values, **kw:
            events.append(("settings", deepcopy(values))),
        _apply_manual_corner_snapshot=lambda *args:
            events.append(("corners",)),
        _set_box_assembly_type=lambda *args, **kw:
            events.append(("joint",)),
        _apply_endcap_fw_snapshot=lambda value: events.append(("endcap_fw",)),
        _store_fold_designer_workspace=lambda value: events.append(("workspace", deepcopy(value))),
        _sync_fold_designer_manual_corner_context=lambda value:
            events.append(("corner_context", value)),
        _reload_current_baseline_features=lambda: events.append(("features",)),
        _request_phase6_update=lambda why: events.append(("update", why)),
    )
    def apply_columns(cols):
        app.door_layout_columns = deepcopy(cols)
        events.append(("layout", deepcopy(cols)))
    app.set_door_layout_columns = apply_columns
    return app, events


def saved(**updates):
    raw = {
        "model": "金庫型", "assembly_type": "INSERT_OVERLAY",
        "settings": {"w": 800.125},
        "w": 800.125, "h": 1600.5,
        "box_body_profile": [{"phase6_key": "zr1", "len": 25}],
        "existing_parts": ["box_body", "head", "tail", "door"],
        "multi_door_enabled": "false",
        "door_layout_columns": [["400.125", ["800.25", "800.25"]],
                                ["400", ["1600.5"]]],
        "door_nameplate_center_datum_top": "140.125",
        "corner_state": {}, "corner_pair_same": {},
    }
    raw.update(updates)
    return raw


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,bad", [
    ("multi_door_enabled", "invalid"),
    ("multi_door_enabled", 2),
    ("door_nameplate_center_datum_top", True),
    ("door_nameplate_center_datum_top", "nan"),
    ("door_layout_columns", [[400, [1600.5]], [True, [1600.5]]]),
    ("door_layout_columns", [[400, [1600.5]], [400, [float("inf")]]]),
    ("door_layout_columns", [[400, [1600.5]], [400, []]]),
])
def test_corrupt_saved_door_source_rejected_before_all_settings(model, field, bad):
    app, events = host()
    source = saved(model=model, **{field: bad})
    prior = deepcopy(source)
    with pytest.raises((ValueError, TypeError)):
        gui._apply_original_fold_designer_snapshot(app, source)
    assert events == []
    assert app.multi_door_enabled_var.get() is True
    assert app.door_nameplate_center_datum_top == 99.0
    assert str(source) == str(prior)


@pytest.mark.parametrize("model,flag", [
    ("金庫型", "false"), ("受電箱", "off"),
    ("金庫型", "true"), ("受電箱", "on"),
])
def test_saved_valid_door_roundtrip_exact_public_engine(model, flag):
    app, events = host()
    source = json.loads(json.dumps(saved(model=model, multi_door_enabled=flag), ensure_ascii=False))
    before = deepcopy(source)
    columns = api.project_operator_saved_door_layout_columns(source["door_layout_columns"])
    gui._apply_original_fold_designer_snapshot(app, source)
    assert app.multi_door_enabled_var.get() is api.normalize_operator_settings_boolean(flag)
    assert app.door_layout_columns == columns
    assert app.door_nameplate_center_datum_top == api.normalize_operator_door_nameplate_center_datum_top("140.125")
    assert events[0][0] == "settings"
    assert next(v for name, v in events if name == "layout") == columns
    assert source == before


def test_absent_legacy_door_layout_remains_single_door():
    app, events = host()
    gui._apply_original_fold_designer_snapshot(
        app, saved(multi_door_enabled=False, door_layout_columns=[], door_nameplate_center_datum_top=None),
    )
    assert app.multi_door_enabled_var.get() is False
    assert app.door_layout_columns == []
    assert app.door_nameplate_center_datum_top is None
    assert not any(row[0] == "layout" for row in events)


@pytest.mark.parametrize("field,bad", [
    ("multi_door_enabled", "bad"),
    ("door_layout_columns", [[True, [1600.5]]]),
    ("door_layout_columns", [[400, [float("nan")]]]),
])
def test_main_open_rejects_bad_door_before_receiving_session_reset(field, bad):
    events = []
    app = SimpleNamespace(
        workspace_controller=SimpleNamespace(reset_receiving_mode_session=lambda: events.append("reset")),
        _reset_manual_corner_parameter_locks=lambda: events.append("corner_reset"),
    )
    source = saved(**{field: bad})
    with pytest.raises((ValueError, TypeError)):
        gui._apply_phase6_project_snapshot(app, source)
    assert events == []


def test_main_project_open_reads_public_engine_source_no_local_float_bool():
    outer = inspect.getsource(gui._apply_phase6_project_snapshot)
    inner = inspect.getsource(gui._apply_original_fold_designer_snapshot)
    assert "if multi_door_enabled and door_columns:" in outer
    assert "manufacturing_api.project_operator_saved_door_layout_columns(" in outer
    assert "float(row[0])" not in outer
    assert "manufacturing_api.normalize_operator_settings_boolean(" in inner
    assert "manufacturing_api.project_operator_saved_door_layout_columns(" in inner
    assert "manufacturing_api.normalize_operator_door_nameplate_center_datum_top(" in inner
    assert inner.index("manufacturing_api.project_operator_saved_door_layout_columns(") < inner.index(
        "self._apply_fold_designer_live_settings("
    )
    assert "float(row[0])" not in inner
    assert "float(datum)" not in inner
