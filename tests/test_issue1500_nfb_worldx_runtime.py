# -*- coding: utf-8 -*-
"""#1500 current Bay operator world-X source/part runtime routing.

Mocks the already-tested #1497 manufacturing verifier to exercise physical
selection and source/provenance file resolution without using a guessed hole.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft,add_nfb_draft_slot
from ae_engine.receiving_nfb_ui1a_edits import editable_nfb_draft
from ae_engine.receiving_nfb_ui1b_runtime import verify_current_nfb_ui_draft
import ae_engine.receiving_nfb_ui1b_runtime as runtime


def setup(tmp_path,monkeypatch):
    root=tmp_path/"基準檔"/"開孔"/"NFB"
    root.mkdir(parents=True)
    index=root/"開關索引.csv"
    index.write_text(
        "\ufeff圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "A,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8",
    )
    profile=root/"來源輪廓索引.csv"
    profile.write_text(
        "brand,indexed_filename,source_sha256,upper_handle,upper_width_mm,"
        "upper_height_mm,source_alias_status,revision\n"
        "士林,400_140X257_107.dxf,"+"a"*64+
        ",585,57,96,SOURCE_ALIAS_UNCERTIFIED,TEST-REV\n",
        encoding="utf-8",
    )
    path=root/"士林"/"400_140X257_107.dxf"
    path.parent.mkdir()
    path.write_bytes(b"mock-source-file-exists-only")
    draft=editable_nfb_draft(new_nfb_ui1a_draft(set_brand="士林"))
    draft=editable_nfb_draft(add_nfb_draft_slot(
        draft,0,filename=path.name,source_brand="士林",
    ))
    unit=draft["layers"][0]["slots"][0]["unit_id"]
    layout={"sets":[{"stable_id":"set-a","switch_brand":"士林",
                     "bays":[{"stable_id":"bay-a"}]}]}
    snapshot={
        "model":"受電箱","multi_door_enabled":True,
        "inner_doors":[{"stable_id":"upper","cell_key":"0:0"}],
        "w":800,"h":1600,"t":2,
    }
    panel=SimpleNamespace(inner_door_id="upper",cell_key="0:0",
                          stable_id="inner-upper-actual")
    monkeypatch.setattr(runtime.cabinet_family_policy,"derive_inner_door_panels",
                        lambda snapshot:(panel,))
    calls=[]
    def verified(*args,**kwargs):
        calls.append((args,kwargs))
        return "genuine-verifier-would-run"
    monkeypatch.setattr(runtime,"verify_nfb_ui1a_for_submit",verified)
    return {
        "draft":draft,"layout":layout,
        "set_index":0,"bay_index":0,"version_id":"inner-v1",
        "projected_snapshot":snapshot,"world_x_by_unit":{unit:0},
        "index_path":index,
    },unit,path,profile,calls


def test_only_real_current_upper_part_and_source_profile_reach_verifier(tmp_path,monkeypatch):
    values,unit,path,profile,calls=setup(tmp_path,monkeypatch)
    result=verify_current_nfb_ui_draft(**values)
    assert result=="genuine-verifier-would-run"
    assert len(calls)==1
    args,kws=calls[0]
    assert kws["source_path"]==path
    assert kws["profile"].upper_handle=="585"
    assert kws["profile"].upper_size_mm==(57,96)
    assert kws["inner_door_id"]=="upper"
    assert kws["physical_scope"].inner_door_part_id=="inner-upper-actual"
    assert kws["physical_scope"].base_plate_part_ids==()
    assert kws["physical_scope"].middle_plate_part_ids==()
    assert kws["world_x_by_unit"]=={unit:0}
    assert kws["datum_snapshot"]["part_id"]=="inner-upper-actual"
    assert kws["datum_revision"]
    assert args[0]["layers"][0]["slots"][0]["unit_id"]==unit


def test_missing_real_source_blocks_even_with_csv_and_world_x(tmp_path,monkeypatch):
    values,unit,path,profile,calls=setup(tmp_path,monkeypatch)
    path.unlink()
    with pytest.raises(ValueError,match="缺原始 DXF"):
        verify_current_nfb_ui_draft(**values)
    assert calls==[]


def test_multiple_possible_upper_inner_doors_are_not_guessed(tmp_path,monkeypatch):
    values,unit,path,profile,calls=setup(tmp_path,monkeypatch)
    snap=values["projected_snapshot"]
    snap["inner_doors"].append({"stable_id":"upper2","cell_key":"1:0"})
    other=SimpleNamespace(inner_door_id="upper2",cell_key="1:0",
                          stable_id="inner-upper-other")
    monkeypatch.setattr(runtime.cabinet_family_policy,"derive_inner_door_panels",
                        lambda snapshot:(
                            SimpleNamespace(inner_door_id="upper",cell_key="0:0",
                                            stable_id="inner-upper-actual"),other,
                        ))
    with pytest.raises(ValueError,match="唯一"):
        verify_current_nfb_ui_draft(**values)
    assert not calls


def test_draft_brand_mismatch_or_unsaved_version_blocks_staging(tmp_path,monkeypatch):
    values,unit,path,profile,calls=setup(tmp_path,monkeypatch)
    for change in (
        {"version_id":""},
        {"layout":{"sets":[{"stable_id":"set-a","switch_brand":"東元",
                            "bays":[{"stable_id":"bay-a"}]}]}},
        {"world_x_by_unit":{unit:17,"extra-unit":32}},
    ):
        if "world_x_by_unit" in change:
            # The real verifier must reject mismatched unit IDs rather than
            # the runtime routing layer silently removing them.
            verify_current_nfb_ui_draft(**{**values,**change})
            assert calls[-1][1]["world_x_by_unit"]==change["world_x_by_unit"]
            continue
        with pytest.raises(ValueError):
            verify_current_nfb_ui_draft(**{**values,**change})


def test_no_matching_source_profile_is_not_automatic_manufacturing(tmp_path,monkeypatch):
    values,unit,path,profile,calls=setup(tmp_path,monkeypatch)
    profile.write_text(
        "brand,indexed_filename,source_sha256,upper_handle,upper_width_mm,"
        "upper_height_mm,source_alias_status,revision\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError,match="尚未建立"):
        verify_current_nfb_ui_draft(**values)
    assert calls==[]



def test_numbered_original_dxf_is_selectable_without_renaming_index(tmp_path,monkeypatch):
    values,unit,original,profile,calls=setup(tmp_path,monkeypatch)
    original.unlink()
    downloaded=tmp_path/"400_140X257_107(1).dxf"
    downloaded.write_bytes(b"operator-selected-same-source-placeholder")
    # The full real byte-level SHA gate remains in #1497; this test only
    # verifies that UI routing retains the ORIGINAL CSV filename identity.
    result=verify_current_nfb_ui_draft(
        **{**values,"selected_source_path":downloaded},
    )
    assert result=="genuine-verifier-would-run"
    assert calls[-1][1]["source_path"]==downloaded
    assert calls[-1][1]["profile"].indexed_filename=="400_140X257_107.dxf"
    with pytest.raises(ValueError,match="並非 CSV 型號"):
        verify_current_nfb_ui_draft(
            **{**values,"selected_source_path":tmp_path/"unrelated.dxf"},
        )
