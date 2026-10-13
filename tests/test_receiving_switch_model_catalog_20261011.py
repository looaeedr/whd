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


def _pad_two_brand_draft(second_brand="東元", second_model="140X260_103.dxf"):
    from ae_engine.receiving_nfb_ui1a import (
        new_nfb_ui1a_draft, add_nfb_draft_slot, set_nfb_slot_brand, OVERRIDE,
    )
    state = new_nfb_ui1a_draft(set_brand="士林", layer_count=1)
    state = add_nfb_draft_slot(
        state, 0, filename="400_140X257_107.dxf", source_brand="士林"
    )
    state = add_nfb_draft_slot(
        state, 0, filename=second_model, source_brand=second_brand
    )
    return set_nfb_slot_brand(state, 0, 1, mode=OVERRIDE, value=second_brand)


def test_pad_two_400_models_uses_brand_specific_csv_depth_not_filename_guess():
    from ae_engine.receiving_switch_model_catalog import model_depth_mm
    from ae_engine.receiving_nfb_pad_depth_policy import (
        preview_nfb_pad_depth, DIFFERENT_DEPTH,
    )
    from ae_engine.receiving_nfb_ui1a import nfb_ui1a_preview
    assert model_depth_mm("士林", "400_140X257_107.dxf") == 107
    assert model_depth_mm("東元", "140X260_103.dxf") == 103
    assert model_depth_mm("伍菱", "NF400_140X257_107.dxf") == 107
    # An actual 2P400 東元 '400_Type' entry has no depth, despite other
    # 東元 400-model rows having 103. Never backfill from a filename/sibling.
    assert model_depth_mm("東元", "400_Type.dxf") is None
    draft = _pad_two_brand_draft()
    pad = preview_nfb_pad_depth(draft)
    assert pad.status == DIFFERENT_DEPTH
    assert pad.layer_count == 1 and pad.unit_count == 2
    assert pad.depth_mm == (107.0, 103.0)
    assert pad.candidate_delta_mm == 4.0
    assert pad.shallower_unit_index == 1
    assert pad.deeper_unit_index == 0
    assert pad.required_pad_count == 0  # not yet manufactured
    assert pad.manufacturing_ready is False
    preview = nfb_ui1a_preview(draft, bay_width_mm=800, upper_cell_height_mm=1100)
    assert preview["pad_depth_preview"]["status"] == DIFFERENT_DEPTH
    assert preview["pad_depth_preview"]["candidate_delta_mm"] == 4
    assert not preview["can_manufacture"]


def test_pad_not_applicable_for_other_layer_or_unit_counts_or_equal_depth():
    from ae_engine.receiving_nfb_ui1a import (
        new_nfb_ui1a_draft, add_nfb_draft_slot, set_nfb_draft_layer_count,
    )
    from ae_engine.receiving_nfb_pad_depth_policy import (
        preview_nfb_pad_depth, NOT_APPLICABLE, NO_PAD_NEEDED,
    )
    draft = _pad_two_brand_draft()
    two_layers = set_nfb_draft_layer_count(draft, 2)
    assert preview_nfb_pad_depth(two_layers).status == NOT_APPLICABLE
    # One or three NFBs are never eligible, regardless of brand/depth.
    single = new_nfb_ui1a_draft(set_brand="士林", layer_count=1)
    single = add_nfb_draft_slot(single, 0, filename="400_140X257_107.dxf")
    assert preview_nfb_pad_depth(single).status == NOT_APPLICABLE
    triple = add_nfb_draft_slot(draft, 0, filename="400_140X257_107.dxf")
    assert preview_nfb_pad_depth(triple).status == NOT_APPLICABLE
    # Different brands are not sufficient: 士林107 and 伍菱107 need no pad.
    same = _pad_two_brand_draft("伍菱", "NF400_140X257_107.dxf")
    pad = preview_nfb_pad_depth(same)
    assert pad.status == NO_PAD_NEEDED
    assert pad.candidate_delta_mm == 0
    assert not pad.candidate and pad.required_pad_count == 0


def test_pad_unknown_when_depth_or_brand_provenance_missing():
    from ae_engine.receiving_nfb_pad_depth_policy import (
        preview_nfb_pad_depth, NEEDS_SOURCE,
    )
    unknown = preview_nfb_pad_depth(_pad_two_brand_draft("東元","400_Type.dxf"))
    assert unknown.status == NEEDS_SOURCE
    assert unknown.depth_mm == (107.0, None)
    stale = _pad_two_brand_draft()
    stale["layers"][0]["slots"][1]["source_brand"] = "伍菱"
    result = preview_nfb_pad_depth(stale)
    assert result.status == NEEDS_SOURCE
    assert result.candidate_delta_mm is None


def test_pad_depth_index_remains_editable_and_rejects_conflicting_duplicates(tmp_path):
    from ae_engine.receiving_switch_model_catalog import model_depth_mm
    from ae_engine.receiving_nfb_pad_depth_policy import preview_nfb_pad_depth
    path = tmp_path / "開關索引.csv"
    header = "圖塊名稱,士林,深,東元,深,伍菱,深\n"
    path.write_text(
        header + "3P400SN,400_140X257_107.dxf,107,140X260_103.dxf,103,NF400_140X257_107.dxf,107\n",
        encoding="utf-8-sig",
    )
    assert model_depth_mm("東元","140X260_103.dxf",path=path) == 103
    path.write_text(
        header + "3P400SN,400_140X257_107.dxf,107,140X260_103.dxf,105,NF400_140X257_107.dxf,107\n",
        encoding="utf-8-sig",
    )
    assert model_depth_mm("東元","140X260_103.dxf",path=path) == 105
    result = preview_nfb_pad_depth(_pad_two_brand_draft(), index_path=path)
    assert result.candidate_delta_mm == 2
    path.write_text(
        header + "2P400,400_140X257_107.dxf,107,140X260_103.dxf,103,NF400_140X257_107.dxf,107\n"
        + "3P400SN,400_140X257_107.dxf,107,140X260_103.dxf,105,NF400_140X257_107.dxf,107\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(ValueError, match="重複深度不一致"):
        preview_nfb_pad_depth(_pad_two_brand_draft(), index_path=path)
