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


# V5 numeric catalog is independent of the legacy original-DXF model index.
def test_v5_numeric_model_list_reads_all_supplied_brands_without_dxf_identity():
    from ae_engine.receiving_nfb_numeric_catalog import (
        BRANDS as NUMERIC_BRANDS, model_choices as numeric_choices,
        brand_csv_path, model_spec, NUMERIC_ONLY_UNVERIFIED,
    )
    assert NUMERIC_BRANDS == ("士林", "東元", "伍菱")
    for brand, size in (("士林", 12), ("東元", 9), ("伍菱", 12)):
        assert brand_csv_path(brand).is_file()
        names = numeric_choices(brand)
        assert len(names) == size == len(set(names))
        assert all(not name.lower().endswith(".dxf") for name in names)
        assert all(model_spec(brand, name).status == NUMERIC_ONLY_UNVERIFIED
                   for name in names)
    assert numeric_choices("三菱") == ()
    assert model_spec("士林", "absent") is None


def test_v5_screw_centres_use_opening_centre_and_only_screw_group_offset():
    from ae_engine.receiving_nfb_numeric_catalog import model_spec
    base = model_spec("士林", "2P125SN")
    assert base.opening_mm == (28, 58)
    assert base.screw_pitch_mm == (25, 111)
    assert base.screw_diameter_mm == 3.2
    assert base.opening_corners_xy_mm == (
        (-14, -29), (14, -29), (14, 29), (-14, 29),
    )
    assert base.screw_centers_xy_mm == (
        (-12.5, -55.5), (12.5, -55.5),
        (-12.5, 55.5), (12.5, 55.5),
    )
    offset = model_spec("東元", "3P400SN")
    assert (offset.screw_offset_x_mm, offset.screw_offset_y_mm) == (5, 1)
    assert offset.opening_corners_xy_mm == (
        (-25, -49), (25, -49), (25, 49), (-25, 49),
    )
    assert offset.screw_centers_xy_mm == (
        (-17.5, -106), (27.5, -106),
        (-17.5, 108), (27.5, 108),
    )


def test_v5_missing_numbers_remain_unknown_and_cannot_claim_manufacturability():
    from ae_engine.receiving_nfb_numeric_catalog import read_numeric_specs, model_spec
    all_rows = [spec for brand in ("士林", "東元", "伍菱")
                for spec in read_numeric_specs(brand)]
    assert len(all_rows) == 33
    assert sum(spec.dimensionally_complete for spec in all_rows) == 17
    shihlin = model_spec("士林", "1PBH")
    assert shihlin.opening_mm is None
    assert shihlin.opening_corners_xy_mm is None
    assert shihlin.screw_centers_xy_mm is None
    assert "NFB深_mm" in shihlin.missing_fields
    missing_pitch = model_spec("伍菱", "100HN-s")
    assert missing_pitch.opening_mm == (28, 56)
    assert missing_pitch.screw_pitch_mm is None
    assert missing_pitch.screw_centers_xy_mm is None
    assert all(spec.status.endswith("UNVERIFIED") for spec in all_rows)


def test_v5_csv_is_live_editable_and_rejects_conflicting_models_and_bad_numbers(tmp_path):
    from ae_engine.receiving_nfb_numeric_catalog import (
        HEADER as NUMERIC_HEADER, model_choices as numeric_choices,
        model_spec,
    )
    source = tmp_path / "nfb.csv"
    header = ",".join(NUMERIC_HEADER) + "\n"
    row = "Q100,140,257,107,28X56,25X111,3.4,,\n"
    source.write_text(header + row, encoding="utf-8-sig")
    assert numeric_choices("士林", path=source) == ("Q100",)
    assert model_spec("士林", "Q100", path=source).screw_centers_xy_mm[0] == (-12.5, -55.5)
    source.write_text(header + row + row, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="重複"):
        numeric_choices("士林", path=source)
    for bad in ("25X", "0X111", "-25X111", "25x111", "NaNX111"):
        source.write_text(header + row.replace("25X111", bad), encoding="utf-8-sig")
        with pytest.raises(ValueError):
            numeric_choices("士林", path=source)
    source.write_text(header + row.replace(",3.4,", ",inf,"), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="無效"):
        numeric_choices("士林", path=source)
    source.write_text("bad,header\n" + row, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="欄位"):
        numeric_choices("士林", path=source)


