"""#2517: saved standard-part Fold material must not be repaired into bogus Settings."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.standard_part_fold_readback import read_standard_part_fold_profiles
from phase6_manufacturing_adapter import read_standard_part_profiles as gui_readback


_PART_KEYS = (
    ("door", "door_fold_l", "door_fold_l"),
    ("base_plate", "base_bend_l", "base_plate_bend"),
    ("indicator_box", "ib_fold_l", "indicator_box_fold"),
    ("indicator_door", "id_fold_l", "indicator_door_fold"),
)


def _source():
    return {"model": "金庫型", "w": 800, "h": 1600, "d": 350, "t": 2,
            "door_fold_l": 20, "door_fold_r": 20,
            "door_fold_b": 20, "door_fold_t": 20,
            "base_plate_bend": 20, "indicator_box_fold": 49,
            "indicator_door_fold": 19}


@pytest.mark.parametrize("part,source_key,result_key", _PART_KEYS)
@pytest.mark.parametrize("invalid", [
    None, True, False, "", "bad", "nan", "inf",
    float("nan"), float("inf"), -5, "-3",
])
def test_explicit_invalid_material_fold_cannot_reach_saved_settings(
    part, source_key, result_key, invalid,
):
    snapshot = _source()
    profiles = api.build_standard_part_fold_profiles(snapshot, part)
    keyed = next(seg for seg in profiles["X"] if seg.get("phase6_key") == source_key)
    keyed["len"] = invalid
    prior = deepcopy((snapshot, profiles))
    with pytest.raises(ValueError, match="STANDARD_PART_FOLD_LENGTH_INVALID"):
        api.read_standard_part_fold_profiles(part, profiles, snapshot)
    with pytest.raises(ValueError, match="STANDARD_PART_FOLD_LENGTH_INVALID"):
        gui_readback(part, profiles, snapshot)
    assert (snapshot, profiles) == prior


@pytest.mark.parametrize("part,source_key,result_key", _PART_KEYS)
def test_numeric_zero_and_fractional_material_source_keep_exact_saved_value(
    part, source_key, result_key,
):
    snapshot = _source()
    profiles = api.build_standard_part_fold_profiles(snapshot, part)
    previous = snapshot.copy()
    # Physical BasePlate/Indicator settings are shared by four flanges.
    # Test fractional/zero source while preserving their real equality gate.
    peers = {
        "base_plate": "base_bend_",
        "indicator_box": "ib_fold_",
        "indicator_door": "id_fold_",
    }
    prefix = peers.get(part)
    rows = [
        seg for axis in ("X", "Y") for seg in profiles[axis]
        if (str(seg.get("phase6_key") or "").startswith(prefix) if prefix
            else seg.get("phase6_key") == source_key)
    ]
    assert len(rows) == (1 if part == "door" else 4)
    for seg in rows:
        seg["len"] = "17.25"
    assert api.read_standard_part_fold_profiles(part, profiles, snapshot)[result_key] == pytest.approx(17.25)
    assert gui_readback(part, profiles, snapshot)[result_key] == pytest.approx(17.25)
    for seg in rows:
        seg["len"] = 0
    # A real material-space zero is not the same as explicit None.
    assert api.read_standard_part_fold_profiles(part, profiles, snapshot)[result_key] == 0.0
    assert snapshot == previous


@pytest.mark.parametrize("part,source_key,result_key", _PART_KEYS)
def test_genuinely_absent_fold_row_preserves_prior_saved_value(
    part, source_key, result_key,
):
    snapshot = _source()
    profiles = api.build_standard_part_fold_profiles(snapshot, part)
    profiles["X"] = [
        seg for seg in profiles["X"] if seg.get("phase6_key") != source_key
    ]
    assert api.read_standard_part_fold_profiles(part, profiles, snapshot)[result_key] == snapshot[result_key]


@pytest.mark.parametrize("invalid", [None, True, float("nan"), -1])
def test_invalid_prior_saved_source_cannot_be_fallback_when_fold_row_is_missing(invalid):
    snapshot = _source()
    snapshot["door_fold_l"] = invalid
    profiles = {"X": (), "Y": ()}
    with pytest.raises(ValueError, match="STANDARD_PART_FOLD_LENGTH_INVALID:door_fold_l"):
        gui_readback("door", profiles, snapshot)


def test_receiving_configured_root_base_still_bypasses_generic_fold_serialization():
    from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT

    snapshot = {
        "model": "receiving", "w": 800, "h": 1600, "t": 2,
        "receiving_base_plate": {
            "pattern": RECEIVING_BASE_PATTERN_LEFT, "height": 340,
            "shrink_top": 20, "shrink_bottom": 20, "shrink_left": 45,
            "shrink_right": 45, "bend": 20,
        },
        "base_plate_bend": 29,
    }
    true_source = api.build_standard_part_fold_profiles(snapshot, "base_plate")
    assert api.read_standard_part_fold_profiles(
        "base_plate", true_source, snapshot,
    ) == {}


def test_gui_readback_delegates_to_single_engine_owner_not_local_float_fallback():
    source = inspect.getsource(gui_readback)
    assert "manufacturing_api.read_standard_part_fold_profiles(" in source
    owner = inspect.getsource(read_standard_part_fold_profiles)
    assert "_profile_value(" in owner
    from ae_engine import standard_part_fold_readback as engine
    internal = inspect.getsource(engine._profile_value)
    assert "_finite_material_length(" in internal
    assert 'float(seg.get("len") or 0)' not in internal
