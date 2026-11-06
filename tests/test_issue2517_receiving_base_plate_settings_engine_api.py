# -*- coding: utf-8 -*-
"""#2517: physical Receiving Base Plate Settings preflight is Engine-owned."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import receiving_base_plate_settings_transaction as gui


CENTER = {
    "pattern": "CENTER", "height": 280.0, "shrink_top": 20.0,
    "shrink_bottom": 20.0, "shrink_left": 85.0,
    "shrink_right": 85.0, "bend": 20.0,
}
# The actual three-pattern constants are supplied by the canonical builder.
from ae_engine.sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERN_LEFT,
)
CENTER["pattern"] = RECEIVING_BASE_PATTERN_CENTER


def _snapshot():
    return {"model": "受電箱", "w": 800.0, "t": 2.0, "h": 1600.0}


def test_headless_valid_source_is_detached_and_input_never_changes():
    source, config = _snapshot(), deepcopy(CENTER)
    frozen = deepcopy((source, config))
    result = manufacturing_api.validate_receiving_base_plate_settings(
        input_snapshot=source, settings_values={}, config=config,
    )
    assert result == config and result is not config
    assert (source, config) == frozen
    result["height"] = 1.0
    assert config["height"] == 280.0


def test_source_wrong_ear_pitch_cannot_relabel_center_as_flat():
    source, config = _snapshot(), deepcopy(CENTER)
    config["pattern"] = RECEIVING_BASE_PATTERN_LEFT
    frozen = deepcopy((source, config))
    with pytest.raises(ValueError):
        manufacturing_api.validate_receiving_base_plate_settings(
            input_snapshot=source, settings_values={}, config=config,
        )
    assert (source, config) == frozen


@pytest.mark.parametrize("kind", ["bad-model", "no-snapshot", "bad-config"])
def test_invalid_source_fails_before_commit(kind):
    source, config = _snapshot(), deepcopy(CENTER)
    if kind == "bad-model":
        source["model"] = "金庫型"
    elif kind == "no-snapshot":
        source = None
    else:
        config = ["not", "a", "mapping"]
    with pytest.raises(ValueError):
        manufacturing_api.validate_receiving_base_plate_settings(
            input_snapshot=source, settings_values={}, config=config,
        )


def test_explicit_reset_does_not_fabricate_plate():
    source = _snapshot()
    assert manufacturing_api.validate_receiving_base_plate_settings(
        input_snapshot=source, settings_values={}, config=None,
    ) is None
    assert "receiving_base_plate" not in source


def test_gui_commits_only_detached_engine_selection(monkeypatch):
    source = _snapshot()
    count = []
    calls = []
    actual = manufacturing_api.commit_operator_receiving_base_plate_settings

    def tracked(**kwargs):
        calls.append(kwargs)
        return actual(**kwargs)

    monkeypatch.setattr(
        manufacturing_api, "commit_operator_receiving_base_plate_settings", tracked,
    )
    result = gui.commit_receiving_base_plate_settings(
        input_snapshot=source, settings_values={},
        submit_geometry_update=lambda: count.append(1), config=CENTER,
    )
    assert result == CENTER
    assert source["receiving_base_plate"] == CENTER
    assert len(calls) == 1 and count == [1]


def test_gui_rolls_back_commit_after_callback_error():
    source = _snapshot()
    source["receiving_base_plate"] = deepcopy(CENTER)
    replacement = deepcopy(CENTER)
    replacement["height"] = 300.0

    def failed_update():
        raise RuntimeError("view update unavailable")

    with pytest.raises(RuntimeError, match="view update"):
        gui.commit_receiving_base_plate_settings(
            input_snapshot=source, settings_values={},
            submit_geometry_update=failed_update, config=None,
        )
    assert source["receiving_base_plate"] == CENTER


def test_headless_public_transaction_matches_gui_for_apply_and_reset():
    assert (manufacturing_api.commit_operator_receiving_base_plate_settings
            is __import__("ae_engine", fromlist=["commit_operator_receiving_base_plate_settings"])
            .commit_operator_receiving_base_plate_settings)
    for action in (manufacturing_api.commit_operator_receiving_base_plate_settings,
                   gui.commit_receiving_base_plate_settings):
        source = _snapshot()
        notifications = []
        result = action(
            input_snapshot=source, settings_values={}, config=CENTER,
            submit_geometry_update=lambda: notifications.append(
                deepcopy(source["receiving_base_plate"])),
        )
        assert result == CENTER and result is not source["receiving_base_plate"]
        assert notifications == [CENTER]
        result["height"] = 5.0
        assert source["receiving_base_plate"]["height"] == CENTER["height"]
        reset = action(
            input_snapshot=source, settings_values={}, config=None,
            submit_geometry_update=lambda: notifications.append("reset"),
        )
        assert reset is None
        assert "receiving_base_plate" not in source
        assert notifications[-1] == "reset"


@pytest.mark.parametrize("failure", ("invalid-config", "invalid-model", "invalid-callback"))
def test_engine_transaction_rejects_bad_input_without_touching_source(failure):
    source = _snapshot()
    original_plate = deepcopy(CENTER)
    source["receiving_base_plate"] = original_plate
    callback_calls = []
    config, notify = CENTER, lambda: callback_calls.append("called")
    if failure == "invalid-config":
        config = {**CENTER, "pattern": RECEIVING_BASE_PATTERN_LEFT}
    elif failure == "invalid-model":
        source["model"] = "金庫型"
    else:
        notify = "not callable"
    previous = deepcopy(source)
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.commit_operator_receiving_base_plate_settings(
            input_snapshot=source, settings_values={}, config=config,
            submit_geometry_update=notify,
        )
    assert source == previous and source["receiving_base_plate"] is original_plate
    assert callback_calls == []


def test_engine_rollback_keeps_existing_plate_identity_and_missing_key_absent():
    source = _snapshot()
    previous_plate = deepcopy(CENTER)
    source["receiving_base_plate"] = previous_plate

    def failed_update():
        assert "receiving_base_plate" not in source
        raise RuntimeError("geometry update failed")

    with pytest.raises(RuntimeError, match="geometry update"):
        manufacturing_api.commit_operator_receiving_base_plate_settings(
            input_snapshot=source, settings_values={}, config=None,
            submit_geometry_update=failed_update,
        )
    assert source["receiving_base_plate"] is previous_plate
    pristine = _snapshot()

    def fail_new():
        assert pristine["receiving_base_plate"] == CENTER
        raise RuntimeError("geometry update failed")

    with pytest.raises(RuntimeError, match="geometry update"):
        manufacturing_api.commit_operator_receiving_base_plate_settings(
            input_snapshot=pristine, settings_values={}, config=CENTER,
            submit_geometry_update=fail_new,
        )
    assert "receiving_base_plate" not in pristine


def test_gui_base_plate_entry_does_not_mutate_manufacturing_selection():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/receiving_base_plate_settings_transaction.py")
    text = source.read_text(encoding="utf-8")
    assert "manufacturing_api.commit_operator_receiving_base_plate_settings" in text
    assert 'input_snapshot["receiving_base_plate"] =' not in text
    assert 'input_snapshot.pop("receiving_base_plate"' not in text
    assert "validate_receiving_base_plate_settings(" not in text
