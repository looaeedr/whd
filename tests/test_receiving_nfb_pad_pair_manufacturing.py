# -*- coding: utf-8 -*-
"""Production-scoped PAD+base part-only CHECK/Q under real source contact."""
import json
from hashlib import sha256
import pytest

from ae_engine.receiving_nfb_pad_pair_manufacturing import (
    export_verified_pad_base_part_only,
)
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from tests.test_receiving_nfb_pad_delivery import installed_pair


def test_certified_t2_pair_produces_actual_annotated_check_q_dxf_and_bom(tmp_path):
    import ezdxf
    snap,base=installed_pair()
    folder=tmp_path/"CERTIFIED_PAD_BASE_PART_ONLY"
    r=export_verified_pad_base_part_only(
        snap,base,folder,version_id="quantity-v1",box_count=3,
        parameters=ManufacturingParameters("SPCC",2.,"LASER"),
    )
    assert folder.is_dir()
    assert (r.per_box_pad_count,r.pad_piece_count,r.base_piece_count)==(1,3,3)
    assert len(r.files)==2
    mfile=folder/"PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json"
    assert sha256(mfile.read_bytes()).hexdigest()==r.evidence_sha256
    manifest=json.loads(mfile.read_text(encoding="utf-8"))
    assert manifest["full_cabinet_manufacturing_released"] is False
    assert manifest["pad_total"]==3 and manifest["base_total"]==3
    assert manifest["sources"][0]["tab_insert_mm"]==pytest.approx(2.)
    assert manifest["sources"][0]["base_slab_collision_verified"] is True
    assert len(manifest["dxf"])==2
    for row in manifest["dxf"]:
        file=folder/row["name"]
        assert file.is_file()
        assert sha256(file.read_bytes()).hexdigest()==row["sha256"]
        entities=tuple(ezdxf.readfile(file).modelspace())
        holes=tuple(e for e in entities
                    if e.dxftype()=="CIRCLE" and e.dxf.layer=="CUTTING")
        squares=tuple(e for e in entities
                      if e.dxftype()=="LWPOLYLINE"
                      and e.dxf.layer=="CUTTING" and e.closed)
        if any(str(key).startswith("nfb_pad:") for key in row["source_ids"]):
            # Raised switch screws are on PAD: four selected-CSV bores.
            assert len(holes)==4
            assert len(squares)==1
        else:
            # One direct-mounted switch keeps its four Base screw bores;
            # the raised switch contributes four Base locator squares only.
            assert len(holes)==4
            assert len(squares)==9
        q=[e for e in entities if e.dxftype() in ("TEXT","MTEXT")
           and e.dxf.layer=="CHECK"]
        assert len(q)==1
        assert q[0].plain_text()=="Q3" if q[0].dxftype()=="MTEXT" else q[0].dxf.text=="Q3"
    with pytest.raises(FileExistsError):
        export_verified_pad_base_part_only(
            snap,base,folder,version_id="quantity-v1",box_count=3,
            parameters=ManufacturingParameters("SPCC",2.,"LASER"),
        )


@pytest.mark.parametrize("quantity",[0,-2,True,1.5])
def test_invalid_quantity_never_allocates_output(tmp_path,quantity):
    snap,base=installed_pair()
    directory=tmp_path/"should_not_exist"
    with pytest.raises(ValueError,match="PAD_PAIR_VERSION_COUNT"):
        export_verified_pad_base_part_only(
            snap,base,directory,version_id="v",box_count=quantity,
            parameters=ManufacturingParameters("SPCC",2.,"LASER"),
        )
    assert not directory.exists()


