# -*- coding: utf-8 -*-
"""Switch model names are always derived from the editable CSV at call time."""
import csv
from pathlib import Path

import pytest

from ae_engine.receiving_switch_model_catalog import (
    PROJECT_ROOT, INDEX_PATH, INDEX_RELATIVE_PATH,
    BRANDS, display_model, model_choices, model_filenames,
)
from ae_engine.receiving_nfb_index_sources import unique_nfb_dxfs_from_switch_index
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import edit_setting, setting_value, validate_setting


def test_user_csv_is_single_authority_and_shows_eight_unique_models_per_brand():
    assert INDEX_RELATIVE_PATH.parts == ("基準檔", "開孔", "NFB", "開關索引.csv")
    assert INDEX_PATH == PROJECT_ROOT / INDEX_RELATIVE_PATH
    assert INDEX_PATH.is_file()
    assert not (PROJECT_ROOT / "開關索引.csv").exists()
    assert model_choices("士林") == (
        "BH_25X95", "BH_25X95_02", "100_75X130_68",
        "125_90X155_72", "250_105X165_72", "400_140X257_107",
        "BH_25X95_03", "LEAKAGE_75X130",
    )
    for brand in BRANDS:
        files = model_filenames(brand)
        assert len(files) == len(set(files)) == 8
        assert all(name.lower().endswith(".dxf") for name in files)
        assert all(not label.lower().endswith(".dxf") for label in model_choices(brand))
    assert model_filenames("三菱") == ()
    assert model_filenames("順山") == ()
    assert display_model("Model.DXF") == "Model"
    with pytest.raises(ValueError):
        display_model("Model.txt")


def test_nfb_dxf_source_index_uses_same_relocated_csv():
    catalog = unique_nfb_dxfs_from_switch_index(INDEX_PATH)
    assert catalog.index_path == "開關索引.csv"
    assert catalog.records_read == 42
    assert len(catalog.sources) == 24
    assert not catalog.diagnostics


def test_model_catalog_path_not_dependent_on_working_directory(monkeypatch, tmp_path):
    before = model_choices("士林")
    monkeypatch.chdir(tmp_path)
    assert model_choices("士林") == before
    assert INDEX_PATH.is_relative_to(PROJECT_ROOT)
    assert INDEX_PATH.relative_to(PROJECT_ROOT) == INDEX_RELATIVE_PATH


def test_editing_same_csv_refreshes_list_without_import_or_restart(tmp_path):
    source = tmp_path / "開關索引.csv"
    header = "圖塊名稱,士林,深,東元,深,伍菱,深\n"
    source.write_text(
        header +
        "a,SAME.dxf,50,無對應檔案,,WL.dxf,60\n" +
        "b,SAME.dxf,50,無對應檔案,,WL.dxf,60\n", encoding="utf-8-sig",
    )
    assert model_choices("士林", path=source) == ("SAME",)
    source.write_text(
        header + "a,CHANGE.DXF,50,無對應檔案,,WL.dxf,60\n",
        encoding="utf-8-sig",
    )
    assert model_choices("士林", path=source) == ("CHANGE",)
    assert model_filenames("士林", path=source) == ("CHANGE.DXF",)
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        stream.write("wrong,header\n")
    with pytest.raises(ValueError, match="欄位"):
        model_choices("士林", path=source)


def test_model_assignments_follow_set_bay_and_round_trip_independently():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    layout = edit_setting(
        layout, set_index=0, bay_index=0, kind="inner_door_models",
        value=["BH_25X95.dxf", ""],
    )
    layout = edit_setting(
        layout, set_index=0, bay_index=1, kind="inner_door_models",
        value=["100_75X130_68.dxf", "BH_25X95_03.dxf"],
    )
    row = layout["sets"][0]
    assert setting_value(row, 0, "inner_door_models") == ["BH_25X95.dxf", ""]
    assert setting_value(row, 1, "inner_door_models") == [
        "100_75X130_68.dxf", "BH_25X95_03.dxf",
    ]
    assert setting_value(row, 0, "inner_door_layers") == 1
    with pytest.raises(ValueError):
        validate_setting("inner_door_models", ["../other.dxf", ""])
    with pytest.raises(ValueError):
        validate_setting("inner_door_models", ["one.dxf"])
