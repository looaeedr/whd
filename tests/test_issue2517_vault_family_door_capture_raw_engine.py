"""#2517 Vault Family preset capture never erases broken physical Door grid source."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as cabinet
from gui_modules.application import door_layout_host_adapter as door


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def host(columns, *, switch="false", profile=None):
    events = []
    workspace = SimpleNamespace(
        box_body_profile=lambda: profile if profile is not None else None,
        set_box_body_profile=lambda value: events.append(("profile", value)),
        box_body_structure_state=lambda: {"active_type": "INTEGRAL"},
    )
    app = SimpleNamespace(
        workspace_controller=workspace,
        _setting_var_map=lambda: {
            "w": Var("800.125"), "h": Var("1600.5"),
            "d": Var("350.25"), "t": Var("2"), "fw": Var("25"),
        },
        _current_cabinet_type_name=lambda: "金庫型",
        _serialize_manual_corner_state=lambda: {},
        manual_corner_pair_same={},
        multi_door_enabled_var=Var(switch),
        door_layout_columns=deepcopy(columns),
    )
    app.get_door_layout_columns = lambda: door.get_door_layout_columns(app)
    return app, events


def test_capture_preserves_exact_engine_validated_door_cells_and_json_roundtrip():
    columns = [["400.125", ["800.25", "800.25"]],
               ["400", ["1600.5"]]]
    app, events = host(columns, switch="true", profile=[{"phase6_key": "test"}])
    saved_before = deepcopy(app.door_layout_columns)
    captured = cabinet._capture_cabinet_family_runtime(app)
    expected = [
        [api.normalize_operator_source_dimension(w, field="w"),
         [api.normalize_operator_source_dimension(h, field="h") for h in heights]]
        for w, heights in columns
    ]
    assert captured["door_layout_columns"] == expected
    assert captured["multi_door_enabled"] is True
    assert captured["box_body_profile"] == [{"phase6_key": "test"}]
    reloaded = json.loads(json.dumps(captured, ensure_ascii=False))
    assert reloaded["door_layout_columns"] == expected
    assert app.door_layout_columns == saved_before
    assert events == []


@pytest.mark.parametrize("bad", [
    [True, [1600.5]], ["nan", [1600.5]],
    [400, [True]], [400, [float("inf")]],
    [400, [0]], [400, ["invalid"]],
])
def test_bad_live_door_cell_never_becomes_empty_saved_layout_or_mutates_workspace(
    monkeypatch, bad,
):
    columns = [[400, [1600.5]], bad]
    app, events = host(columns, profile=None)
    prior = deepcopy(app.door_layout_columns)
    monkeypatch.setattr(api, "build_box_body_fold_profile",
                        lambda *a, **kw: pytest.fail("invalid Door source must not build profile"))
    with pytest.raises((ValueError, TypeError)):
        cabinet._capture_cabinet_family_runtime(app)
    assert app.door_layout_columns == prior
    assert events == []


@pytest.mark.parametrize("raw", ["invalid", None, 2, float("inf")])
def test_bad_multi_door_flag_rejected_before_box_profile_creation(monkeypatch, raw):
    app, events = host([[400, [1600.5]]], switch=raw, profile=None)
    monkeypatch.setattr(api, "build_box_body_fold_profile",
                        lambda *a, **kw: pytest.fail("bad switch must not build profile"))
    with pytest.raises(ValueError, match="布林"):
        cabinet._capture_cabinet_family_runtime(app)
    assert events == []


def test_no_door_grid_keeps_legacy_empty_layout_without_inventing_cells():
    app, events = host([], profile=[{"phase6_key": "test"}])
    captured = cabinet._capture_cabinet_family_runtime(app)
    assert captured["door_layout_columns"] == []
    assert captured["multi_door_enabled"] is False
    assert events == []


def test_capture_does_not_silently_replace_invalid_door_source_with_empty_layout():
    import inspect
    source = inspect.getsource(cabinet._capture_cabinet_family_runtime)
    assert "manufacturing_api.normalize_operator_source_dimension(width, field=\"w\")" in source
    assert "manufacturing_api.normalize_operator_source_dimension(height, field=\"h\")" in source
    assert "except Exception:" not in source
    assert "float(width)" not in source
    restore = inspect.getsource(cabinet._restore_cabinet_family_runtime)
    assert "self.set_door_layout_columns(layout)" in restore
    assert "float(row[0])" not in restore
    assert restore.index('manufacturing_api.normalize_operator_source_dimension(width, field="w")') < restore.index("self._apply_fold_designer_live_settings(")


class TrackedVar(Var):
    def __init__(self, value, writes):
        super().__init__(value)
        self.writes = writes

    def set(self, value):
        self.writes.append(("multi", value))
        self.value = value


def restore_host():
    app, events = host([], profile=[{"phase6_key": "profile"}])
    app._apply_fold_designer_live_settings = (
        lambda values, **kw: events.append(("settings", dict(values)))
    )
    app._apply_manual_corner_snapshot = (
        lambda *args: events.append(("corners", args))
    )
    app.multi_door_enabled_var = TrackedVar("false", events)
    app.set_door_layout_columns = (
        lambda values: events.append(("layout", deepcopy(values)))
    )
    app.workspace_controller.set_box_body_structure_state = (
        lambda value: events.append(("structure", value))
    )
    app.workspace_controller.set_box_body_profile = (
        lambda value: events.append(("profile", value))
    )
    return app, events


@pytest.mark.parametrize("bad", [
    [True, [1600.5]], ["nan", [1600.5]],
    [400, [True]], [400, [0]],
    [400, ["inf"]], [400, []],
    ["invalid-row"], "invalid-row",
])
def test_restore_rejects_bad_saved_door_cell_before_any_physical_side_effect(bad):
    app, events = restore_host()
    payload = {
        "settings": {"w": "800.125", "draw_stock": "false"},
        "multi_door_enabled": "true",
        "door_layout_columns": [[400, [1600.5]], bad],
    }
    before = deepcopy(payload)
    with pytest.raises((ValueError, TypeError)):
        cabinet._restore_cabinet_family_runtime(app, payload)
    assert events == []
    assert payload == before


def test_restore_uses_same_public_engine_dimensions_for_json_saved_door_grid():
    app, events = restore_host()
    source = {
        "settings": {"w": "800.125", "draw_stock": "false"},
        "multi_door_enabled": "true",
        "door_layout_columns": [["400.125", ["800.25", "800.25"]],
                                ["400", ["1600.5"]]],
    }
    raw = json.loads(json.dumps(source, ensure_ascii=False))
    cabinet._restore_cabinet_family_runtime(app, raw)
    saved = next(row[1] for row in events if row[0] == "layout")
    expected = [
        (api.normalize_operator_source_dimension(width, field="w"),
         [api.normalize_operator_source_dimension(h, field="h") for h in heights])
        for width, heights in raw["door_layout_columns"]
    ]
    assert saved == expected
    assert events[0][0] == "settings"
    assert raw == source
