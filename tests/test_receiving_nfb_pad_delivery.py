# -*- coding: utf-8 -*-
"""#1503: actual PAD+BASЕ physical inventory and DXF bundle, not fake MFG green."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_pad_delivery import (
    resolve_committed_pad_physical_delivery,
    pad_physical_demand_rows,
    export_pad_trial_bundle,
)
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make


def installed_pair():
    snap=_current()
    # V5 identities are selected input DATA, never a generator branch.
    snap["nfb_config"]["holes"][0].update(
        model_filename="nfbv5:士林:3P400SN",source_brand="士林")
    snap["nfb_config"]["holes"][1].update(
        model_filename="nfbv5:士林:100HN-s",source_brand="士林")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"])
    actual=apply_committed_csv_v5_to_canonical_parts(snap,(_make(snap),))
    assert len(actual)==1
    return snap,actual


def test_bom_is_a_separate_real_physical_pad_per_installed_shallower_nfb():
    snap,base=installed_pair()
    demand,=resolve_committed_pad_physical_delivery(
        snap,base,piece_count=3)
    assert demand.quantity==3
    assert demand.parent_base_id=="base_plate"
    assert demand.owner_hole_id==snap["nfb_config"]["holes"][1]["physical_hole_id"]
    assert demand.physical_id.startswith("nfb_pad:")
    assert (demand.blank_width_mm,demand.blank_height_mm)==(149.,130.)
    assert (demand.formed_width_mm,demand.formed_height_mm)==(75.,130.)
    assert demand.rise_mm==39.
    assert demand.thickness_mm==2.
    assert len(demand.source_csv_sha256)==64
    assert len(demand.tooling_sha256)==64
    assert demand.tab_tip_mating_preview_verified is True
    assert demand.full_thickness_contact_certified is False
    assert demand.full_volume_collision_certified is False
    assert demand.manufacturing_ready is False
    physical,=pad_physical_demand_rows("v1",snap,base,piece_count=3)
    assert physical.quantity==3
    assert physical.physical_id==demand.physical_id
    assert physical.render_data is demand.render_data or (
        physical.render_data.material.equals(demand.render_data.material))


@pytest.mark.parametrize("amount",(0,-1,True,2.5))
def test_pad_bom_rejects_invalid_piece_counts(amount):
    snap,base=installed_pair()
    with pytest.raises(ValueError,match="PAD_BOM_PIECE_COUNT"):
        resolve_committed_pad_physical_delivery(snap,base,piece_count=amount)


def test_cannot_create_bom_without_submitted_verified_real_base_or_four_squares():
    snap,base=installed_pair()
    with pytest.raises(ValueError,match="PAD_REAL_PARENT_BASE_MISSING"):
        resolve_committed_pad_physical_delivery(snap,(),piece_count=1)
    snap["nfb_config_submitted"]=False
    assert resolve_committed_pad_physical_delivery(snap,base)==()


def test_real_pad_and_its_matching_base_dxf_reopen_as_atomic_trial_bundle(tmp_path):
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    snap,base=installed_pair()
    target=tmp_path/"PAD_INSTALLATION_TRIAL"
    receipt=export_pad_trial_bundle(snap,base,target,piece_count=4)
    assert receipt["manufacturing_ready"] is False
    assert receipt["do_not_use_for_production"] is True
    assert receipt["parts"][0]["quantity"]==4
    assert len(receipt["dxf"])==2
    assert len(tuple(target.glob("*.dxf")))==2
    assert (target/"NOT_FOR_PRODUCTION.txt").exists()
    manifest=json.loads((target/"BOM_AND_VERIFICATION_NOT_FOR_PRODUCTION.json").read_text(encoding="utf-8"))
    assert manifest==receipt
    from hashlib import sha256
    for doc in receipt["dxf"]:
        path=target/doc["filename"]
        assert sha256(path.read_bytes()).hexdigest()==doc["sha256"]
    pad,=resolve_committed_pad_physical_delivery(snap,base)
    with pytest.raises(ValueError,match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_part_render_data_dxf(pad.render_data,tmp_path/"FORBIDDEN_PAD_MFG.dxf")
    assert not (tmp_path/"FORBIDDEN_PAD_MFG.dxf").exists()
    with pytest.raises(FileExistsError):
        export_pad_trial_bundle(snap,base,target)
    assert len(tuple(target.glob("*.dxf")))==2


def test_committed_single_bay_pad_is_counted_once_per_quantity_version():
    from ae_engine.receiving_nfb_pad_delivery import (
        pad_bom_demands_from_committed_snapshot,
    )
    snap,_=installed_pair()
    v1,=pad_bom_demands_from_committed_snapshot("v1",snap,piece_count=3)
    v2,=pad_bom_demands_from_committed_snapshot("v2",snap,piece_count=5)
    assert (v1.version_id,v1.physical_id,v1.quantity)==(
        "v1",v2.physical_id,3)
    assert (v2.version_id,v2.quantity)==("v2",5)
    assert v1.per_box_count==v2.per_box_count==1
    assert v1.render_data.metadata["manufacturing_ready"] is False
    assert v2.render_data.metadata["nfb_deferred_manufacturing_role"]=="PAD"


def test_committed_mixed_nfb_may_not_disappear_from_bom_if_world_x_missing():
    from ae_engine.receiving_nfb_pad_delivery import (
        pad_bom_demands_from_committed_snapshot,
    )
    snap,_=installed_pair()
    # Source identities still require one PAD, but there is no actual
    # installed hole geometry. Silently returning 0 BOM would under-order.
    snap["part_features"]={}
    for row in snap["nfb_config"]["holes"]:
        row["manual_x_mm"]=None
        row["manual_x_state"]="UNVERIFIED_BASIS"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"])
    # Preserve operator's explicitly selected flat PAD-bearing Base Plate;
    # the source-derived fallback can select CENTER when the NFB X is gone.
    snap["receiving_base_plate"]={
        "pattern":"LEFT_FLAT_SIDE","height":340.,
        "shrink_top":20.,"shrink_bottom":20.,
        "shrink_left":45.,"shrink_right":45.,"bend":20.,
    }
    with pytest.raises(ValueError,match="PAD_BOM_CONFIRMED_WORLD_X"):
        pad_bom_demands_from_committed_snapshot("v1",snap,piece_count=2)


def test_quantity_bom_pipeline_includes_per_version_pad_without_manufacturing_release(monkeypatch):
    from types import SimpleNamespace
    import phase6_quantity_manufacturing as quantity
    import phase6_manufacturing_service as service
    from ae_engine import manufacturing_api
    snap,_=installed_pair()
    from phase6_manufacturing_contracts import freeze_manufacturing_value
    requests=(
        ("v1",3,SimpleNamespace(input_snapshot=freeze_manufacturing_value(deepcopy(snap)))),
        ("v2",5,SimpleNamespace(input_snapshot=freeze_manufacturing_value(deepcopy(snap)))),
    )
    monkeypatch.setattr(quantity,"build_quantity_manufacturing_requests",
                        lambda _base,_work: requests)
    monkeypatch.setattr(service,"resolve",
                        lambda _req: SimpleNamespace(geometry=SimpleNamespace(
                            parts=(SimpleNamespace(part_key="base_plate"),))))
    monkeypatch.setattr(manufacturing_api,"resolved_quantity_physical_demands",
                        lambda *_args,**_kwargs: ())
    result=quantity.resolve_quantity_manufacturing(
        SimpleNamespace(cabinet_model="受電箱"),
        {"custom_parts":{"items":{}}},
    )
    assert len(result.demands)==2
    assert {(r.version_id,r.quantity) for r in result.demands}=={
        ("v1",3),("v2",5)}
    assert len({r.physical_id for r in result.demands})==1
    assert all(r.source_part_id.startswith("nfb_pad:") for r in result.demands)
    assert all(r.render_data.metadata["manufacturing_ready"] is False
               for r in result.demands)
