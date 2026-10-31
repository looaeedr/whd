# -*- coding: utf-8 -*-
"""#2383 real Receiving EndCap head/tail: source-to-W03/W04 and DXF reopen."""
from copy import deepcopy
import hashlib
import shutil

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import verify_saved_part_render_data_dxf
from ae_engine.manufacturing_endcap_compat import resolve_endcap_request
from ae_engine.sheetmetal_drawing import CirclePrimitive
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.worker_receiving_endcap import (
    receiving_endcap_spec_from_trusted_part, receiving_endcap_shared_baseline,
    receiving_endcap_frame, require_receiving_endcap_frame,
    _render as receiving_endcap_render,
)
from tests.test_issue2378_prepare_batch import (
    HERE, COMMIT, ENGINE, KEY, _root, _request, _prepare,
    _export_request_from_prepared,
)


def _part(role="end_cap_head"):
    return {
        "kind": role, "cabinet_family": "受電箱",
        "source_part_ref": role, "dimension_semantics": "cabinet_outer",
        "dimensions_mm": {
            "width": 800.0, "height": 1600.0,
            "depth": 350.0, "thickness": 2.0,
        },
        "frame_width_mm": 29.0,
        "endcap_yl1_mm": 15.0, "endcap_yr1_mm": 15.0,
        "endcap_ytop1_mm": 16.0, "endcap_ybottom1_mm": 15.0,
        "endcap_side_rear_bend_mm": 18.0,
    }


def _source(tmp_path,role="end_cap_head",*,
            has_untransferred_feature=False):
    root, _, _ = _root(tmp_path)
    baseline = receiving_endcap_shared_baseline(root)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "基準檔" / "金庫型" / "封頭尾.dxf", baseline)
    source = tmp_path / "CADSplit-Receiving-authenticated-source.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if has_untransferred_feature:
        doc.modelspace().add_circle((40,40),4,dxfattribs={"layer":"CUTTING"})
    doc.saveas(source)
    request = _request()
    request["items"][0]["part"]=_part(role)
    request["items"][0]["source_document_sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"]=compute_wire_request_digest(request)
    return root,source,request


@pytest.mark.parametrize("role",["end_cap_head","end_cap_tail"])
def test_receiving_head_tail_real_two_t_material_and_verified_dxf(role,tmp_path):
    root,source,request=_source(tmp_path,role)
    spec=receiving_endcap_spec_from_trusted_part(request["items"][0]["part"])
    resolved=resolve_endcap_request(spec)
    assert resolved.model_name=="受電箱" and resolved.is_tail==(role=="end_cap_tail")
    assert resolved.depth_comp_t==2.0
    assert spec.depth_comp_t==2.0
    assert [seg.phase6_key for seg in spec.fold_profile_y] == (
        ["ybottom1","endcap_d_core","fw","ytop1"] if role=="end_cap_tail"
        else ["ytop1","fw","endcap_d_core","ybottom1"]
    )
    assert any(seg.core=="D-T" and seg.length==346.0 for seg in spec.fold_profile_y)
    render=receiving_endcap_render(spec,ManufacturingContext(resource_root=root))
    holes=[x for x in render.scene.primitives
           if isinstance(x,CirclePrimitive) and x.layer=="CUTTING"
           and getattr(x,"source_type",None)=="baseline_endcap_hole"]
    assert len(holes)==3 and render.fold_guides
    prepared=_prepare(request,root)
    assert prepared["status"]=="success" and prepared["manufacturing_verified"] is False
    physical=prepared["items"][0]["physical_part_id"]
    frame=prepared["items"][0]["target_frames"][0]
    assert frame["frame_id"]==f"{role}:{physical}:receiving:flat:size-only-v1"
    assert frame["allowed_feature_types"]==[]
    require_receiving_endcap_frame(frame,role=role,physical_part_id=physical)
    assert frame==receiving_endcap_frame(
        spec,ManufacturingContext(resource_root=root),physical_part_id=physical
    )
    output=tmp_path/"receiving-head-tail-real-dxf"
    actual=save_trusted_door_circle_finalscene_batch(
        request,prepared,_export_request_from_prepared(request,prepared),
        source_documents={request["items"][0]["item_id"]:source},
        resource_root=root,output_dir=output,
        engine_commit=COMMIT,engine_sha256=ENGINE,
        build_id="test-only-source",worker_key=KEY,
    )
    final=output/(physical+".dxf")
    assert final.is_file() and actual=={physical:str(final)}
    assert verify_saved_part_render_data_dxf(render,final).ok
    reopened=ezdxf.readfile(final)
    assert reopened.modelspace().query('*[layer=="CUTTING"]')
    assert reopened.modelspace().query('*[layer=="BEND"]')