def test_explicit_pair_manufacturer_keeps_generic_draft_denial(tmp_path):
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    snap,base=installed_pair()
    pad,=resolve_committed_pad_physical_delivery(snap,base)
    with pytest.raises(ValueError,match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_part_render_data_dxf(pad.render_data,tmp_path/"unscoped.dxf")
    assert not (tmp_path/"unscoped.dxf").exists()


def test_pair_does_not_manufacture_when_actual_assembled_parent_is_missing(tmp_path):
    snap,_=installed_pair()
    out=tmp_path/"missing"
    with pytest.raises(ValueError):
        export_verified_pad_base_part_only(
            snap,(),out,version_id="v1",box_count=1,
            parameters=ManufacturingParameters("SPCC",2.,"LASER"),
        )
    assert not out.exists()


def test_cannot_certify_foreign_cutting_line_on_actual_base(tmp_path):
    from dataclasses import replace
    from ae_engine.sheetmetal_drawing import DrawingScene,LinePrimitive
    from ae_engine.sheetmetal_geometry import Vec2
    snap,parts=installed_pair()
    parent,=parts
    data=parent.render_data
    # Malicious/ad-hoc toolpath does not change original PAD four cutouts:
    # a count-only collision check would miss the extra manufacturing cut.
    injected=LinePrimitive(Vec2(3.,4.),Vec2(10.,12.),"CUTTING")
    corrupted=replace(parent,render_data=replace(
        data,scene=DrawingScene([*data.scene.primitives,injected])))
    folder=tmp_path/"MUST_NOT_WRITE"
    with pytest.raises(ValueError,match="PAD_PAIR_BASE_UNRECOGNIZED_CUTTING"):
        export_verified_pad_base_part_only(
            snap,(corrupted,),folder,version_id="v1",box_count=2,
            parameters=ManufacturingParameters("SPCC",2.,"LASER"),
        )
    assert not folder.exists()



def _mixed_source_two_tiers():
    """Two actual independent Base PartRenderData, one with a PAD pair."""
    from copy import deepcopy
    from ae_engine.receiving_nfb_committed_final_scene import (
        apply_committed_csv_v5_to_canonical_parts,
    )
    from tests.test_issue1502_current_csv_original_two_tier_dxf import (
        _current_two_tiers, _actual_scene,
    )
    snapshot=_current_two_tiers()
    first=snapshot["nfb_config"]["holes"][0]
    first.update(
        model_filename="nfbv5:士林:3P400SN",manual_x_mm=-150.,
    )
    pad=deepcopy(first)
    pad.update(
        physical_hole_id="tier:0:pad:1",
        model_filename="nfbv5:士林:100HN-s",
        layer_index=0,slot_index=1,manual_x_mm=150.,
    )
    snapshot["nfb_config"]["holes"].append(pad)
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snapshot["nfb_config"]
    )
    return snapshot,_actual_scene(snapshot)


def test_same_source_rule_manufactures_only_pad_bearing_tier_with_real_check_q(tmp_path):
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    snapshot,parts=_mixed_source_two_tiers()
    records=resolve_committed_pad_physical_delivery(snapshot,parts,piece_count=2)
    assert len(records)==1
    assert records[0].parent_base_id=="base_plate:nfb_layer:0"
    assert records[0].seating_witness.full_thickness_seated
    assert records[0].seating_witness.base_slab_collision_verified
    target=tmp_path/"real-tier-0-pair"
    output=export_verified_pad_base_part_only(
        snapshot,parts,target,version_id="two-tier-v1",box_count=2,
        parameters=ManufacturingParameters("SPCC",2.,"LASER"),
    )
    assert output.per_box_pad_count==1
    assert (output.pad_piece_count,output.base_piece_count)==(2,2)
    assert len(output.files)==2
    import ezdxf
    for filename in output.files:
        entity=tuple(ezdxf.readfile(target/filename).modelspace())
        assert sum(x.dxf.layer=="CHECK" and x.dxftype() in ("TEXT","MTEXT")
                   for x in entity)==1
    manifest=json.loads(
        (target/"PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json").read_text(
            encoding="utf-8"))
    assert manifest["sources"][0]["parent_base_id"]=="base_plate:nfb_layer:0"


def test_two_tier_pair_rejects_stale_parent_owner_before_export(tmp_path):
    from dataclasses import replace
    snapshot,parts=_mixed_source_two_tiers()
    tier0=next(p for p in parts if p.part_key=="base_plate:nfb_layer:0")
    broken=replace(tier0,render_data=replace(
        tier0.render_data,metadata={
            **tier0.render_data.metadata,"nfb_layer_index":1,
        }))
    out=tmp_path/"wrong-tier-NO-OUTPUT"
    with pytest.raises(ValueError,match="PAD_PAIR_TIER_BASE_PHYSICAL_SOURCE_NOT_VERIFIED"):
        export_verified_pad_base_part_only(
            snapshot,tuple(broken if p.part_key==tier0.part_key else p
                           for p in parts),
            out,version_id="v",box_count=1,
            parameters=ManufacturingParameters("SPCC",2.,"LASER"),
        )
    assert not out.exists()



