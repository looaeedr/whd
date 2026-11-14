"""#2517: BasePlate physical shrink source uses one public Engine contract."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace
import tkinter as tk

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
from gui_modules.application import fold_designer_composition_registry_edges as gui


@pytest.mark.parametrize(("raw", "expected"), [
    (0, 0.0), ("0", 0.0), (0.25, 0.25), ("0.25", 0.25),
    (55, 55.0), ("55.125", 55.125),
])
def test_engine_public_base_plate_shrink_accepts_legitimate_values(raw, expected):
    assert api.normalize_operator_base_plate_edge_shrink is owner.normalize_operator_base_plate_edge_shrink
    assert ae_engine.normalize_operator_base_plate_edge_shrink is api.normalize_operator_base_plate_edge_shrink
    assert api.normalize_operator_base_plate_edge_shrink(raw) == expected
    key = "base_plate_shrink_top"
    assert api.normalize_operator_settings_updates({key: 55.0}, {key: raw}) == {key: expected}
    tx = api.commit_operator_settings_state({key: 55.0}, {}, {}, {key: raw})
    # Generic Settings commits deliberately preserve the original value type;
    # the manual edge-shrink operation alone normalizes its physical source.
    assert tx.committed == {key: raw}
    assert tx.settings_values[key] == raw
    assert tx.input_snapshot[key] == raw


@pytest.mark.parametrize("bad", [
    True, False, "NaN", float("inf"), float("-inf"),
    None, -1.0, "-0.25", "invalid", object(),
])
def test_engine_manual_shrink_operation_rejects_invalid_source(bad):
    key = "base_plate_shrink_left"
    settings = {key: 55.0}
    input_snapshot = {key: 40.0}
    box = {"w": 400.0}
    before = deepcopy((settings, input_snapshot, box))
    with pytest.raises(ValueError, match="縮量"):
        api.normalize_operator_base_plate_edge_shrink(bad)
    assert (settings, input_snapshot, box) == before



def test_generic_fold_settings_retain_existing_signed_numeric_compatibility():
    """Manual edge-shrink UI policy must NOT tighten generic Fold/INI sources."""
    key = "base_plate_shrink_left"
    settings = {key: 55.0}
    assert api.normalize_operator_settings_updates(settings, {key: "-3.125"}) == {
        key: -3.125
    }
    assert api.commit_operator_settings_state(
        settings, {}, {}, {key: "-3.125"}
    ).committed[key] == "-3.125"
    for damaged in (True, False, None, "nan", float("inf"), "bad"):
        assert api.normalize_operator_settings_updates(settings, {key: damaged}) == {}


def _run_gui(raw, family="金庫型"):
    emitted = []
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": family},
        _settings_values={"base_plate_shrink_top": 55.0},
        base_plate_edge_shrink_vars={},
    )
    fields = {
        "_BASE_PLATE_EDGE_SETTING_KEYS": {"TOP": "base_plate_shrink_top"},
        "original": SimpleNamespace(tk=tk),
    }
    host = SimpleNamespace(
        app=app,
        _required=lambda _ns, name: fields[name],
        stage_setting_update=lambda ns, key, value: emitted.append(("stage", key, value)),
        flush_pending_settings=lambda ns: emitted.append(("flush",)),
    )
    result = gui.commit_base_plate_edge_shrink(host, {}, "TOP", raw)
    return result, emitted, app


@pytest.mark.parametrize(("raw", "expected"), [
    ("0", 0.0), ("0.25", 0.25), ("55.125", 55.125),
])
def test_vault_gui_stages_only_engine_normalized_shrink(raw, expected):
    done, emitted, app = _run_gui(raw)
    assert done is True
    assert emitted == [("stage", "base_plate_shrink_top", expected), ("flush",)]
    assert app._settings_values == {"base_plate_shrink_top": 55.0}
    assert "float(raw_value)" not in inspect.getsource(gui.commit_base_plate_edge_shrink)


@pytest.mark.parametrize("raw", [True, False, "nan", "inf", "-1", object()])
def test_vault_gui_rejects_bad_shrink_without_staging(raw):
    done, emitted, _app = _run_gui(raw)
    assert done is False
    assert emitted == []


def test_receiving_base_plate_keeps_source_derived_shrink_noneditable():
    for raw in ("50", True, "nan"):
        done, emitted, app = _run_gui(raw, family="受電箱")
        assert done is False
        assert emitted == []
        assert app._settings_values == {"base_plate_shrink_top": 55.0}


def test_saved_shrink_source_reloads_with_identical_gui_engine_outcome():
    payload = json.loads(json.dumps({"base_plate_shrink_top": "0.25"}))
    done, emitted, app = _run_gui(payload["base_plate_shrink_top"])
    tx = api.commit_operator_settings_state(
        app._settings_values, {}, {},
        {"base_plate_shrink_top": payload["base_plate_shrink_top"]},
    )
    assert done is True
    assert tx.committed["base_plate_shrink_top"] == "0.25"
    assert emitted[0] == (
        "stage", "base_plate_shrink_top",
        api.normalize_operator_base_plate_edge_shrink(tx.committed["base_plate_shrink_top"]),
    )
    assert payload["base_plate_shrink_top"] == "0.25"
