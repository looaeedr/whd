# -*- coding: utf-8 -*-
"""#2517 Receiving inner-door NFB editor work area is an Engine projection."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_shared_settings import (
    SETTING_DEFAULTS, validate_setting,
)


def _snapshot():
    return {
        "model": "受電箱", "h": 1600.0,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "multi_door_enabled": True,
    }


def test_engine_reuses_single_upper_door_cell_for_validator_and_preview():
    snapshot = _snapshot()
    original = deepcopy(snapshot)
    assert api.project_receiving_nfb_work_area_height_mm(snapshot) == 1100.0
    assert api.validate_receiving_nfb_layer_heights_for_work_area(
        snapshot, [330.0, 830.0], layer_count=2,
    ) == [330.0, 830.0]
    assert api.validate_receiving_nfb_layer_heights_for_work_area(
        snapshot, [550.0, 830.0], layer_count=1,
    ) == [550.0, 830.0]
    assert snapshot == original


def test_fallback_to_source_h_when_there_is_no_unique_upper_door_cell():
    source = {"h": 1600.0}
    assert api.project_receiving_nfb_work_area_height_mm(source) == 1600.0
    split = {"h": 1600.0, "door_layout_columns": [
        [400.0, [1100.0, 500.0]], [400.0, [1100.0, 500.0]],
    ]}
    assert api.project_receiving_nfb_work_area_height_mm(split) == 1600.0


@pytest.mark.parametrize("height", [0, -1, True, float("nan"), float("inf"), 10 ** 400])
def test_invalid_unconfigured_work_area_never_authorizes_nominal_y(height):
    with pytest.raises(ValueError, match="內門作業區高度未定"):
        api.project_receiving_nfb_work_area_height_mm({"h": height})


def test_operator_layer_heights_cannot_escape_actual_upper_cell():
    source = _snapshot()
    with pytest.raises(ValueError, match="層高必須在目前內門作業區內"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [330.0, 1100.0], layer_count=2,
        )
    with pytest.raises(ValueError, match="層高必須在目前內門作業區內"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [1100.0, 1300.0], layer_count=1,
        )
    with pytest.raises(ValueError, match="內門層數必須為 1 或 2"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [330.0, 830.0], layer_count=True,
        )
    with pytest.raises(ValueError, match="第一層／第二層高度須為正數"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [float("nan"), 830.0], layer_count=2,
        )


def test_legacy_approved_default_inputs_and_editor_source_remain_unmodified():
    source = _snapshot()
    assert SETTING_DEFAULTS["inner_door_layer_heights_mm"] == [330.0, 830.0]
    assert validate_setting("inner_door_layer_heights_mm", [410.0, 910.0]) == [410.0, 910.0]
    composer = (Path(__file__).resolve().parents[1]
                / "gui_modules/application/fold_designer_composition_receiving.py").read_text(encoding="utf-8")
    inner = composer.split("    def inner_edit(", 1)[1].split(
        "    def current_inner_editor_config(", 1
    )[0]
    assert "manufacturing_api.validate_receiving_nfb_layer_heights_for_work_area(" in inner
    assert "manufacturing_api.project_receiving_nfb_work_area_height_mm(" in inner
    assert "derive_door_layout_cells(" not in inner
    assert "manufacturing_api.normalize_receiving_operator_nfb_layer_heights(" in inner
    assert 'initial["layer_heights_mm"]' in inner
    assert "for v in initial_heights" in inner
    assert 'for v in initial["layer_heights_mm"]' not in inner


@pytest.mark.parametrize("disabled", (False, "false", " FALSE ", "off", "no", "0", 0))
def test_saved_disabled_door_does_not_let_stale_top_cell_cap_nfb_work_area(disabled):
    source = _snapshot()
    source["multi_door_enabled"] = disabled
    before = deepcopy(source)

    # The dormant 1100/500 grid is not an active Door and cannot cap the
    # operator's two-tier draft. Source H=1600 is the existing fallback.
    assert api.project_receiving_nfb_work_area_height_mm(source) == 1600.0
    assert api.validate_receiving_nfb_layer_heights_for_work_area(
        source, [500.0, 1300.0], layer_count=2,
    ) == [500.0, 1300.0]
    assert source == before


@pytest.mark.parametrize("enabled", (True, "true", " TRUE ", "on", "yes", "1", 1))
def test_saved_enabled_door_keeps_original_actual_upper_cell_nfb_work_area(enabled):
    source = _snapshot()
    source["multi_door_enabled"] = enabled
    before = deepcopy(source)
    assert api.project_receiving_nfb_work_area_height_mm(source) == 1100.0
    with pytest.raises(ValueError, match="層高必須在目前內門作業區內"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [500.0, 1300.0], layer_count=2,
        )
    assert source == before


@pytest.mark.parametrize("invalid", (None, "maybe", 2, -1, 0.5, [], {}, float("nan")))
def test_corrupt_present_door_mode_cannot_silently_authorize_nfb_draft(invalid):
    source = _snapshot()
    source["multi_door_enabled"] = invalid
    before = repr(source)
    with pytest.raises(ValueError, match="設定的布林值"):
        api.project_receiving_nfb_work_area_height_mm(source)
    with pytest.raises(ValueError, match="設定的布林值"):
        api.validate_receiving_nfb_layer_heights_for_work_area(
            source, [330.0, 830.0], layer_count=2,
        )
    assert repr(source) == before


@pytest.mark.parametrize("columns", (False, "800:1100,500", [[True, [1599.0, 1.0]]],
                                      [[800.0, [False, 1599.0]]], [[800.0, []]]))
def test_enabled_invalid_stored_grid_never_becomes_whole_box_nfb_area(columns):
    source = _snapshot()
    source["door_layout_columns"] = columns
    before = deepcopy(source)
    with pytest.raises((ValueError, TypeError)):
        api.project_receiving_nfb_work_area_height_mm(source)
    assert source == before


def test_missing_legacy_mode_preserves_original_nfb_preview_schematic():
    source = _snapshot()
    source.pop("multi_door_enabled")
    before = deepcopy(source)
    assert api.project_receiving_nfb_work_area_height_mm(source) == 1100.0
    assert source == before


@pytest.mark.parametrize("saved_flag,expected_height", (
    ("false", 1600.0), ("no", 1600.0), ("true", 1100.0), ("yes", 1100.0),
))
def test_real_p6fold_reload_nfb_workarea_matches_saved_public_door_source(
    tmp_path, saved_flag, expected_height,
):
    import phase6_project_file as project

    source = {**_snapshot(), "w": 800.0, "d": 350.0, "t": 2.0, "fw": 29.0}
    source["multi_door_enabled"] = saved_flag
    before = deepcopy(source)
    target = project.write_project(
        tmp_path / ("receiving-nfb-workarea-" + saved_flag + ".p6fold"),
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    restored = project.read_project(target)["snapshot"]
    assert restored["multi_door_enabled"] == saved_flag
    original_restored = deepcopy(restored)
    assert api.project_receiving_nfb_work_area_height_mm(restored) == expected_height
    if expected_height == 1100.0:
        with pytest.raises(ValueError, match="層高必須在目前內門作業區內"):
            api.validate_receiving_nfb_layer_heights_for_work_area(
                restored, [500.0, 1300.0], layer_count=2,
            )
    else:
        assert api.validate_receiving_nfb_layer_heights_for_work_area(
            restored, [500.0, 1300.0], layer_count=2,
        ) == [500.0, 1300.0]
    assert restored == original_restored
    assert source == before
