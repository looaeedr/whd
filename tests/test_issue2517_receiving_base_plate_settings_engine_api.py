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
    actual = manufacturing_api.validate_receiving_base_plate_settings

    def tracked(**kwargs):
        calls.append(kwargs)
        return actual(**kwargs)

    monkeypatch.setattr(
        manufacturing_api, "validate_receiving_base_plate_settings", tracked,
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
