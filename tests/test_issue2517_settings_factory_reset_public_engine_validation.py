"""#2517: Factory Settings restoration consumes the same Engine source validator."""
from copy import deepcopy
from dataclasses import fields
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)
from phase6_settings_transitions import normalize_updates


class FakeSettingsTransactions:
    def __init__(self):
        self.settings = {
            "w": 800.0, "h": 1600.0, "d": 350.0,
            "fw": 25.0, "flag": True, "ui_text_size": "small",
            "yl1": 15.0,
        }
        self.source = deepcopy(self.settings)
        self.box = {"w": 800.0, "h": 1600.0, "d": 350.0}
        self.calls = []

    def normalize_updates(self, values):
        self.calls.append(("normalize_updates", deepcopy(values)))
        return normalize_updates(self.settings, values)

    def commit_settings(self, values):
        self.calls.append(("commit_settings", deepcopy(values)))
        tx = api.commit_operator_settings_state(
            self.settings, self.source, self.box, values
        )
        self.settings.clear()
        self.settings.update(tx.settings_values)
        self.source.clear()
        self.source.update(tx.input_snapshot)
        self.box.clear()
        self.box.update(tx.box_whd)
        return dict(tx.committed)

    def mark_workspace_dirty(self):
        self.calls.append(("mark_workspace_dirty",))


def host():
    tx = FakeSettingsTransactions()
    effects = []

    def make_port(name):
        def port(*args, **kwargs):
            effects.append((name, args, kwargs))
            if name == "read_settings_snapshot":
                return SimpleNamespace(settings_values=deepcopy(tx.settings))
            return None
        return port

    ports = Phase6SettingsApplicationPorts(**{
        f.name: make_port(f.name) for f in fields(Phase6SettingsApplicationPorts)
    })
    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=tx, ports=ports
    )
    return coordinator, tx, effects


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_reset_preserves_engine_normalized_bool_and_fractional_whd(family):
    coordinator, tx, effects = host()
    tx.source["model"] = family
    original = {
        "w": "800.125", "h": "1600.375", "d": "350.625",
        "flag": "false", "fw": "29.125",
        "ui_text_size": "大", "yl1": "17.5",
        "unknown": "123",
    }
    expected = normalize_updates(tx.settings, original)
    assert expected["flag"] is False
    assert expected["w"] == 800.125
    assert expected["h"] == 1600.375
    assert expected["d"] == 350.625
    assert expected["ui_text_size"] == "large"
    assert coordinator.reset_factory_settings(original) is True
    assert tx.calls[0] == ("normalize_updates", original)
    assert tx.calls[1] == ("commit_settings", expected)
    assert tx.settings["flag"] is tx.source["flag"] is False
    assert tx.settings["ui_text_size"] == "large"
    for axis in ("w", "h", "d"):
        assert tx.settings[axis] == tx.source[axis] == tx.box[axis] == expected[axis]
    assert "unknown" not in tx.settings
    assert any(name == "apply_profile_plan" for name, _, _ in effects)
    assert any(name == "render_bending" for name, _, _ in effects)
    restored = json.loads(json.dumps({
        "settings": tx.settings, "source": tx.source, "box": tx.box
    }))
    for axis in ("w", "h", "d"):
        assert restored["box"][axis] == restored["source"][axis]
    assert restored["source"]["flag"] is False


@pytest.mark.parametrize("axis", ("w", "h", "d"))
@pytest.mark.parametrize("bad", (True, "nan", "inf", 0, -1, None))
def test_bad_late_physical_factory_default_rejects_without_partial_commit(axis, bad):
    coordinator, tx, effects = host()
    before = deepcopy((tx.settings, tx.source, tx.box))
    defaults = {"flag": "false", "fw": "26", axis: bad}
    assert coordinator.reset_factory_settings(defaults) is False
    assert (tx.settings, tx.source, tx.box) == before
    assert not any(call[0] == "commit_settings" for call in tx.calls)
    assert not any(call[0] == "mark_workspace_dirty" for call in tx.calls)
    assert [name for name, _, _ in effects] == ["project_status"]
    assert "失敗" in effects[0][2]["message"]


@pytest.mark.parametrize("bad", ("maybe", "2", 2, None, 1.5))
def test_invalid_serialized_factory_boolean_is_fail_closed(bad):
    coordinator, tx, effects = host()
    initial = deepcopy((tx.settings, tx.source, tx.box))
    assert coordinator.reset_factory_settings({
        "w": "800.625", "flag": bad,
    }) is False
    assert (tx.settings, tx.source, tx.box) == initial
    assert [call[0] for call in tx.calls] == ["normalize_updates"]
    assert [name for name, _, _ in effects] == ["project_status"]


def test_bad_legacy_nonphysical_numeric_is_skipped_not_manufactured():
    coordinator, tx, effects = host()
    assert coordinator.reset_factory_settings({"yl1": "nan", "flag": "false"})
    assert tx.settings["yl1"] == 15.0
    assert tx.settings["flag"] is False
    assert "yl1" not in tx.calls[1][1]


def test_reset_source_never_coerces_manufacturing_values_in_gui():
    body = inspect.getsource(
        Phase6FoldDesignerSettingsCoordinator.reset_factory_settings
    )
    assert "self._transactions.normalize_updates(factory)" in body
    assert "bool(raw)" not in body
    assert "float(raw)" not in body
    assert "self._transactions.commit_settings(clean)" in body
