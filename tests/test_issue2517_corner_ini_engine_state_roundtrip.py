"""#2517: Corner INI storage must consume Engine type/bool/numeric authority."""
from __future__ import annotations

import configparser
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import corner_state_transactions as owner
from ae_engine.sheetmetal_geometry import CornerDirection, CornerTypeId
from phase6_settings_center import (
    CORNER_KEYS, load_corner_defaults_from_ini, save_corner_defaults_to_ini,
)


def _host(tmp_path):
    return SimpleNamespace(
        INI_PATH=tmp_path / "corner.ini", config=configparser.ConfigParser(),
    )


def test_saved_false_pair_and_legacy_c02_rotation_roundtrip_in_same_ini(tmp_path):
    host = _host(tmp_path)
    corners = {"head": {
        "top_left": {"type_id": "C02", "rotation_quadrants": 5},
        "bottom_left": {"type_id": "CROSS", "cross_mode": "extra_cut",
                        "direction": "both", "amount_t": "1.25"},
    }}
    pairs = {"head": {"top": "false", "bottom": "on"}}
    original = deepcopy((corners, pairs))
    save_corner_defaults_to_ini(host, corners, pairs, context="head")
    parser = configparser.ConfigParser()
    parser.read(host.INI_PATH, encoding="utf-8")
    assert parser.getboolean("CORNER_HEAD", "top_same") is False
    assert parser.getboolean("CORNER_HEAD", "bottom_same") is True
    assert parser.get("CORNER_HEAD", "top_left") == "C02"
    assert parser.getint("CORNER_HEAD", "top_left_rotation") == 1
    assert parser.getfloat("CORNER_HEAD", "bottom_left_amount_t") == 1.25
    after_corners, after_pairs = load_corner_defaults_from_ini(host)
    assert after_pairs["head"] == {"top": False, "bottom": True}
    assert after_corners["head"]["top_left"]["type_id"] == "C02"
    assert after_corners["head"]["top_left"]["rotation_quadrants"] == 1
    assert after_corners["head"]["bottom_left"]["amount_t"] == 1.25
    derived = api.endcap_corner_selection_from_raw(after_corners["head"]["top_left"])
    assert derived.type_id is CornerTypeId.CROSS
    assert derived.direction is CornerDirection.HEIGHT
    assert (corners, pairs) == original


@pytest.mark.parametrize("kind,value,expected", [
    ("C02", 5, 1), ("c02", -1, 3), ("C02", "2", 2),
    ("C01", "invalid but irrelevant", 0), ("CROSS", True, 0),
])
def test_engine_is_only_legacy_quadrant_owner(kind, value, expected):
    assert api.project_operator_corner_ini_rotation(kind, value) == expected


@pytest.mark.parametrize("value", [True, False, "nan", "inf", "-inf", "1.5", object()])
def test_invalid_legacy_c02_rotation_fails_before_ini_write(tmp_path, value):
    host = _host(tmp_path)
    corners = {"head": {"top_left": {"type_id": "C02",
                                    "rotation_quadrants": value}}}
    with pytest.raises((ValueError, TypeError)):
        save_corner_defaults_to_ini(host, corners, {"head": {}}, context="head")
    assert not host.INI_PATH.exists()


@pytest.mark.parametrize("invalid", ["nan", "-inf", float("inf"), float("nan"), True])
def test_invalid_saved_corner_numeric_never_enters_ini(tmp_path, invalid):
    host = _host(tmp_path)
    corners = {"head": {"bottom_left": {
        "type_id": "CROSS", "cross_mode": "extra_cut", "amount_t": invalid,
    }}}
    with pytest.raises(ValueError, match="有限數值"):
        save_corner_defaults_to_ini(host, corners, {"head": {}}, context="head")
    assert not host.INI_PATH.exists()


@pytest.mark.parametrize("invalid", ["maybe", None, "2", 2, -1, float("nan")])
def test_invalid_pair_flag_never_silently_becomes_true(tmp_path, invalid):
    host = _host(tmp_path)
    with pytest.raises(ValueError, match="布林值"):
        save_corner_defaults_to_ini(
            host, {"head": {}}, {"head": {"top": invalid}}, context="head",
        )
    assert not host.INI_PATH.exists()


def test_bad_numeric_ini_source_is_skipped_but_legacy_corner_stays(tmp_path):
    host = _host(tmp_path)
    host.config.add_section("CORNER_HEAD")
    host.config.set("CORNER_HEAD", "top_left", "C02")
    host.config.set("CORNER_HEAD", "top_left_rotation", "5")
    host.config.set("CORNER_HEAD", "top_left_amount_t", "nan")
    host.config.set("CORNER_HEAD", "top_left_secondary_depth_t", "inf")
    corners, pairs = load_corner_defaults_from_ini(host)
    assert corners["head"]["top_left"]["type_id"] == "C02"
    assert corners["head"]["top_left"]["rotation_quadrants"] == 1
    assert "amount_t" not in corners["head"]["top_left"]
    assert "secondary_depth_t" not in corners["head"]["top_left"]
    assert pairs["head"] == {"top": True, "bottom": True}


def test_non_c02_rotation_is_zero_without_new_geometry_semantics(tmp_path):
    host = _host(tmp_path)
    save_corner_defaults_to_ini(host, {
        "head": {"top_left": {"type_id": "INSERT", "rotation_quadrants": 3}}
    }, {"head": {"top": True}}, context="head")
    corners, _ = load_corner_defaults_from_ini(host)
    assert corners["head"]["top_left"]["rotation_quadrants"] == 0


def test_gui_ini_transport_delegates_physical_semantics_to_public_engine():
    import phase6_settings_center as gui
    assert api.project_operator_corner_ini_rotation is owner.project_operator_corner_ini_rotation
    assert CORNER_KEYS is api.MANUAL_CORNER_KEYS
    save_code = inspect.getsource(gui.save_corner_defaults_to_ini)
    read_code = inspect.getsource(gui.load_corner_defaults_from_ini)
    assert api.project_operator_corner_ini_save_options is owner.project_operator_corner_ini_save_options
    assert api.project_operator_corner_ini_load_section is owner.project_operator_corner_ini_load_section
    assert "manufacturing_api.project_operator_corner_ini_save_options(" in save_code
    assert "manufacturing_api.project_operator_corner_ini_load_section(" in read_code
    # Rotation, pairing, and finite manufacturing values must be handled by
    # the Engine section codec, never reinterpreted by the GUI file adapter.
    for code in (save_code, read_code):
        assert "manufacturing_api.project_operator_corner_ini_rotation(" not in code
        assert "manufacturing_api.normalize_operator_settings_updates(" not in code
        assert "manufacturing_api.normalize_operator_settings_boolean(" not in code
    assert "project_operator_corner_ini_rotation(" in inspect.getsource(
        owner.project_operator_corner_ini_load_section
    )
    assert "project_operator_corner_ini_rotation(" in inspect.getsource(
        owner.project_operator_corner_ini_save_options
    )
    assert "bool(pairs.get(" not in save_code
    assert "float(value)" not in save_code
    assert "from phase6_" not in inspect.getsource(owner)
