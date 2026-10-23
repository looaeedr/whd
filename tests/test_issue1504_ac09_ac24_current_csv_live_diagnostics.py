# -*- coding: utf-8 -*-
"""#1504 AC-09/AC-24: current saved CSV V5 source, scope and operator holds.

No legacy DXF proof, guessed world-X, persisted DRAFT/READY, or whole-cabinet
fabrication authorization is used to assert source availability.
"""
from __future__ import annotations

from copy import deepcopy
import csv
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_v5_diagnostics import current_v5_nfb_diagnostics
from ae_engine.receiving_nfb_numeric_catalog import (
    HEADER, brand_csv_path, read_numeric_specs,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
)
from ae_engine.receiving_nfb_persistence import normalize_nfb_saved_fields
from gui_modules.application.receiving_nfb_manifest_view import (
    nfb_manifest_display_lines, highlighted_nfb_manifest_lines,
)
from phase6_project_file import PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V3, write_project, read_project


def _model(brand="士林"):
    specs = read_numeric_specs(brand)
    available = [spec.model for spec in specs if spec.dimensionally_complete]
    assert available, brand
    return available[0]


def _bay(brand="士林", *, count=1, version="b1", state="CONFIRMED"):
    model = _model(brand)
    rows = [{
        "physical_hole_id": f"nfb:{version}:layer:{layer}:unit:0",
        "model_filename": f"nfbv5:{brand}:{model}",
        "source_brand": brand,
        "layer_count": count,
        "layer_index": layer,
        "slot_index": 0,
        "rotation_deg": 0,
        "manual_x_state": state,
        "manual_x_mm": 0 if state=="CONFIRMED" else None,
        **({"datum_revision":"operator-x","datum_snapshot":{"w":800}}
           if state=="CONFIRMED" else {}),
    } for layer in range(count)]
    return {"nfb_config_submitted":True,
            "nfb_config":{"layer_count":count,"holes":rows}}


def _inspect(bay, *, bay_id="B1", version="inner-door-v1"):
    return current_v5_nfb_diagnostics(
        bay, set_id="setA", bay_id=bay_id, version_id=version,
        dependent_part_ids=("inner_door:upper:panel","base_plate"),
        unaffected_part_ids=("side_panel:left",),
    )


def test_ac09_valid_real_numeric_csv_is_recheck_only_not_manufacturing_ready():
    view=_inspect(_bay())
    assert view["status"]=="CSV_V5_SCOPED_DIAGNOSTIC"
    assert view["derived_state"]=="CONFIGURED"
    assert view["set_id"]=="setA" and view["bay_id"]=="B1"
    assert view["version_id"]=="inner-door-v1"
    assert view["unit_rows"][0]["source_status"]=="SOURCE_PRESENT_RECHECK_ONLY"
    assert view["unit_rows"][0]["reasons"]==()
    assert view["unit_rows"][0]["manufacturing_verified"] is False
    assert view["manufacturing_ready"] is False
    assert view["actual_export_count"] is None and not view["rows"]
    assert all(part["status"]=="RECHECK_ONLY" for part in view["part_rows"][:2])
    assert view["part_rows"][2]["status"]=="NFB_UNAFFECTED"
    lines=highlighted_nfb_manifest_lines(
        {"manifest":lambda si,bi:view},0,(0,),
    )
    assert any("Set setA／Bay B1／版本 inner-door-v1" in line for line in lines)
    assert any("第1層／第1顆" in line and "實體待驗" in line for line in lines)
    assert any("side_panel:left" in line and "不受 NFB 缺項連坐" in line
               for line in lines)
    assert not any("可加工 1 片" in line for line in lines)


def test_ac24_two_tiers_per_hole_reasons_do_not_hide_draft_or_other_part():
    bay=_bay(count=2)
    bay["nfb_config"]["holes"][1]["manual_x_state"]="RECONFIRM_REQUIRED"
    bay["nfb_config"]["holes"][1]["manual_x_mm"]=None
    view=_inspect(bay)
    assert view["derived_state"]=="DRAFT"
    assert [r["layer_index"] for r in view["unit_rows"]]==[0,1]
    assert [r["slot_index"] for r in view["unit_rows"]]==[0,0]
    assert view["unit_rows"][0]["reasons"]==()
    assert view["unit_rows"][1]["reasons"]==("NFB_WORLD_X_RECONFIRM_REQUIRED",)
    assert all(x["status"]=="BLOCKED" for x in view["part_rows"][:2])
    assert view["part_rows"][2]["status"]=="NFB_UNAFFECTED"
    lines=nfb_manifest_display_lines(view)
    assert any("第2層／第1顆" in line and "WORLD_X_RECONFIRM_REQUIRED" in line
               for line in lines)
    # Derivation is read-only: the submitted config remains persistable.
    assert bay["nfb_config_submitted"] is True
    assert "readiness" not in bay["nfb_config"]
    assert normalize_nfb_saved_fields(bay)["nfb_config"]["layer_count"]==2