def test_v5_identity_has_explicit_brand_and_survives_set_bay_version_save_reload():
    from ae_engine.receiving_nfb_model_identity import (
        numeric_model_ref, numeric_model_refs, parse_numeric_model_ref,
        display_model_ref, validate_stored_model_ref, selected_numeric_spec,
    )
    from ae_engine.receiving_inner_door_candidates import (
        KEY, create_inner_candidate, inner_config,
    )
    from phase6_quantity_model import normalize_quantity_snapshot
    from ae_engine.receiving_shared_settings import edit_setting, setting_value
    model = numeric_model_ref("士林", "2P125SN")
    assert model == "nfbv5:士林:2P125SN"
    assert display_model_ref(model) == "2P125SN"
    assert parse_numeric_model_ref(model) == ("士林", "2P125SN")
    assert model in numeric_model_refs("士林")
    assert model not in numeric_model_refs("東元")
    assert selected_numeric_spec("士林", model).opening_mm == (28, 58)
    assert selected_numeric_spec("東元", model) is None
    assert validate_stored_model_ref("BH_25X95.dxf") == "BH_25X95.dxf"
    for invalid in ("nfbv5:士林:", "nfbv5:錯誤:X", "nfbv5:士林:../bad",
                    "nfbv5:士林", "random", "../a.dxf"):
        with pytest.raises(ValueError):
            validate_stored_model_ref(invalid)
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    layout = edit_setting(layout, set_index=0, bay_index=1,
                          kind="inner_door_models", value=[[model, model], ""])
    lib, version_id = create_inner_candidate(
        None, {"layers": 1, "models": [[model, model], ""]},
    )
    snapshot = {
        "cabinet_type": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout, KEY: lib,
    }
    saved = normalize_quantity_snapshot(snapshot, for_save=True)
    assert inner_config(saved[KEY], version_id)["models"] == [[model, model], ""]
    assert setting_value(saved["receiving_layout"]["sets"][0], 1, "inner_door_models") == [
        [model, model], "",
    ]
    assert setting_value(saved["receiving_layout"]["sets"][0], 0, "inner_door_models") == [
        "", "",
    ]
    assert saved["receiving_layout"]["sets"][0]["bays"][1].get(
        "nfb_config_submitted"
    ) is not True  # Numeric selection is not a certified manufactured hole.


def test_v5_real_tk_numeric_panel_shows_local_holes_without_reading_dxf(monkeypatch):
    import tkinter as tk
    from tkinter import ttk
    from ae_engine.receiving_nfb_model_identity import numeric_model_ref
    from gui_modules.application.receiving_nfb_source_preview import (
        NfbDxfSourcePreviewPanel,
    )
    root = tk.Tk()
    root.withdraw()
    try:
        host = ttk.Frame(root)
        host.pack(fill="both", expand=True)
        panel = NfbDxfSourcePreviewPanel(host)
        def no_dxf(*_args, **_kwargs):
            raise AssertionError("V5 preview must not read a DXF file")
        monkeypatch.setattr(panel.cache, "load", no_dxf)
        panel.canvas.configure(width=396, height=415)
        root.update_idletasks()
        model = numeric_model_ref("東元", "3P400SN")
        panel.show("東元", model)
        assert panel._numeric_spec.model == "3P400SN"
        assert "未經實體／製造驗證" in panel.reason.get()
        assert panel.viewport.preview is None
        items = panel.canvas.find_withtag("nfb-dxf")
        types = [panel.canvas.type(item) for item in items]
        assert types.count("rectangle") == 1
        assert types.count("oval") == 4
        panel.zoom(1.25)
        assert panel._numeric_zoom == 1.25
        panel.reset()
        assert panel._numeric_zoom == 1
        panel.show("士林", numeric_model_ref("士林", "1PBH"))
        assert panel._numeric_spec.opening_mm is None
        assert panel.canvas.find_withtag("nfb-dxf")
        panel.show("東元", numeric_model_ref("士林", "2P125SN"))
        assert panel._numeric_spec is None
        assert "不符" in panel.reason.get()
    finally:
        root.destroy()


