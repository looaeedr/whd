# -*- coding: utf-8 -*-
"""#1497: no manual approval registry; real CSV/DXF + configured physical X/Y."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_cutting_preflight import NfbExistingCuttingClaim
from ae_engine.receiving_nfb_manufacturing_release import (
    VALIDATED, NfbConfiguredInnerDoorHole, configured_nfb_inner_door_render_data,
    save_configured_nfb_inner_door_dxf,
)
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def _state():
    state = apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    state.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    return state


def _source(tmp_path, *, suffix=""):
    index = tmp_path / "開關索引.csv"
    index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    src = tmp_path / f"400_140X257_107{suffix}.dxf"
    doc = ezdxf.new("R2010")
    row = doc.modelspace().add_lwpolyline(
        [(10.,20.), (67.,20.), (67.,116.), (10.,116.)],
        close=True, dxfattribs={"color":150},
    )
    doc.saveas(src)
    profile = NfbUpperSourceProfile(
        brand="士林", indexed_filename="400_140X257_107.dxf",
        source_sha256=sha256(src.read_bytes()).hexdigest(),
        upper_handle=str(row.dxf.handle), upper_size_mm=(57.,96.),
        source_alias_status="SOURCE_ALIAS_UNCERTIFIED",
        revision="SHIHLIN400-OBSERVATION-01",
    )
    return index,src,profile


def _hole(x=0., *, id="nfb:upper:layer:1:unit:1", layer=1,slot=0, angle=0):
    return NfbConfiguredInnerDoorHole(
        physical_hole_id=id,world_x_mm=x,
        layer_count=layer,slot_index=slot,rotation_deg=angle,
    )


def _ready(tmp_path, holes=None, *, suffix="", claims=()):
    index,src,profile = _source(tmp_path,suffix=suffix)
    return configured_nfb_inner_door_render_data(
        _state(), "upper", holes=holes if holes is not None else (_hole(),),
        index_path=index,source_path=src,profile=profile,existing_claims=claims,
    )


@pytest.mark.parametrize("angle,wh", [
    (0,(57.,96.)),(90,(96.,57.)),(180,(57.,96.)),(270,(96.,57.)),
])
def test_configured_world_x_y_produce_real_door_cutting_without_manual_approval(
        tmp_path,angle,wh):
    state = _state()
    panel = next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
                 if p.inner_door_id == "upper")
    baseline = build_inner_door_panel_render_data(panel)
    approved = _ready(tmp_path,holes=(_hole(angle=angle),))
    assert approved.manufacturing_ready
    assert approved.part_id == panel.stable_id
    assert approved.render_data.metadata["nfb_trial_status"] == VALIDATED
    assert approved.render_data.metadata["nfb_trial_export_approved"] is True
    cuts = [p for p in approved.render_data.scene.primitives
            if isinstance(p,PolylinePrimitive) and p.layer=="CUTTING" and p.closed]
    assert len(cuts) == 2
    xs=[p.x for p in cuts[-1].points]
    ys=[p.y for p in cuts[-1].points]
    assert (max(xs)-min(xs),max(ys)-min(ys))==pytest.approx(wh)
    assert (min(xs)+max(xs))/2.0==pytest.approx(361.5)
    # Actual Y is projected by existing 1100-inner-door manufacturer, not
    # copied from the DXF's arbitrary absolute source drawing coordinates.
    assert 19 < min(ys) and max(ys) < 1075-19
    assert build_inner_door_panel_render_data(panel).scene.primitives==baseline.scene.primitives


def test_original_download_suffix_and_stale_profile_sha_are_allowed_for_same_format(tmp_path):
    index,src,profile = _source(tmp_path,suffix="(1)")
    result = configured_nfb_inner_door_render_data(
        _state(),"upper",holes=(_hole(),),
        index_path=index,source_path=src,profile=profile,
    )
    assert result.manufacturing_ready
    # The operator may edit a historical index SHA. It is NOT a frozen
    # manufacturing allow-list: actual DXF geometry is read again.
    rebound = configured_nfb_inner_door_render_data(
        _state(),"upper",holes=(_hole(),),
        index_path=index,source_path=src,
        profile=replace(profile,source_sha256="0"*64),
    )
    assert rebound.source_sha256 == profile.source_sha256
    assert rebound.render_data.metadata["nfb_source_handle"] == (
        profile.source_sha256 + ":" + profile.upper_handle
    )
    renamed=tmp_path/"unrelated_name.dxf"
    renamed.write_bytes(src.read_bytes())
    with pytest.raises(ValueError,match="filename"):
        configured_nfb_inner_door_render_data(
            _state(),"upper",holes=(_hole(),),
            index_path=index,source_path=renamed,profile=profile,
        )


def test_missing_absolute_x_invalid_y_and_geometry_collision_fail_no_output(tmp_path):
    index,src,profile = _source(tmp_path)
    target=tmp_path/"no_partial_output.dxf"
    for holes in [
        (_hole(x=None),),(_hole(layer=3),),(_hole(x=10000),),
        (_hole(),_hole(id="nfb:2",x=0.)),
        (_hole(),_hole(id="nfb:2",x=10.)),
    ]:
        with pytest.raises((ValueError,TypeError)):
            save_configured_nfb_inner_door_dxf(
                _state(),"upper",target,holes=holes,
                index_path=index,source_path=src,profile=profile,
            )
        assert not target.exists()


def test_legacy_same_physical_hole_fails_no_duplicate_cutting(tmp_path):
    index,src,profile = _source(tmp_path)
    claim=NfbExistingCuttingClaim(
        physical_hole_id="nfb:upper:layer:1:unit:1",
        part_id="inner_door:upper:panel",
        outline_uv_xy=((320.,500.),(400.,500.),(400.,620.),(320.,620.)),
    )
    with pytest.raises(ValueError,match="blocked"):
        configured_nfb_inner_door_render_data(
            _state(),"upper",holes=(_hole(),),index_path=index,source_path=src,
            profile=profile,existing_claims=(claim,),
        )


def test_final_manufacturing_dxf_contains_original_panel_and_color3_hole(tmp_path):
    index,src,profile=_source(tmp_path)
    output=tmp_path/"shihlin400_inner_door.dxf"
    save_configured_nfb_inner_door_dxf(
        _state(),"upper",output,holes=(_hole(),),
        index_path=index,source_path=src,profile=profile,
    )
    assert output.is_file()
    msp=ezdxf.readfile(output).modelspace()
    cuts=[e for e in msp if e.dxftype()=="LWPOLYLINE"
          and e.dxf.layer=="CUTTING" and e.closed]
    assert len(cuts)==2
    assert cuts[-1].dxf.color==3