def test_ac09_missing_model_and_malformed_current_csv_fail_closed_without_rewriting_saved_unit(
    tmp_path, monkeypatch,
):
    brand="士林"
    original=brand_csv_path(brand).read_bytes()
    alternate=tmp_path/"NFB數值規格.csv"
    alternate.write_bytes(original)
    import ae_engine.receiving_nfb_numeric_catalog as catalog
    real=catalog.brand_csv_path
    monkeypatch.setattr(catalog,"brand_csv_path",
                        lambda name:alternate if name==brand else real(name))
    bay=_bay(brand)
    before=deepcopy(bay)
    assert _inspect(bay)["derived_state"]=="CONFIGURED"
    # Remove exactly one current model from an ISOLATED CSV copy.
    with alternate.open(encoding="utf-8-sig",newline="") as stream:
        rows=list(csv.DictReader(stream))
    assert rows
    selected=bay["nfb_config"]["holes"][0]["model_filename"].split(":",2)[2]
    remaining=[row for row in rows if row["型號"]!=selected]
    with alternate.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(remaining)
    missing=_inspect(bay)
    assert missing["derived_state"]=="DRAFT"
    assert "NFB_CSV_MODEL_MISSING" in missing["unit_rows"][0]["reasons"]
    assert missing["part_rows"][0]["status"]=="BLOCKED"
    assert missing["part_rows"][2]["status"]=="NFB_UNAFFECTED"
    alternate.write_text("wrong,columns\\n",encoding="utf-8")
    malformed=_inspect(bay)
    assert "NFB_CSV_SOURCE_UNAVAILABLE_OR_INVALID" in malformed["unit_rows"][0]["reasons"]
    alternate.unlink()
    absent=_inspect(bay)
    assert "NFB_CSV_SOURCE_UNAVAILABLE_OR_INVALID" in absent["unit_rows"][0]["reasons"]
    alternate.write_bytes(original)
    recovered=_inspect(bay)
    assert recovered["derived_state"]=="CONFIGURED"
    assert bay==before
    assert recovered["manufacturing_ready"] is False


