"""#2517 Fold Designer full live source uses public Engine before GUI mutation."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace
import pytest
from ae_engine import manufacturing_api as api
from gui_modules.application import lifecycle as gui


class Var:
    def __init__(self, value, events=None):
        self.value = value
        self.events = events

    def get(self):
        return self.value

    def set(self, value):
        if self.events is not None:
            self.events.append(("variable", value))
        self.value = value


def source(**changes):
    payload = {
        "origin": "external", "model": "金庫型",
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail", "door"],
        "settings": {"w": 800.125},
        "multi_door_enabled": "false",
        "use_box_distance": "false",
        "door_nameplate_center_datum_top": "140.25",
        "door_layout_columns": [["400.125", ["800.25", "800.25"]], ["400", ["1600.5"]]],
        "workspace": {
            "existing_parts": ["box_body", "head", "tail", "door"],
            "part_features": {"door_c1_r1": [{"source": "physical"}]},
        },
    }
    payload.update(changes)
    return payload


def host():
    events = []
    host = SimpleNamespace(
        _fold_designer_live_sync_guard=False,
        baseline_var=Var("金庫型", events),
        _phase6_last_fold_designer_live_payload=None,
        _apply_fold_designer_live_settings=lambda *a, **kw: events.append(("settings",)),
        _apply_manual_corner_snapshot=lambda *a: events.append(("corners",)),
        _set_box_assembly_type=lambda *a, **kw: events.append(("joint",)),
        _phase6_current_existing_parts=lambda: ("box_body", "head", "tail", "door"),
        _apply_endcap_fw_snapshot=lambda *a: events.append(("fw",)),
        is_box_dist_var=Var(True, events),
        door_nameplate_center_datum_top=99.0,
        multi_door_enabled_var=Var(True, events),
        _store_fold_designer_workspace=lambda *a: events.append(("workspace",)),
        _apply_existing_parts_from_fold_workspace=lambda *a, **kw: events.append(("parts",)),
        surface_features={"head": [], "tail": []},
        w_var=Var("800.125"),
        d_var=Var("350"),
        box_body_face_features={},
        door_layout_columns=[],
        get_door_layout_columns=lambda: (),
        _sync_fold_designer_manual_corner_context=lambda *a: events.append(("context",)),
        refresh_corner_type_panel=lambda: events.append(("panel",)),
        _phase6_update_scheduler=SimpleNamespace(mark_dirty=lambda *a: events.append(("dirty",))),
        project_controller=SimpleNamespace(capture_committed=lambda *a: events.append(("capture",))),
        _compose_phase6_project_snapshot_from_main_gui=lambda: {},
    )
    def set_columns(rows):
        host.door_layout_columns = deepcopy(rows)
        events.append(("layout", deepcopy(rows)))
    host.set_door_layout_columns = set_columns
    return host, events


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,bad", [
    ("multi_door_enabled", "invalid"),
    ("multi_door_enabled", 2),
    ("use_box_distance", "invalid"),
    ("use_box_distance", float("nan")),
    ("door_nameplate_center_datum_top", True),
    ("door_nameplate_center_datum_top", float("inf")),
    ("door_layout_columns", [[True, [800]]]),
    ("door_layout_columns", [[400, ["nan"]]]),
    ("door_layout_columns", [[400, []]]),
])
def test_bad_full_live_door_source_rejected_before_any_gui_mutation(family, field, bad):
    app, events = host()
    saved = source(model=family, **{field: bad})
    prior = deepcopy(saved)
    with pytest.raises((ValueError, TypeError)):
        gui._apply_fold_designer_live_snapshot(app, saved)
    assert events == []
    assert app._fold_designer_live_sync_guard is False
    assert app.multi_door_enabled_var.get() is True
    assert app.door_nameplate_center_datum_top == 99.0
    assert str(saved) == str(prior)


@pytest.mark.parametrize("family,flag", [
    ("金庫型", "false"), ("受電箱", "off"),
    ("金庫型", "true"), ("受電箱", "on"),
])
def test_live_door_grid_and_saved_boolean_matches_headless_engine(family, flag, monkeypatch):
    app, events = host()
    saved = json.loads(json.dumps(source(model=family, multi_door_enabled=flag), ensure_ascii=False))
    prior = deepcopy(saved)
    expected = api.project_operator_saved_door_layout_columns(saved["door_layout_columns"])
    monkeypatch.setattr(api, "project_operator_endcap_legacy_hole_rows", lambda *a, **kw: {})
    result = gui._apply_fold_designer_live_snapshot(app, saved)
    assert result is True
    assert app._fold_designer_live_sync_guard is False
    assert app.door_layout_columns == expected
    assert app.multi_door_enabled_var.get() is api.normalize_operator_settings_boolean(flag)
    assert app.is_box_dist_var.get() is False
    assert app.door_nameplate_center_datum_top == 140.25
    assert next(row[1] for row in events if row[0] == "layout") == expected
    assert saved == prior


def test_absent_saved_grid_keeps_preexisting_operator_grid(monkeypatch):
    app, events = host()
    app.get_door_layout_columns = lambda: [[600, [1600]]]
    monkeypatch.setattr(api, "project_operator_endcap_legacy_hole_rows", lambda *a, **kw: {})
    saved = source(door_layout_columns=None)
    assert gui._apply_fold_designer_live_snapshot(app, saved) is True
    assert any(row[0] == "capture" for row in events)
    assert not any(row[0] == "layout" for row in events)


def test_full_live_source_uses_public_engine_and_leaves_quantity_shortcut():
    src = inspect.getsource(gui._apply_fold_designer_live_snapshot)
    assert src.index("if custom_part_only_change") < src.index(
        "manufacturing_api.project_operator_saved_door_layout_columns("
    )
    for name in (
        "normalize_operator_settings_boolean",
        "normalize_operator_door_nameplate_center_datum_top",
        "project_operator_saved_door_layout_columns",
    ):
        assert f"manufacturing_api.{name}(" in src
    assert src.index("manufacturing_api.project_operator_saved_door_layout_columns(") < src.index(
        "self._apply_fold_designer_live_settings("
    )
    assert "float(row[0])" not in src
    assert "float(datum)" not in src
    assert 'bool(payload.get("multi_door_enabled"' not in src
