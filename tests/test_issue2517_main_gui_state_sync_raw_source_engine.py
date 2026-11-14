"""#2517: main GUI Settings sync must preserve Engine raw-source rejection."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import state_sync


NUMERIC = (
    "w", "h", "d", "t", "fw", "zl1", "zl2", "zr1", "zr2", "z_comp",
    "yl1", "yr1", "ytop1", "ybottom1", "door_gap_w", "door_gap_h",
    "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b",
    "base_plate_shrink_top", "base_plate_shrink_bottom",
    "base_plate_shrink_left", "base_plate_shrink_right", "base_plate_bend",
)


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Snapshot:
    def __init__(self, values):
        self.values = dict(values)

    def as_dict(self):
        return dict(self.values)

    def __getitem__(self, key):
        return self.values[key]


class Service:
    def __init__(self, initial):
        self.values = dict(initial)
        self.updates = []

    def snapshot(self):
        return Snapshot(self.values)

    def update(self, updates):
        self.updates.append(dict(updates))
        self.values.update(updates)
        return self.snapshot()


class Scheduler:
    def __init__(self):
        self.calls = []

    def begin(self):
        self.calls.append("begin")

    def mark_dirty(self, key):
        self.calls.append(key)

    def end(self):
        self.calls.append("end")


def _raw():
    values = {key: "19.25" for key in NUMERIC}
    values.update({
        "w": "800.125", "h": "1600.5", "d": "350.75",
        "t": "2.0", "fw": "25.5", "zl1": "-3.125",
        "base_plate_shrink_left": "-2.5", "draw_stock": "false",
    })
    return values


def _host(raw):
    initial = {key: 2.0 for key in NUMERIC}
    initial.update({"w": 800.0, "h": 1600.0, "d": 350.0,
                    "t": 2.0, "fw": 25.0, "draw_stock": True})
    service = Service(initial)
    scheduler = Scheduler()
    host = SimpleNamespace(
        settings_service=service,
        _setting_var_map=lambda: {key: Var(value) for key, value in raw.items()},
        _phase6_update_scheduler=scheduler,
        fold_designer_app=None,
        _settings_sync_guard=False,
    )
    return host, service, scheduler


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_collect_all_main_settings_matches_public_engine_and_json_roundtrip(family):
    raw = json.loads(json.dumps(_raw()))
    before = deepcopy(raw)
    host, service, _ = _host(raw)
    physical = api.normalize_operator_source_dimensions(raw)
    other = api.normalize_operator_settings_updates(
        service.snapshot().as_dict(),
        {key: value for key, value in raw.items() if key not in physical},
    )
    result = state_sync.collect_main_setting_values(host)
    assert len(service.updates) == 1
    assert service.updates[0] == {**physical, **other}
    assert result["w"] == 800.125 and result["zl1"] == -3.125
    assert result["base_plate_shrink_left"] == -2.5
    assert result["draw_stock"] is False
    assert raw == before
    assert family in ("金庫型", "受電箱")


@pytest.mark.parametrize(("field", "invalid"), [
    ("w", True), ("fw", "nan"), ("t", "0"),
    ("zl1", True), ("door_fold_l", "inf"),
    ("base_plate_shrink_left", "bad"), ("draw_stock", "maybe"),
])
def test_collect_bad_raw_setting_does_not_commit_any_other_field(field, invalid):
    raw = _raw()
    raw[field] = invalid
    saved = deepcopy(raw)
    host, service, _ = _host(raw)
    before = service.snapshot().as_dict()
    with pytest.raises(ValueError):
        state_sync.collect_main_setting_values(host)
    assert raw == saved
    assert service.updates == []
    assert service.snapshot().as_dict() == before


@pytest.mark.parametrize(("field", "invalid"), [
    ("w", True), ("fw", "inf"), ("door_fold_l", "nan"),
    ("base_plate_bend", False), ("draw_stock", "invalid"),
])
def test_live_invalid_source_cannot_schedule_or_commit(field, invalid):
    host, service, scheduler = _host(_raw())
    before = service.snapshot().as_dict()
    state_sync.on_main_setting_var_changed(host, field, Var(invalid))
    assert service.updates == []
    assert scheduler.calls == []
    assert service.snapshot().as_dict() == before


def test_live_nonphysical_fold_and_stock_commit_exact_public_engine_values():
    host, service, scheduler = _host(_raw())
    state_sync.on_main_setting_var_changed(host, "door_fold_l", Var("-1.625"))
    state_sync.on_main_setting_var_changed(host, "draw_stock", Var("false"))
    assert service.updates == [{"door_fold_l": -1.625}, {"draw_stock": False}]
    assert service.snapshot()["door_fold_l"] == -1.625
    assert service.snapshot()["draw_stock"] is False
    assert scheduler.calls == [
        "begin", "setting:door_fold_l", "end",
        "begin", "setting:draw_stock", "end",
    ]
