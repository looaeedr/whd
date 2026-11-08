"""#2517: Fold Designer Editor may only publish Engine-validated Settings source."""
from copy import deepcopy
from dataclasses import fields
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_composition_shell_settings as shell
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator, Phase6SettingsApplicationPorts,
)
from phase6_settings_transitions import normalize_updates


class Var:
    def __init__(self):
        self.writes = []

    def set(self, value):
        self.writes.append(value)


class Transactions:
    def __init__(self, family):
        self.settings = {
            "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
            "fw": 25.0, "yl1": 15.0, "flag": True,
        }
        self.source = {"model": family, **deepcopy(self.settings)}
        self.box = {"w": 800.0, "h": 1600.0, "d": 350.0}
        self.events = []

    def normalize_updates(self, incoming):
        self.events.append(("normalize", deepcopy(incoming)))
        return normalize_updates(self.settings, incoming)

    def commit_settings(self, accepted):
        self.events.append(("commit", deepcopy(accepted)))
        result = api.commit_operator_settings_state(
            self.settings, self.source, self.box, accepted
        )
        self.settings.clear()
        self.settings.update(result.settings_values)
        self.source.clear()
        self.source.update(result.input_snapshot)
        self.box.clear()
        self.box.update(result.box_whd)
        return dict(result.committed)

    def commit_editor_fw_takeover(self, value):
        self.events.append(("takeover", value))


def _environment(family="受電箱"):
    tx = Transactions(family)
    effects = []
    app = SimpleNamespace(
        _phase6_input_snapshot=tx.source,
        _phase6_settings_guard=False,
        left_global_vars={}, setting_vars={},
        v_w=Var(), v_h=Var(), v_d=Var(),
    )
    required = {
        "_setting_number_text": str,
        "original": SimpleNamespace(tk=SimpleNamespace(BooleanVar=Var)),
    }
    composer = SimpleNamespace(
        app=app, _required=lambda _namespace, name: required[name],
    )

    def project_ui_values(values, **kwargs):
        effects.append(("ui", deepcopy(values), deepcopy(kwargs)))
        # Execute the production UI projection: it writes editor_snapshot to
        # the saved manufacturing source, so this is not a mock state update.
        return shell.settings_application_project_ui_values(
            composer, None, values, **kwargs
        )

    def apply_profile_plan(values, **kwargs):
        effects.append(("profile", deepcopy(values), deepcopy(kwargs)))

    def publish_live_state(values, **kwargs):
        effects.append(("publish", deepcopy(values), deepcopy(kwargs)))

    def no_effect(name):
        return lambda *args, **kwargs: effects.append((name, args, kwargs))

    ports = {
        f.name: no_effect(f.name) for f in fields(Phase6SettingsApplicationPorts)
    }
    ports.update({
        "read_settings_snapshot": lambda: SimpleNamespace(
            settings_values=deepcopy(tx.settings),
            input_snapshot=deepcopy(tx.source),
            box_whd=deepcopy(tx.box),
        ),
        "project_ui_values": project_ui_values,
        "apply_profile_plan": apply_profile_plan,
        "publish_live_state": publish_live_state,
    })
    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=tx,
        ports=Phase6SettingsApplicationPorts(**ports),
    )
    return coordinator, tx, effects, app


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_valid_editor_values_match_engine_and_save_reload_fold(family):
    owner, tx, effects, app = _environment(family)
    raw = {
        "w": "800.125", "h": "1600.375", "d": "350.625",
        "fw": "29.125", "flag": "false", "yl1": "17.25",
    }
    expected = normalize_updates(tx.settings, raw)
    changed = owner.commit_editor_values(raw, notify=True)
    assert changed == expected
    assert tx.settings["flag"] is tx.source["flag"] is False
    assert tx.events[0] == ("normalize", raw)
    assert ("commit", expected) in tx.events
    assert ("takeover", expected["fw"]) in tx.events
    assert next(row for row in effects if row[0] == "ui")[2]["editor_snapshot"] == expected
    assert next(row for row in effects if row[0] == "profile")[1] == expected
    assert next(row for row in effects if row[0] == "publish")[1] == expected
    for key in expected:
        assert tx.settings[key] == tx.source[key] == expected[key]
    for axis in ("w", "h", "d"):
        assert tx.box[axis] == expected[axis]
    restored = json.loads(json.dumps(tx.source))
    assert restored == tx.source
    for part in ("head", "tail"):
        assert (api.build_endcap_xy_fold_profiles(restored, part_key=part) ==
                api.build_endcap_xy_fold_profiles(tx.source, part_key=part))


@pytest.mark.parametrize("bad", ("nan", "inf", "-inf", "", "not-a-number", True))
def test_unaccepted_editor_only_batch_cannot_enter_saved_source_or_refresh(bad):
    owner, tx, effects, app = _environment()
    before = deepcopy((tx.settings, tx.source, tx.box))
    assert owner.commit_editor_values({
        "fw": bad, "yl1": "nan", "ghost": "non-finite",
    }) == {}
    assert (tx.settings, tx.source, tx.box) == before
    assert not any(event[0] in ("commit", "takeover") for event in tx.events)
    assert effects == []


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_mixed_accepted_and_rejected_inputs_only_project_engine_result(family):
    owner, tx, effects, app = _environment(family)
    before_fw = tx.source["fw"]
    raw = {
        "w": "810.25", "flag": "false", "fw": "nan",
        "yl1": "inf", "unknown_control": "garbage",
    }
    expected = normalize_updates(tx.settings, raw)
    assert expected == {"w": 810.25, "flag": False}
    assert owner.commit_editor_values(raw) == expected
    assert tx.source["fw"] == tx.settings["fw"] == before_fw
    assert tx.source["yl1"] == tx.settings["yl1"] == 15.0
    assert "unknown_control" not in tx.source
    ui = next(row for row in effects if row[0] == "ui")
    profile = next(row for row in effects if row[0] == "profile")
    assert ui[2]["editor_snapshot"] == profile[1] == expected
    assert "nan" not in repr(tx.source).lower()
    assert tx.box["w"] == 810.25


@pytest.mark.parametrize("bad", (0, True, "nan", "-4", float("inf")))
def test_invalid_physical_dimension_aborts_before_partial_gui_write(bad):
    owner, tx, effects, app = _environment()
    before = deepcopy((tx.settings, tx.source, tx.box))
    with pytest.raises(ValueError, match="包外尺寸"):
        owner.commit_editor_values({"flag": "false", "w": bad})
    assert (tx.settings, tx.source, tx.box) == before
    assert not any(item[0] == "commit" for item in tx.events)
    assert effects == []


@pytest.mark.parametrize("bad", ("maybe", "2", None, 2, 1.5))
def test_invalid_persisted_editor_bool_never_becomes_true(bad):
    owner, tx, effects, app = _environment()
    before = deepcopy((tx.settings, tx.source, tx.box))
    with pytest.raises(ValueError, match="布林值"):
        owner.commit_editor_values({"w": "810", "flag": bad})
    assert (tx.settings, tx.source, tx.box) == before
    assert effects == []


def test_gui_editor_coordinator_has_no_raw_source_escape():
    source = inspect.getsource(
        Phase6FoldDesignerSettingsCoordinator.commit_editor_values
    )
    assert "self._transactions.normalize_updates(raw)" in source
    assert "editor_snapshot=clean" in source
    assert "self._ports.apply_profile_plan(\n            clean," in source
    assert "clean[key] = value" not in source