@pytest.mark.parametrize("fault",[
    "wrong_family","wrong_kind","wrong_ref","wrong_semantics","missing_height",
    "missing_thickness","missing_fw","over_width","zero_depth","small_fw",
    "missing_side_bend","fake_vault_scalar","manual_corner","manual_fold",
    "nan_top","bool_bottom","negative_side_bend",
])
def test_receiving_endcap_refuses_unverified_source_and_assembly(fault):
    p=_part()
    if fault=="wrong_family":p["cabinet_family"]="金庫型"
    elif fault=="wrong_kind":p["kind"]="end_cap_unregistered"
    elif fault=="wrong_ref":p["source_part_ref"]="end_cap_tail"
    elif fault=="wrong_semantics":p["dimension_semantics"]="part_formed_outer"
    elif fault=="missing_height":del p["dimensions_mm"]["height"]
    elif fault=="missing_thickness":del p["dimensions_mm"]["thickness"]
    elif fault=="missing_fw":del p["frame_width_mm"]
    elif fault=="over_width":p["dimensions_mm"]["width"]=1
    elif fault=="zero_depth":p["dimensions_mm"]["depth"]=0
    elif fault=="small_fw":p["frame_width_mm"]=0.5
    elif fault=="missing_side_bend":del p["endcap_side_rear_bend_mm"]
    elif fault=="fake_vault_scalar":p["depth_comp_t"]=3
    elif fault=="manual_corner":p["corner_policy"]={"bottom_left":"WRAP"}
    elif fault=="manual_fold":p["fold_profile_y"]=[1,2]
    elif fault=="nan_top":p["endcap_ytop1_mm"]=float("nan")
    elif fault=="bool_bottom":p["endcap_ybottom1_mm"]=True
    elif fault=="negative_side_bend":p["endcap_side_rear_bend_mm"]=-18
    with pytest.raises(PrepareEvidenceError):
        receiving_endcap_spec_from_trusted_part(p)


def test_receiving_endcap_rejects_untransferred_original_hole(tmp_path):
    root,source,request=_source(tmp_path,has_untransferred_feature=True)
    prepared=_prepare(request,root)
    out=tmp_path/"must-not-lose-source-hole"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request,prepared,_export_request_from_prepared(request,prepared),
            source_documents={request["items"][0]["item_id"]:source},
            resource_root=root,output_dir=out,
            engine_commit=COMMIT,engine_sha256=ENGINE,
            build_id="test-only-source",worker_key=KEY,
        )
    assert exc.value.code=="WHD_FINALSCENE_UNVERIFIED" and not out.exists()


def test_receiving_endcap_shared_hole_baseline_tamper_invalidates_token(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export
    root,source,request=_source(tmp_path)
    prepared=_prepare(request,root)
    export=_export_request_from_prepared(request,prepared)
    baseline=receiving_endcap_shared_baseline(root)
    d=ezdxf.readfile(baseline)
    d.modelspace().add_circle((5,5),2,dxfattribs={"layer":"CUTTING"})
    d.saveas(baseline)
    with pytest.raises(PrepareEvidenceError) as exc:
        recheck_trusted_door_export(
            request,prepared,export,resource_root=root,
            engine_commit=COMMIT,engine_sha256=ENGINE,
            build_id="test-only-source",worker_key=KEY,
        )
    assert exc.value.code=="WHD_PREPARE_STALE"


def test_receiving_endcap_signed_head_tail_role_cannot_be_replayed(tmp_path):
    root,source,request=_source(tmp_path)
    prepared=_prepare(request,root)
    export=_export_request_from_prepared(request,prepared)
    export["items"][0]["part"]["kind"]="end_cap_tail"
    export["items"][0]["part"]["source_part_ref"]="end_cap_tail"
    export["request_digest"]=compute_wire_request_digest(export)
    out=tmp_path/"no-retargeted-tail"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request,prepared,export,
            source_documents={request["items"][0]["item_id"]:source},
            resource_root=root,output_dir=out,
            engine_commit=COMMIT,engine_sha256=ENGINE,
            build_id="test-only-source",worker_key=KEY,
        )
    assert exc.value.code=="WHD_PREPARE_STALE" and not out.exists()
