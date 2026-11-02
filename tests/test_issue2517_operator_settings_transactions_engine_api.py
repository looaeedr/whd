"""#2517 External operator Settings must not mutate physical source semantics."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from phase6_settings_transitions import commit_settings, normalize_updates


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("FALSE", False), ("0", False), ("off", False),
    ("no", False), ("", False), (False, False), (0, False),
    ("true", True), ("TRUE", True), ("1", True), ("on", True),
    ("yes", True), (True, True), (1, True),
])
def test_external_boolean_sync_matches_engine_serialization(raw, expected):
    saved = {"some_flag": not expected, "w": 800.0, "ui_text_size": "small"}
    actual = normalize_updates(saved, {"some_flag": raw})
    assert actual == {"some_flag": expected}
    assert api.normalize_operator_settings_updates(saved, {"some_flag": raw}) == actual
    assert normalize_updates(
        {**saved, "some_flag": expected}, {"some_flag": raw},
        external_apply_guard=True,
    ) == {}


@pytest.mark.parametrize("raw", ("maybe", "2", 2, -1, 1.5, float("nan"), None))
def test_explicit_bad_boolean_fails_instead_of_becoming_true_or_false(raw):
    with pytest.raises(ValueError, match="布林值"):
        normalize_updates({"enabled": False}, {"enabled": raw})


@pytest.mark.parametrize("key", ("w", "h", "d"))
@pytest.mark.parametrize("bad", (0, -1, True, "not-a-number", "nan", "inf", float("-inf")))
def test_invalid_physical_dimension_rejected_before_state_mutation(key, bad):
    saved = {"w": 800.0, "h": 1600.0, "d": 350.0}
    initial = deepcopy(saved)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_settings_updates(saved, {key: bad})
    with pytest.raises(ValueError, match="包外尺寸"):
        api.commit_operator_settings_state(saved, saved, saved, {key: bad})
    assert saved == initial


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_fractional_finished_dimensions_remain_identical_in_all_save_reload_sources(model):
    source = {"model": model, "w": 800.0, "h": 1600.0, "d": 350.0, "flag": False}
    settings = {"w": 800.0, "h": 1600.0, "d": 350.0, "flag": False}
    box = {"w": 800.0, "h": 1600.0, "d": 350.0}
    original = (deepcopy(source), deepcopy(settings), deepcopy(box))
    incoming = {"w": "800.25", "h": 1600.125, "d": "350.5", "flag": "false"}
    normalized = normalize_updates(settings, incoming)
    assert normalized == {"w": 800.25, "h": 1600.125, "d": 350.5, "flag": False}
    result = commit_settings(settings, source, box, normalized)
    direct = api.commit_operator_settings_state(settings, source, box, normalized)
    assert result == direct
    assert isinstance(result, api.OperatorSettingsCommitTransition)
    for key in ("w", "h", "d"):
        assert result.settings_values[key] == result.input_snapshot[key] == result.box_whd[key] == normalized[key]
    assert (source, settings, box) == original
    reloaded = json.loads(json.dumps({"snapshot": result.input_snapshot, "box_whd": result.box_whd}))
    for key in ("w", "h", "d"):
        assert reloaded["snapshot"][key] == reloaded["box_whd"][key] == normalized[key]


def test_legacy_skip_unknown_nonphysical_and_gui_choice_does_not_enter_engine():
    state = {"w": 800.0, "fw": 25.0, "flag": False, "ui_text_size": "small"}
    updates = {"unknown": 5, "fw": "nan", "ui_text_size": "大", "flag": "false"}
    actual = normalize_updates(state, updates)
    assert actual == {"ui_text_size": "large", "flag": False}
    assert api.normalize_operator_settings_updates(state, updates) == {"flag": False}
    saved = commit_settings(state, state, {"w": 800.0}, actual)
    assert saved.settings_values["ui_text_size"] == "large"
    assert saved.input_snapshot["ui_text_size"] == "large"


def test_gui_kernel_has_no_bool_truthiness_or_physical_ui_rounding():
    text = Path("phase6_settings_transitions.py").read_text(encoding="utf-8")
    assert "manufacturing_api.normalize_operator_settings_updates(" in text
    assert "manufacturing_api.commit_operator_settings_state(" in text
    assert "value = bool(raw)" not in text
    assert "_ui_len(committed[key])" not in text
    engine = Path("ae_engine/operator_settings_transactions.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine
