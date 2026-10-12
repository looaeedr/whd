# -*- coding: utf-8 -*-
"""#1491: physical NFB layer/slot draft, 3-tier brand inheritance, nominal X/Y."""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, NEEDS_RESELECTION, PREVIEW_ONLY,
    new_nfb_ui1a_draft, reconcile_set_brand, set_nfb_draft_layer_count,
    set_nfb_layer_brand, set_nfb_slot_brand, add_nfb_draft_slot,
    select_nfb_slot_model, remove_nfb_draft_slot, effective_nfb_slot_brand,
    nfb_ui1a_preview,
)


def _draft():
    return new_nfb_ui1a_draft(set_brand="士林", layer_count=1,
                            model_layers=(["400_140X257_107.dxf"]*2,""))


def test_single_set_brand_owner_and_explicit_same_value_overrides():
    source=_draft()
    same_layer=set_nfb_layer_brand(source,0,mode=OVERRIDE,value="士林")
    same_unit=set_nfb_slot_brand(same_layer,0,0,mode=OVERRIDE,value="士林")
    assert same_layer["layers"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}
    assert same_unit["layers"][0]["slots"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}
    assert source["layers"][0]["brand"]=={"mode":INHERIT,"value":None}
    updated=reconcile_set_brand(same_unit,"東元")
    assert updated["set_brand"]=="東元"
    assert effective_nfb_slot_brand(updated,0,0)=="士林"  # explicit override
    assert effective_nfb_slot_brand(updated,0,1)=="士林"  # layer override
    inherit=set_nfb_layer_brand(updated,0,mode=INHERIT)
    assert effective_nfb_slot_brand(inherit,0,0)=="士林"
    assert effective_nfb_slot_brand(inherit,0,1)=="東元"
    reset=set_nfb_slot_brand(inherit,0,0,mode=INHERIT)
    assert effective_nfb_slot_brand(reset,0,0)=="東元"


def test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name():
    old=_draft()
    updated=reconcile_set_brand(old,"東元")
    selected=nfb_ui1a_preview(updated,bay_width_mm=800,upper_cell_height_mm=1100,
        catalog={"東元":("400_140X257_107.dxf",)})
    assert all(x["status"]==NEEDS_RESELECTION for x in selected["layers"][0]["slots"])
    assert all(x["filename"]=="400_140X257_107.dxf"
               for x in selected["layers"][0]["slots"])
    assert all(x["absolute_x_mm"] is None for x in selected["layers"][0]["slots"])
    updated=select_nfb_slot_model(
        updated,0,0,"400_140X257_107.dxf",
        catalog={"東元":("400_140X257_107.dxf",)})
    rows=nfb_ui1a_preview(updated,bay_width_mm=800,upper_cell_height_mm=1100)["layers"][0]["slots"]
    assert [x["status"] for x in rows]==["MODEL_SELECTED",NEEDS_RESELECTION]
    assert old["set_brand"]=="士林"


@pytest.mark.parametrize("width,quantity,pitch", [
    (600,2,(180.0,)), (750,2,(310.0,)), (800,2,(325.0,)),
    (800,3,(180.0,180.0)),
])
def test_nominal_pitch_exact_but_never_absolute_x(width,quantity,pitch):
    draft=new_nfb_ui1a_draft(set_brand="士林")
    for i in range(quantity):
        draft=add_nfb_draft_slot(draft,0,filename="400_140X257_107.dxf")
    r=nfb_ui1a_preview(draft,bay_width_mm=width,upper_cell_height_mm=1100)
    assert r["layers"][0]["adjacent_x_mm"]==pitch
    assert r["layers"][0]["nominal_y_from_top_mm"]==550.0
    assert all(p["absolute_x_mm"] is None for p in r["layers"])
    assert not r["can_manufacture"] and not r["has_absolute_x"]
    assert r["status"]==PREVIEW_ONLY


