"""#2517 Receiving preview must not convert corrupt real W/H/D to valid-looking mm."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_mode_session import fresh_receiving_mode
from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
from gui_modules.application.receiving_multi_settings_window import (
    default_preview_dimensions as gui_preview,
)


def _snapshot(mode):
    return fresh_receiving_mode(
        mode, {"w": 800.25, "h": 1600.5, "d": 350.75},
    )


@pytest.mark.parametrize("mode", ("quantity", "set_bay"))
def test_real_receiving_active_mode_uses_original_fractional_physical_source(mode):
    snapshot = _snapshot(mode)
    before = deepcopy(snapshot)
    expected = (800.25, 1600.5, 350.75)
    assert api.receiving_default_preview_dimensions(snapshot) == expected
    assert gui_preview(snapshot) == expected
    assert snapshot == before
    # The public W/H/D values themselves remain stable JSON-serializable mm.
    assert tuple(json.loads(json.dumps(expected))) == expected


@pytest.mark.parametrize("mode", ("quantity", "set_bay"))
@pytest.mark.parametrize(("axis", "bad"), [
    ("w", True), ("w", "nan"), ("w", 0),
    ("h", False), ("h", float("inf")), ("h", -1),
    ("d", None), ("d", float("-inf")), ("d", "invalid"),
])
def test_present_invalid_physical_source_never_gets_family_default(mode, axis, bad):
    snapshot = _snapshot(mode)
    if mode == "quantity":
        snapshot["receiving_quantity_box"][axis] = bad
    else:
        physical = {"w": "width", "h": "height", "d": "depth"}[axis]
        snapshot["receiving_layout"]["sets"][0]["bays"][0][physical] = bad
    frozen = deepcopy(snapshot)
    with pytest.raises(ValueError):
        api.receiving_default_preview_dimensions(snapshot)
    with pytest.raises(ValueError):
        gui_preview(snapshot)
    assert snapshot == frozen


@pytest.mark.parametrize("mode", ("quantity", "set_bay"))
def test_explicit_missing_physical_axis_rejected(mode):
    snapshot = _snapshot(mode)
    if mode == "quantity":
        del snapshot["receiving_quantity_box"]["h"]
    else:
        del snapshot["receiving_layout"]["sets"][0]["bays"][0]["height"]
    old = deepcopy(snapshot)
    with pytest.raises(ValueError):
        api.receiving_default_preview_dimensions(snapshot)
    assert snapshot == old


@pytest.mark.parametrize("snapshot", [
    {"active_mode": "quantity", "receiving_quantity_box": {}},
    {"active_mode": "quantity", "receiving_quantity_box": None},
    {"active_mode": "set_bay", "receiving_layout": {}},
    {"active_mode": "set_bay", "receiving_layout": {"sets": []}},
    {"active_mode": "set_bay", "receiving_layout": None},
    {"active_mode": "set_bay", "receiving_layout": {"sets": [{}]}},
    {"active_mode": "set_bay", "receiving_layout": {"sets": [{"bays": [None]}]}},
])
def test_explicit_broken_source_does_not_mint_family_preview_dimensions(snapshot):
    before = deepcopy(snapshot)
    with pytest.raises(ValueError):
        api.receiving_default_preview_dimensions(snapshot)
    assert snapshot == before


def test_only_absent_source_uses_original_receiving_family_schematic():
    defaults = tuple(float(BOX_BODY_DEFAULTS[axis]) for axis in ("w", "h", "d"))
    assert api.receiving_default_preview_dimensions({}) == defaults
    assert api.receiving_default_preview_dimensions(None) == defaults
    assert api.receiving_default_preview_dimensions({"active_mode": "quantity"}) == defaults
    assert gui_preview({"active_mode": "set_bay"}) == defaults


def test_incorrect_snapshot_type_is_not_silently_treated_as_absence():
    for source in (False, True, (), "not a snapshot", 2.0):
        with pytest.raises(ValueError):
            api.receiving_default_preview_dimensions(source)


def test_gui_only_forwards_engine_validated_preview_dimensions():
    src = inspect.getsource(gui_preview)
    assert "manufacturing_api.receiving_default_preview_dimensions(snapshot)" in src
    assert "float(" not in src
    engine = inspect.getsource(api.receiving_default_preview_dimensions)
    assert "normalize_operator_source_dimension(" in engine
    assert "float(box[axis])" not in engine
