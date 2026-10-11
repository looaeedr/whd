# -*- coding: utf-8 -*-
"""#1502 native Color150 -> real horizontal divider UV, never MFG2 READY."""
from dataclasses import replace
from hashlib import sha256
from math import isclose

import ezdxf
import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.contracts import ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import (
    build_box_body_divider_render_data, save_part_render_data_dxf,
)
from ae_engine.manufacturing_equivalence import (
    ManufacturingParameters, manufacturing_equivalence_payload,
)
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_middle_plate_projection import (
    MIDDLE_SHADOW, NfbMiddlePlateUnfoldDatum,
    shadow_nfb_middle_plate_color150,
)
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def _source(tmp_path):
    source=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    model=doc.modelspace()
    upper=model.add_lwpolyline(
        [(3700,2550),(3757,2550),(3757,2646),(3700,2646)],
        close=True,dxfattribs={"color":150},
    )
    lower=model.add_lwpolyline(
        [(3700,1900),(3840,1900),(3840,2157),(3700,2157)],
        close=True,dxfattribs={"color":3},
    )
    model.add_circle((3800,2590),2,dxfattribs={"color":30})
    model.add_line((3790,2610),(3800,2610),dxfattribs={"color":212})
    model.add_line((3790,2000),(3800,2000),dxfattribs={"color":212})
    doc.saveas(source)
    digest=sha256(source.read_bytes()).hexdigest()
    return source,NfbUpperSourceProfile(
        "士林",source.name,digest,upper.dxf.handle,
        (57.,96.),"SOURCE_ALIAS_SHA256_IDENTICAL","v2",
    ),lower.dxf.handle


def _part():
    snapshot=receiving.apply_family_defaults({})
    snapshot.update({
        "w":800.,"h":1600.,"d":350.,"t":2.,"fw":29.,
        "door_layout_scope":"receiving-main",
        "door_layout_columns":[[800.,[1100.,500.]]],
        "multi_door_enabled":True,
    })
    part=derive_box_body_dividers(
        [(800.,[1100.,500.])],depth=350.,thickness=2.,
        layout_scope="receiving-main",model_name="受電箱",
    )[0]
    assert part.axis=="HORIZONTAL"
    assert isclose(part.span,796.)
    render=build_box_body_divider_render_data(part,ManufacturingContext())
    band=part.physical_geometry_contract["core_physical_segment"]["flat_band"]
    datum=NfbMiddlePlateUnfoldDatum(
        part.stable_id,1,(band[0]+band[1])/2.,"SHADOW-DEPTH-AXIS-UNVERIFIED",
    )
    return snapshot,part,render,datum


def _plan(tmp_path, *, world_x=0., rotation=0):
    source,profile,lower=_source(tmp_path)
    snapshot,part,baseline,datum=_part()
    kwargs=dict(
        source_path=source,profile=profile,lower_reference_handle=lower,
        world_x_mm=world_x,physical_datum=datum,rotation_deg=rotation,
    )
    return snapshot,part,baseline,kwargs


def test_real_middle_plate_origin_from_W800_horizontal_divider_not_raw_DXF(tmp_path):
    snapshot,part,original,kwargs=_plan(tmp_path)
    trial=shadow_nfb_middle_plate_color150(snapshot,part,original,**kwargs)
    assert trial.part_id==part.stable_id
    assert trial.status==MIDDLE_SHADOW
    assert not trial.manufacturing_ready
    assert trial.source_handle==kwargs["profile"].upper_handle
    assert trial.original_region=="UPPER_SOURCE"
    assert trial.uv_center_xy[1]==pytest.approx(398.)
    assert trial.uv_center_xy[0]==pytest.approx(kwargs["physical_datum"].core_depth_uv_x_mm)
    assert original.metadata.get("nfb_mfg2_status") is None  # immutable baseline
    assert len(trial.render_data.scene.primitives)==len(original.scene.primitives)+1
    cut=trial.render_data.scene.primitives[-1]
    assert isinstance(cut,PolylinePrimitive)
    assert cut.layer=="CUTTING" and cut.closed and cut.color==150
    assert trial.render_data.material.area==pytest.approx(original.material.area-57*96)
    assert "LOWER_SOURCE" not in str(trial.render_data.metadata)
    assert trial.render_data.metadata["nfb_mfg2_manufacturing_ready"] is False
    path=tmp_path/"middle_shadow_unreleased.dxf"
    save_part_render_data_dxf(trial.render_data,path)
    model=ezdxf.readfile(path).modelspace()
    assert any(
        x.dxftype()=="LWPOLYLINE"
        and x.dxf.layer=="CUTTING" and x.closed
        and x.dxf.color==150
        for x in model
    )
    assert not any(x.dxf.get("color",256)==212 for x in model)