def test_v5_same_source_serves_distinct_inner_middle_and_base_panel_datums():
    from ae_engine.receiving_nfb_numeric_panel_projection import (
        NfbPanelDatum, project_nfb_v5_to_panel, STATUS,
    )
    inner = NfbPanelDatum("inner_door:1", "inner-door", (100, 200),
                          (1, 0), (0, 1))
    middle = NfbPanelDatum("box_body:middle:1", "middle-plate", (300, 40),
                           (0, 1), (-1, 0))
    base = NfbPanelDatum("base_plate:1", "base-plate", (50, 70),
                         (1, 0), (0, 1))
    i = project_nfb_v5_to_panel("士林", "2P125SN", inner, feature="opening")
    m = project_nfb_v5_to_panel("士林", "2P125SN", middle, feature="opening")
    b = project_nfb_v5_to_panel("士林", "2P125SN", base, feature="screws")
    assert i.opening_uv_mm == (
        (86, 171), (114, 171), (114, 229), (86, 229),
    )
    assert i.screw_centres_uv_mm is None
    assert m.opening_uv_mm == (
        (329, 26), (329, 54), (271, 54), (271, 26),
    )
    assert b.opening_uv_mm is None
    assert b.screw_centres_uv_mm == (
        (37.5, 14.5), (62.5, 14.5), (37.5, 125.5), (62.5, 125.5),
    )
    assert b.screw_diameter_mm == 3.2
    assert all(not p.manufacturing_ready and p.status == STATUS
               for p in (i, m, b))
    assert {p.datum.part_id for p in (i,m,b)} == {
        "inner_door:1", "box_body:middle:1", "base_plate:1",
    }


def test_v5_cross_panel_offset_rotates_with_explicit_axis_not_assumed_world_xy():
    from ae_engine.receiving_nfb_numeric_panel_projection import (
        NfbPanelDatum, project_nfb_v5_to_panel,
    )
    datum=NfbPanelDatum("middle:2", "middle-plate", (100, 200),
                        (0, 1), (-1, 0))
    p=project_nfb_v5_to_panel("東元", "3P400SN", datum, feature="both")
    assert p.opening_uv_mm == (
        (149, 175), (149, 225), (51, 225), (51, 175),
    )
    # Original local screw group is shifted +5,+1; the 90-degree
    # panel transformation rotates the *entire* pattern consistently.
    assert p.screw_centres_uv_mm == (
        (206, 182.5), (206, 227.5),
        (-8, 182.5), (-8, 227.5),
    )
    assert p.screw_diameter_mm == 5.1
    assert p.manufacturing_ready is False


def test_v5_panel_projection_rejects_unknown_basis_missing_holes_and_mirroring():
    from ae_engine.receiving_nfb_numeric_panel_projection import (
        NfbPanelDatum, project_nfb_v5_to_panel,
    )
    right=NfbPanelDatum("base:1","base-plate",(0,0),(1,0),(0,1))
    with pytest.raises(ValueError,match="缺失"):
        project_nfb_v5_to_panel("士林","1PBH",right,feature="screws")
    with pytest.raises(ValueError,match="不足"):
        project_nfb_v5_to_panel("伍菱","100HN-s",right,feature="screws")
    ok=project_nfb_v5_to_panel("伍菱","100HN-s",right,feature="opening")
    assert ok.screw_centres_uv_mm is None
    with pytest.raises(ValueError,match="明確"):
        project_nfb_v5_to_panel("士林","2P125SN",right,feature="unsupported")
    for bad in (
        NfbPanelDatum("base:1","base-plate",(0,0),(1,0),(0,-1)),
        NfbPanelDatum("base:1","base-plate",(0,0),(1,0),(1,0)),
        NfbPanelDatum("base:1","base-plate",(0,0),(2,0),(0,1)),
        NfbPanelDatum("base:1","base-plate",(0,0),(0,1),(1,0)),
    ):
        with pytest.raises(ValueError,match="禁止鏡射"):
            project_nfb_v5_to_panel("士林","2P125SN",bad,feature="both")
    with pytest.raises(ValueError,match="板件用途"):
        project_nfb_v5_to_panel(
            "士林","2P125SN",
            NfbPanelDatum("unknown","manufacturing",(0,0),(1,0),(0,1)),
            feature="opening",
        )