def test_both_real_tiers_pad_and_base_have_independent_owners_and_total_q(tmp_path):
    """Every physical tier is solved independently, even if sheets nest/group."""
    from copy import deepcopy
    from ae_engine.receiving_nfb_committed_final_scene import (
        apply_committed_csv_v5_to_canonical_parts,
    )
    from tests.test_issue1502_current_csv_original_two_tier_dxf import (
        _actual_scene,
    )
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    snap,_=_mixed_source_two_tiers()
    second=snap["nfb_config"]["holes"][1]
    second.update(model_filename="nfbv5:士林:3P400SN",manual_x_mm=-150.)
    pad=deepcopy(second)
    pad.update(physical_hole_id="tier:1:pad:1",
               model_filename="nfbv5:士林:100HN-s",
               layer_index=1,slot_index=1,manual_x_mm=150.)
    snap["nfb_config"]["holes"].append(pad)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"])
    actual=_actual_scene(snap)
    records=resolve_committed_pad_physical_delivery(
        snap,actual,piece_count=2)
    assert len(records)==2
    assert {r.parent_base_id for r in records}=={
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"}
    assert all(r.full_thickness_contact_certified
               and r.seating_witness.base_slab_collision_verified
               for r in records)
    target=tmp_path/"two-tier-all-sheets"
    result=export_verified_pad_base_part_only(
        snap,actual,target,version_id="two-layer-source-v1",box_count=2,
        parameters=ManufacturingParameters("SPCC",2.,"LASER"))
    assert (result.per_box_pad_count,result.pad_piece_count,
            result.base_piece_count)==(2,4,4)
    doc=json.loads((target/"PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json"
                    ).read_text(encoding="utf-8"))
    assert {r["parent_base_id"] for r in doc["sources"]}=={
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"}
    # Equivalence may nest identical sheet stock into the same CHECK/Q DXF,
    # but source identities and total physical quantities cannot disappear.
    assert sum(r["quantity"] for r in doc["dxf"])==8
    assert sum(len(r["source_ids"]) for r in doc["dxf"])==4
    assert len(set(r["physical_id"] for r in doc["sources"]))==2



def test_original_gui_pad_base_export_action_routes_real_two_tier_pair(tmp_path,monkeypatch):
    """Product action's exact Set/Bay/qty material UI route uses the same proof."""
    from types import SimpleNamespace
    from unittest.mock import Mock
    from gui_modules.project.export_actions import (
        export_receiving_pad_base_part_only_dxf,
    )
    import gui_modules.project.export_actions as actions
    import tkinter.simpledialog as dialog
    import fold_designer_bridge as bridge
    snap,parts=_mixed_source_two_tiers()
    assert snap["nfb_config_submitted"] is True
    adapter=SimpleNamespace(query_assembly_render_data=lambda: SimpleNamespace(
        assembly_parts=parts))
    monkeypatch.setattr(bridge,"_phase6_final_scene_adapter",
                        lambda _designer: adapter)
    monkeypatch.setattr(dialog,"askstring",
                        Mock(side_effect=["SPCC","LASER"]))
    monkeypatch.setattr(dialog,"askinteger",
                        Mock(return_value=2))
    monkeypatch.setattr(actions.filedialog,"askdirectory",
                        Mock(return_value=str(tmp_path)))
    success=Mock()
    errors=Mock()
    monkeypatch.setattr(actions.messagebox,"showinfo",success)
    monkeypatch.setattr(actions.messagebox,"showerror",errors)
    panel=SimpleNamespace(
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=snap),
        _flush_phase6_authoritative_state=lambda:None,
    )
    r=export_receiving_pad_base_part_only_dxf(panel)
    errors.assert_not_called()
    success.assert_called_once()
    assert r is not None
    assert r.scope=="RECEIVING_PAD_BASE_PAIR_PART_ONLY_CHECK_Q"
    assert (r.pad_piece_count,r.base_piece_count)==(2,2)
    assert len(r.files)==2
    directory=tmp_path/next(iter(p.name for p in tmp_path.iterdir()))
    assert len(list(directory.glob("*.dxf")))==2
    manifest=json.loads(
        (directory/"PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json"
         ).read_text(encoding="utf-8"))
    assert manifest["full_cabinet_manufacturing_released"] is False
    assert manifest["pad_total"]==2
    assert manifest["base_total"]==2