def test_W800_world_x_reversible_and_rotation_changes_exact_equivalence(tmp_path):
    snapshot,part,original,kwargs=_plan(tmp_path)
    center=shadow_nfb_middle_plate_color150(snapshot,part,original,**kwargs)
    right=shadow_nfb_middle_plate_color150(
        snapshot,part,original,**(kwargs|{"world_x_mm":180.}),
    )
    rotated=shadow_nfb_middle_plate_color150(
        snapshot,part,original,**(kwargs|{"rotation_deg":90}),
    )
    assert right.uv_center_xy[1]-center.uv_center_xy[1]==pytest.approx(180.)
    assert rotated.uv_center_xy==pytest.approx(center.uv_center_xy)
    params=ManufacturingParameters("steel",2.,"laser")
    base=manufacturing_equivalence_payload(center.render_data,params)
    identical=manufacturing_equivalence_payload(
        shadow_nfb_middle_plate_color150(snapshot,part,original,**kwargs).render_data,
        params,
    )
    assert base==identical
    assert base!=manufacturing_equivalence_payload(right.render_data,params)
    assert base!=manufacturing_equivalence_payload(rotated.render_data,params)


@pytest.mark.parametrize("change",(
    "wrong_part","vertical","axis_missing","bad_sign","opposite_sign","outside_width",
    "wrong_sha","wrong_lower","wrong_handle","core_overflow",
))
def test_missing_physical_or_source_identity_stops_before_cutting(tmp_path,change):
    snapshot,part,original,kwargs=_plan(tmp_path)
    if change=="wrong_part":
        kwargs["physical_datum"]=replace(kwargs["physical_datum"],part_id="wrong")
    elif change=="vertical":
        part=replace(part,axis="VERTICAL")
    elif change=="axis_missing":
        kwargs["physical_datum"]=replace(kwargs["physical_datum"],revision="")
    elif change=="bad_sign":
        kwargs["physical_datum"]=replace(kwargs["physical_datum"],span_world_x_sign=0)
    elif change=="opposite_sign":
        kwargs["physical_datum"]=replace(kwargs["physical_datum"],span_world_x_sign=-1)
    elif change=="outside_width":
        kwargs["world_x_mm"]=500.
    elif change=="wrong_sha":
        kwargs["profile"]=replace(kwargs["profile"],source_sha256="0"*64)
    elif change=="wrong_lower":
        kwargs["lower_reference_handle"]=kwargs["profile"].upper_handle
    elif change=="wrong_handle":
        kwargs["profile"]=replace(kwargs["profile"],upper_handle="NONEXISTENT")
    elif change=="core_overflow":
        kwargs["physical_datum"]=replace(kwargs["physical_datum"],core_depth_uv_x_mm=0.)
    with pytest.raises((TypeError,ValueError)):
        shadow_nfb_middle_plate_color150(snapshot,part,original,**kwargs)
    assert original.metadata.get("nfb_mfg2_status") is None


def test_original_customer_DXF_is_never_modified_by_middle_shadow(tmp_path):
    snapshot,part,original,kwargs=_plan(tmp_path)
    before=kwargs["source_path"].read_bytes()
    trial=shadow_nfb_middle_plate_color150(snapshot,part,original,**kwargs)
    assert before==kwargs["source_path"].read_bytes()
    assert trial.source_sha256==sha256(before).hexdigest()
    assert trial.render_data.metadata["nfb_source_handle"]==kwargs["profile"].upper_handle


def test_optional_actual_shihlin_400_native_source_replay_keeps_lower_deferred(tmp_path):
    """Replay original bytes only if supplied, never commit a customer DXF."""
    import os
    source_value=os.environ.get("WHD_NFB_ORIGINAL_DXF")
    if not source_value:
        pytest.skip("customer original DXF not available in GitHub CI")
    from pathlib import Path
    path=Path(source_value)
    if path.name!="400_140X257_107.dxf":
        pytest.skip("only exact indexed Shihlin 400 original qualifies")
    real_sha="8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
    assert sha256(path.read_bytes()).hexdigest()==real_sha
    snapshot,part,baseline,datum=_part()
    profile=NfbUpperSourceProfile(
        "士林",path.name,real_sha,"585",(57.,96.),
        "SOURCE_ALIAS_SHA256_IDENTICAL","NFB-1497-SHIHLIN400-SOURCE-BYTE-IDENTITY-V2",
    )
    trial=shadow_nfb_middle_plate_color150(
        snapshot,part,baseline,source_path=path,profile=profile,
        lower_reference_handle="597",world_x_mm=0.,
        physical_datum=datum,
    )
    assert trial.source_sha256==real_sha
    assert trial.source_handle=="585"
    assert trial.render_data.material.area==pytest.approx(baseline.material.area-57*96)
    assert trial.status==MIDDLE_SHADOW and not trial.manufacturing_ready
    assert trial.original_region=="UPPER_SOURCE"