def test_empty_slot_keeps_physical_order_and_requires_no_fake_hole():
    source=_draft()
    with_empty=add_nfb_draft_slot(source,0)
    r=nfb_ui1a_preview(with_empty,bay_width_mm=800,upper_cell_height_mm=1100)
    assert len(r["layers"][0]["slots"])==3
    assert r["layers"][0]["slots"][2]["status"]=="EMPTY"
    assert r["layers"][0]["adjacent_x_mm"]==(180.0,180.0)
    assert source["layers"][0]["slots"][-1]["filename"]=="400_140X257_107.dxf"
    restored=remove_nfb_draft_slot(with_empty,0,2)
    assert restored==source
    with pytest.raises(IndexError):
        remove_nfb_draft_slot(source,0,8)


def test_two_layers_y_290_790_only_for_actual_1100_basis():
    d=new_nfb_ui1a_draft(set_brand="士林",layer_count=2)
    d=add_nfb_draft_slot(d,0,filename="400_140X257_107.dxf")
    d=add_nfb_draft_slot(d,1,filename="400_140X257_107.dxf")
    result=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=1100)
    assert tuple(x["nominal_y_from_top_mm"] for x in result["layers"])==(290.0,790.0)
    unknown=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=900)
    assert not unknown["is_1100_y_known"]
    assert all(x["nominal_y_from_top_mm"] is None for x in unknown["layers"])
    assert nfb_ui1a_preview(d,bay_width_mm=825,upper_cell_height_mm=1100)["layers"][0]["adjacent_x_mm"] is None
    assert d["status"]==PREVIEW_ONLY


def test_slots_do_not_erase_second_layer_and_no_stale_model_is_saved():
    d=new_nfb_ui1a_draft(set_brand="士林",layer_count=2,
                         model_layers=(["400_140X257_107.dxf"],["400_140X257_107.dxf"]))
    before=deepcopy(d)
    with pytest.raises(ValueError,match="remove"):
        set_nfb_draft_layer_count(d,1)
    assert d==before
    assert set_nfb_draft_layer_count(d,2)==d
    with pytest.raises(ValueError,match="physical layer must be visible and valid"):
        add_nfb_draft_slot(new_nfb_ui1a_draft(set_brand="士林"),1)
    with pytest.raises(ValueError,match="cannot hide"):
        new_nfb_ui1a_draft(set_brand="士林",layer_count=1,
                           model_layers=("", "400_140X257_107.dxf"))
    with pytest.raises(ValueError,match="registered"):
        reconcile_set_brand(d,"虛構廠牌")


def test_slot_reselection_requires_real_csv_entry_for_effective_brand():
    d=_draft()
    d=set_nfb_slot_brand(d,0,0,mode=OVERRIDE,value="東元")
    with pytest.raises(ValueError,match="current brand CSV"):
        select_nfb_slot_model(d,0,0,"400_140X257_107.dxf",catalog={"東元":()})
    d=select_nfb_slot_model(d,0,0,"400_140X257_107.dxf",
        catalog={"東元":("400_140X257_107.dxf",)})
    r=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=1100,
        catalog={"東元":("400_140X257_107.dxf",),"士林":("400_140X257_107.dxf",)})
    assert r["layers"][0]["slots"][0]["effective_brand"]=="東元"
    assert r["layers"][0]["slots"][0]["brand_mode"]==OVERRIDE
    assert r["layers"][0]["slots"][0]["status"]=="MODEL_SELECTED"
    assert r["layers"][0]["slots"][1]["status"]=="MODEL_SELECTED"


def test_no_unapproved_geometry_or_persistence_fields():
    d=_draft()
    for name in ("readiness","manufacturing_ready","approved","nfb_config_submitted",
                 "hole_center_x_mm","cutting"):
        assert name not in d
    result=nfb_ui1a_preview(d,bay_width_mm=600,upper_cell_height_mm=1100)
    assert not result["can_manufacture"]
    assert all(x["absolute_x_mm"] is None for x in result["layers"])