def test_v5_trial_cuts_real_inner_door_finalscene_without_export_approval():
    from ae_engine.receiving_nfb_v5_real_part_cutting import (
        trial_v5_numeric_cutting_on_real_part, TRIAL_STATUS,
    )
    from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    from tools.nfb_v5_cadcraft_crosscheck import _fixture
    baseline, datum = _fixture()
    original_primitives = tuple(baseline.scene.primitives)
    original_area = baseline.material.area
    result = trial_v5_numeric_cutting_on_real_part(
        baseline, datum=datum, brand="士林", model="2P125SN", feature="both",
    )
    assert result.part_id == datum.part_id
    assert result.status == TRIAL_STATUS
    assert result.manufacturing_ready is False
    assert result.render_data.metadata["nfb_trial_export_approved"] is False
    assert result.render_data.material.area < original_area
    assert tuple(baseline.scene.primitives) == original_primitives
    assert baseline.material.area == original_area
    appended = result.render_data.scene.primitives[len(original_primitives):]
    assert len(appended) == 5
    assert len([p for p in appended
                if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.color == 3]) == 1
    assert len([p for p in appended
                if isinstance(p, CirclePrimitive) and p.layer == "CUTTING" and p.color == 3]) == 4
    assert result.render_data.unfolded_topology == baseline.unfolded_topology
    assert result.render_data.fold_guides == baseline.fold_guides
    with pytest.raises(ValueError, match="超出實際板材"):
        from ae_engine.receiving_nfb_numeric_panel_projection import NfbPanelDatum
        outside = NfbPanelDatum(
            datum.part_id, "inner-door", (100000, 100000), (1, 0), (0, 1))
        trial_v5_numeric_cutting_on_real_part(
            baseline, datum=outside, brand="士林", model="2P125SN", feature="both",
        )
    with pytest.raises(ValueError, match="不可疊寫"):
        trial_v5_numeric_cutting_on_real_part(
            result.render_data, datum=datum, brand="士林", model="2P125SN",
            feature="opening",
        )


def test_v5_cadcraft_fixture_uses_actual_cutting_scene_and_detects_modified_dxf(tmp_path):
    import json
    import shutil
    import ezdxf
    from tools.nfb_v5_cadcraft_crosscheck import emit, verify
    source = tmp_path / "w.dxf"
    copy = tmp_path / "cadcraft.dxf"
    info = tmp_path / "cadcraft-info.json"
    manifest = tmp_path / "manifest.json"
    emit(source, manifest)
    info.write_text(json.dumps({"source": "simulated info for comparator test"}), encoding="utf-8")
    # Unit check exercises the geometry comparator; actual CadCraft process
    # invocation is required by the separate GitHub workflow.
    shutil.copyfile(source, copy)
    verify(source, copy, manifest, info)
    d = ezdxf.readfile(copy)
    circles = [e for e in d.modelspace() if e.dxftype() == "CIRCLE"
               and e.dxf.layer == "CUTTING"]
    assert len(circles) == 4
    circles[0].dxf.radius *= 2
    d.saveas(copy)
    with pytest.raises(ValueError, match="CADCRAFT_DXF_GEOMETRY_OR_LAYER_DIFF"):
        verify(source, copy, manifest, info)
