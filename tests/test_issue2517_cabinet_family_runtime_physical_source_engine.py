"""#2517: Main GUI Family preset restores physical mm via the public Engine API."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import cabinet_controller as gui


class Var:
    def __init__(self, value):
        self.value = value
        self.writes = 0

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes += 1


def _host(family="金庫型"):
    calls = []
    multi = Var(False)
    controller = SimpleNamespace(
        set_box_body_structure_state=lambda value: calls.append(("structure", value)),
        set_box_body_profile=lambda value: calls.append(("profile", value)),
    )
    host = SimpleNamespace(
        workspace_controller=controller,
        multi_door_enabled_var=multi,
        door_layout_columns=[],
        _current_cabinet_type_name=lambda: family,
        _apply_fold_designer_live_settings=lambda values, *, recalculate: calls.append(
            ("settings", dict(values), recalculate)
        ),
        _apply_manual_corner_snapshot=lambda *args: calls.append(("corners", args)),
    )
    return host, multi, calls


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_saved_family_physical_mm_uses_original_engine_source_and_json_roundtrip(family):
    host, multi, calls = _host(family)
    saved = {
        "settings": {
            "w": "800.125", "h": "1600.375", "d": "350.625",
            "t": "2.25", "fw": "29.5", "draw_stock": "false",
            "yl1": "0", "zr1": "-5",
        },
        "multi_door_enabled": "false",
    }
    before = deepcopy(saved)
    restored = json.loads(json.dumps(saved, ensure_ascii=False))
    gui._restore_cabinet_family_runtime(host, restored)
    physical = {field: api.normalize_operator_source_dimension(
        before["settings"][field], field=field
    ) for field in api.PHYSICAL_SNAPSHOT_SOURCE_KEYS}
    settings = next(row[1] for row in calls if row[0] == "settings")
    assert {field: settings[field] for field in physical} == physical
    assert settings["draw_stock"] is False
    assert settings["yl1"] == 0.0 and settings["zr1"] == -5.0
    assert multi.get() is False and multi.writes == 1
    assert restored == before


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
@pytest.mark.parametrize("bad", (
    True, False, 0, -1, None, "nan", "inf", "-inf", [], {},
))
def test_invalid_saved_physical_source_fails_before_any_gui_or_workspace_mutation(
    field, bad,
):
    host, multi, calls = _host("受電箱")
    saved = {
        "settings": {
            "w": "800.125", "h": "1600.375", "d": "350.625",
            "t": "2.25", "fw": "29.5", "draw_stock": "false",
        },
        "multi_door_enabled": "true",
    }
    saved["settings"][field] = bad
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="包外尺寸"):
        gui._restore_cabinet_family_runtime(host, saved)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(bad, field=field)
    assert saved == before
    assert calls == []
    assert multi.writes == 0


def test_legacy_missing_physical_keys_and_nonphysical_bad_source_keep_compatibility():
    host, multi, calls = _host()
    saved = {
        "settings": {
            "draw_stock": "off", "yl1": "not-a-number",
            "zl1": "0", "yr1": "-2.125",
        },
    }
    gui._restore_cabinet_family_runtime(host, saved)
    settings = next(row[1] for row in calls if row[0] == "settings")
    assert settings == {"draw_stock": False, "zl1": 0.0, "yr1": -2.125}
    assert multi.get() is False


@pytest.mark.parametrize("value", ("0.001", "125.625", 2, 25.0))
def test_valid_single_physical_snapshot_field_preserves_precision(value):
    host, _, calls = _host()
    gui._restore_cabinet_family_runtime(host, {"settings": {"fw": value}})
    settings = next(row[1] for row in calls if row[0] == "settings")
    assert settings["fw"] == api.normalize_operator_source_dimension(value, field="fw")


def test_gui_family_restore_never_erases_physical_source_before_engine_validation():
    source = inspect.getsource(gui._restore_cabinet_family_runtime)
    assert "manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS" in source
    assert "manufacturing_api.normalize_operator_source_dimension(" in source
    assert source.index("normalize_operator_source_dimension(") < source.index(
        "self._apply_fold_designer_live_settings("
    )
    assert source.index("normalize_operator_source_dimension(") < source.index(
        "self.multi_door_enabled_var.set("
    )
