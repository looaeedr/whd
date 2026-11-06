"""#2517: GUI Corner INI filesystem adapter uses the same public Engine codec."""
from copy import deepcopy
import configparser
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.corner_state_transactions import (
    project_operator_corner_ini_load_section as original_load,
    project_operator_corner_ini_save_options as original_save,
)
from phase6_settings_center import (
    load_corner_defaults_from_ini,
    save_corner_defaults_to_ini,
)


def _source(tmp_path):
    return SimpleNamespace(
        INI_PATH=tmp_path / "corner.ini",
        config=configparser.ConfigParser(),
    )


def test_public_engine_api_uses_original_corner_source_owner():
    assert manufacturing_api.project_operator_corner_ini_load_section is original_load
    assert manufacturing_api.project_operator_corner_ini_save_options is original_save
    assert ae_engine.project_operator_corner_ini_load_section is original_load
    assert ae_engine.project_operator_corner_ini_save_options is original_save


def test_engine_load_preserves_legacy_c02_rotation_pairs_and_parameters():
    ini = {
        "top_same": "no", "bottom_same": "on",
        "top_left": " c02 ", "top_left_rotation": "1",
        "top_right": "C01", "top_right_rotation": "2",
        "bottom_left": " cross ", "bottom_left_cross_mode": " EXTRA_CUT ",
        "bottom_left_direction": " WIDTH ",
        "bottom_left_amount_t": "0.5",
        "bottom_left_secondary_retain_t": "0.25",
        "bottom_left_secondary_depth_t": "2",
    }
    prior = deepcopy(ini)
    corners, pairs = manufacturing_api.project_operator_corner_ini_load_section(ini)
    assert pairs == {"top": False, "bottom": True}
    assert corners["top_left"] == {"type_id": "C02", "rotation_quadrants": 1}
    assert corners["top_right"] == {"type_id": "C01", "rotation_quadrants": 0}
    assert corners["bottom_left"] == {
        "type_id": "CROSS", "rotation_quadrants": 0,
        "cross_mode": "extra_cut", "direction": "width",
        "amount_t": 0.5, "secondary_retain_t": 0.25,
        "secondary_depth_t": 2.0,
    }
    assert ini == prior


def test_actual_corner_ini_save_reload_preserves_source_and_noncorner_sections(tmp_path):
    source = _source(tmp_path)
    source.INI_PATH.write_text("[UNRELATED]\\nkeep = original\\n", encoding="utf-8")
    corners = {"head": {
        "top_left": {
            "type_id": "C02", "rotation_quadrants": 1,
            "amount_t": 0.5,
        },
        "bottom_right": {
            "type_id": "CROSS", "cross_mode": "extra_cut",
            "direction": "both", "amount_t": 1.5,
        },
    }}
    pairs = {"head": {"top": False, "bottom": True}}
    original_corners, original_pairs = deepcopy(corners), deepcopy(pairs)
    save_corner_defaults_to_ini(source, corners, pairs, context="head")
    first_bytes = source.INI_PATH.read_bytes()
    states, saved_pairs = load_corner_defaults_from_ini(source)
    assert saved_pairs["head"] == pairs["head"]
    assert states["head"]["top_left"] == {
        "type_id": "C02", "rotation_quadrants": 1, "amount_t": 0.5,
    }
    assert states["head"]["bottom_right"]["type_id"] == "CROSS"
    assert states["head"]["bottom_right"]["amount_t"] == 1.5
    assert corners == original_corners and pairs == original_pairs
    assert "[UNRELATED]" in first_bytes.decode("utf-8")
    assert "keep = original" in first_bytes.decode("utf-8")

    # The existing non-C02 saved rotation is always reset to zero.
    second = manufacturing_api.project_operator_corner_ini_save_options(
        {"top_right": {"type_id": "C01", "rotation_quadrants": 3}},
        {"top": True, "bottom": True},
    )
    assert second["top_right_rotation"] == "0"


def test_invalid_ini_load_fails_closed_without_modifying_file(tmp_path):
    source = _source(tmp_path)
    source.INI_PATH.write_text(
        "[CORNER_HEAD]\\ntop_same = maybe\\ntop_left = C02\\n", encoding="utf-8",
    )
    before = source.INI_PATH.read_bytes()
    with pytest.raises(ValueError):
        load_corner_defaults_from_ini(source)
    assert source.INI_PATH.read_bytes() == before

    source.INI_PATH.write_text(
        "[CORNER_HEAD]\\ntop_left = C02\\ntop_left_rotation = x\\n",
        encoding="utf-8",
    )
    before = source.INI_PATH.read_bytes()
    with pytest.raises(ValueError):
        load_corner_defaults_from_ini(source)
    assert source.INI_PATH.read_bytes() == before


def test_invalid_save_does_not_write_or_mutate_source(tmp_path):
    source = _source(tmp_path)
    source.INI_PATH.write_text("[CORNER_HEAD]\\ntop_left = C01\\n", encoding="utf-8")
    before = source.INI_PATH.read_bytes()
    corners = {"head": {"top_left": {
        "type_id": "CROSS", "amount_t": float("nan"),
    }}}
    with pytest.raises(ValueError, match="有限"):
        save_corner_defaults_to_ini(source, corners, {}, context="head")
    assert source.INI_PATH.read_bytes() == before
    assert corners["head"]["top_left"]["type_id"] == "CROSS"


def test_gui_only_performs_ini_transport_and_delegates_corner_semantics():
    src_load = inspect.getsource(load_corner_defaults_from_ini)
    src_save = inspect.getsource(save_corner_defaults_to_ini)
    assert "manufacturing_api.project_operator_corner_ini_load_section" in src_load
    assert "manufacturing_api.project_operator_corner_ini_save_options" in src_save
    for forbidden in (
        "rotation_quadrants", "project_operator_corner_ini_rotation",
        "normalize_operator_settings_updates", "cross_mode", "secondary_depth_t",
    ):
        assert forbidden not in src_load and forbidden not in src_save