def test_ac09_two_current_bays_save_reload_source_invalidation_is_per_bay(tmp_path,monkeypatch):
    first=_bay("士林",version="one")
    second=_bay("東元",version="two",state="UNVERIFIED_BASIS")
    layout=new_receiving_layout(width=800,height=1600,depth=350)
    layout=resize_receiving_bays(layout,set_index=0,bay_count=2)
    layout=update_receiving_bay(layout,set_index=0,bay_index=0,
                                nfb_config_submitted=True,
                                nfb_config=first["nfb_config"])
    layout=update_receiving_bay(layout,set_index=0,bay_index=1,
                                nfb_config_submitted=True,
                                nfb_config=second["nfb_config"])
    file=write_project(tmp_path/"two-bays.p6fold",{
        "schema":PROJECT_SCHEMA_V1,
        "snapshot":{"model":"受電箱","active_mode":"set_bay","receiving_layout":layout},
    })
    reopened=read_project(file)
    assert reopened["schema"]==PROJECT_SCHEMA_V3
    bays=reopened["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    id_a,id_b=bays[0]["stable_id"],bays[1]["stable_id"]
    before=deepcopy(reopened)
    a=current_v5_nfb_diagnostics(bays[0],set_id="setA",bay_id=id_a,version_id="inner-door-v1")
    b=current_v5_nfb_diagnostics(bays[1],set_id="setA",bay_id=id_b,version_id="inner-door-v2")
    assert a["derived_state"]=="CONFIGURED"
    assert b["derived_state"]=="DRAFT"
    assert a["unit_rows"][0]["physical_hole_id"]!=b["unit_rows"][0]["physical_hole_id"]
    import ae_engine.receiving_nfb_numeric_catalog as catalog
    real=catalog.brand_csv_path
    monkeypatch.setattr(catalog,"brand_csv_path",lambda brand:
                        tmp_path/"missing-shihlin.csv" if brand=="士林" else real(brand))
    stale_a=current_v5_nfb_diagnostics(bays[0],set_id="setA",bay_id=id_a,version_id="inner-door-v1")
    still_b=current_v5_nfb_diagnostics(bays[1],set_id="setA",bay_id=id_b,version_id="inner-door-v2")
    assert stale_a["derived_state"]=="DRAFT"
    assert "SOURCE_UNAVAILABLE" in stale_a["unit_rows"][0]["reasons"][0]
    assert still_b["unit_rows"][0]["source_status"]=="UNVERIFIED"
    assert still_b["unit_rows"][0]["reasons"]==("NFB_WORLD_X_RECONFIRM_REQUIRED",)
    assert reopened==before
    assert all(row["nfb_config_submitted"] is True for row in bays)


def test_ac24_legacy_mixed_and_cross_part_guards():
    legacy={"nfb_config_submitted":True,
            "nfb_config":{"layer_count":1,"holes":[{
                "physical_hole_id":"old","model_filename":"400_140X257_107.dxf",
                "manual_x_state":"NONE","manual_x_mm":None,
            }]}}
    assert current_v5_nfb_diagnostics(
        legacy,set_id="setA",bay_id="B1",version_id=None,
    ) is None
    mixed=_bay()
    mixed["nfb_config"]["holes"].append(deepcopy(legacy["nfb_config"]["holes"][0]))
    view=_inspect(mixed)
    assert view["derived_state"]=="DRAFT"
    assert "NFB_CURRENT_CSV_LEGACY_MIXED_SOURCE" in view["unit_rows"][1]["reasons"]
    with pytest.raises(ValueError,match="duplicate or overlapping"):
        current_v5_nfb_diagnostics(
            _bay(),set_id="setA",bay_id="B1",version_id="inner-door-v1",
            dependent_part_ids=("base_plate",),unaffected_part_ids=("base_plate",),
        )
    assert current_v5_nfb_diagnostics(
        {"nfb_config_submitted":False},set_id="setA",bay_id="B1",version_id=None
    ) is None



def test_ac24_v5_typed_model_identity_accepts_optional_persisted_source_brand():
    source=_bay()
    original=source["nfb_config"]["holes"][0]["source_brand"]
    source["nfb_config"]["holes"][0].pop("source_brand")
    assert _inspect(source)["derived_state"]=="CONFIGURED"
    source["nfb_config"]["holes"][0]["source_brand"]=None
    assert _inspect(source)["derived_state"]=="CONFIGURED"
    source["nfb_config"]["holes"][0]["source_brand"]="東元"
    with pytest.raises(ValueError,match="mismatch"):
        _inspect(source)
    assert original=="士林"


def test_ac24_duplicate_physical_slot_or_stale_layer_count_keeps_draft_unverified():
    saved=_bay(count=2)
    duplicate=deepcopy(saved)
    duplicate["nfb_config"]["holes"][1]["layer_index"]=0
    duplicate["nfb_config"]["holes"][1]["slot_index"]=0
    report=_inspect(duplicate)
    assert report["derived_state"]=="DRAFT"
    assert "NFB_DUPLICATE_LAYER_UNIT_OWNER" in report["unit_rows"][1]["reasons"]
    assert report["part_rows"][0]["status"]=="BLOCKED"
    mismatched=deepcopy(saved)
    mismatched["nfb_config"]["holes"][1]["layer_count"]=1
    report=_inspect(mismatched)
    assert report["derived_state"]=="DRAFT"
    assert "NFB_UNIT_LAYER_COUNT_MISMATCH" in report["unit_rows"][1]["reasons"]
    assert report["part_rows"][-1]["status"]=="NFB_UNAFFECTED"
    assert saved==_bay(count=2)


def test_ac24_forbid_forged_green_status_and_gui_source_is_connected():
    current=_inspect(_bay())
    for bad in (
        {**current,"manufacturing_ready":True},
        {**current,"actual_export_count":1},
        {**current,"rows":({"part_id":"fake","may_export":True},)},
    ):
        with pytest.raises(ValueError,match="must not claim"):
            nfb_manifest_display_lines(bad)
    gui=(Path(__file__).resolve().parents[1] /
         "gui_modules/application/fold_designer_composition_receiving.py"
         ).read_text(encoding="utf-8")
    assert "current_v5_nfb_diagnostics(" in gui
    assert 'setting_value(\n                        owner, bay_index, "inner_door_version_id",' in gui
    assert "committed_nfb_evidence.get((set_index,bay_index))" in gui
    assert 'export_current_csv_nfb_door_base_pair(' in gui
