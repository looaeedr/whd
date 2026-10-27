# -*- coding: utf-8 -*-
"""Current submitted numeric CSV -> ORIGINAL selected GUI -> complete bounded DXF.

One normal transaction: actual BoxBody with side MARKING, one or two source
fixed EARs on each physical NFB base, current CSV inner door, individual base
CUTTING, optional other selected cabinet sheets. No second operator button.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from gui_modules.project.export_actions import (
    _export_selected_resolved_parts, _resolved_export_intention_key,
)
from tests.test_issue1050_receiving_mother_plate_marking import (
    _snapshot as _box_snapshot, _full_receiving_geometry,
)
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _current_two_tiers,
)
from tests.test_receiving_two_tier_physical_base_parts import _source


def _prepare(two):
    raw = _current_two_tiers() if two else _current()
    snapshot = _box_snapshot()
    snapshot.update(deepcopy(raw))
    base = _source(snapshot)
    if two:
        source_parts = expand_receiving_nfb_layer_parts(snapshot,(base,))
    else:
        placed = resolve_assembly_placement(snapshot, "base_plate")
        source_parts = (replace(base,offset=placed.world_offset),)
    panel = next(p for p in derive_inner_door_panels(snapshot)
                 if str(p.cell_key).split(":")[-1] == "0")
    door = ResolvedManufacturingPart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., 0., 0.),
    )
    bases = tuple(ResolvedManufacturingPart(
        part_key=p.part_key,render_data=p.render_data,
        x_profile=p.x_profile,y_profile=p.y_profile,
        placement=p.placement,offset=p.offset,
    ) for p in source_parts)
    csv_parts = apply_committed_csv_v5_to_canonical_parts(
        snapshot, (door,)+bases,
    )
    body = _full_receiving_geometry(snapshot)
    result = replace(body,parts=body.parts+csv_parts)
    return snapshot,result


def _host(snapshot, geometry):
    calls=[]
    class Designer:
        _phase6_input_snapshot=snapshot
        designer_workspace=None
        def _phase6_resolve_manufacturing_geometry(self):
            calls.append("resolve")
            return geometry
    return SimpleNamespace(fold_designer_app=Designer()),calls


def _flags(**kwargs):
    data={"box_body":True,"head":True,"tail":False,"door":True,
          "base_plate":True,"indicator_box":False,"indicator_door":False}
    data.update(kwargs)
    return data


def _run(snapshot, geometry, output, flags=None):
    host,calls=_host(snapshot,geometry)
    names,errs=_export_selected_resolved_parts(
        host,str(output),_flags(**(flags or {})),
    )
    return names,errs,calls


@pytest.mark.parametrize("two,ear_count,base_count",(
    (False,2,1),(True,4,2),
))
def test_one_original_selected_export_contains_real_complete_csv_inventory(
    tmp_path,two,ear_count,base_count,
):
    snapshot,geom=_prepare(two)
    source=tuple((p.part_key,p.render_data) for p in geom.parts)
    names,errors,calls=_run(snapshot,geom,tmp_path)
    assert errors == [] and calls == ["resolve"]
    # A true whole-cabinet selection now carries an atomic software MFG-2
    # receipt IN ADDITION TO every genuine production sheet (not instead).
    import json
    from ae_engine.receiving_mfg2_software_receipt import (
        RECEIPT_FILENAME, RECEIPT_SCHEMA,
    )
    assert names.count(RECEIPT_FILENAME) == 1
    source_receipt = json.loads((tmp_path / RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert source_receipt["schema"] == RECEIPT_SCHEMA
    assert source_receipt["output_dxf_count"] == len(names)-1
    names = [name for name in names if name != RECEIPT_FILENAME]
    assert len(names)==len(list(tmp_path.glob("*.dxf")))
    assert len(names)==len(set(names))
    assert len([name for name in names if "fixing_plate" in name])==ear_count
    assert len([name for name in names if "base_plate" in name
                and "fixing_plate" not in name])==base_count
    assert "inner_door_upper_panel.dxf" in names or any(
        "inner_door" in name and "panel" in name for name in names
    )
    for name in names:
        ezdxf.readfile(tmp_path/name)
    for name in names:
        if "fixing_plate" in name:
            msp=ezdxf.readfile(tmp_path/name).modelspace()
            assert sum(1 for x in msp if x.dxf.layer=="BEND") == 1
            assert sum(1 for x in msp if x.dxftype()=="LWPOLYLINE"
                       and x.dxf.layer=="CUTTING" and x.closed)==5
    for side in ("left_side","right_side"):
        file=tmp_path/("box_body_box_body_"+side+".dxf")
        assert file.is_file()
        marking=[x for x in ezdxf.readfile(file).modelspace()
                 if x.dxftype()=="LINE" and x.dxf.layer=="MARKING"]
        assert len(marking)>=(2 if two else 1)
    assert source==tuple((p.part_key,p.render_data) for p in geom.parts)


@pytest.mark.parametrize("two", (False,True))
def test_door_and_base_only_use_original_selection_without_ears(tmp_path,two):
    snapshot,geometry=_prepare(two)
    names,errors,calls=_run(snapshot,geometry,tmp_path,{
        "box_body":False,"head":False,
    })
    assert errors==[] and calls==["resolve"]
    assert not any("fixing_plate" in p for p in names)
    # "door" intentionally selects all actual visible DOOR sheets as well
    # as the NFB inner-door panel. Do not assume the user's existing outer
    # door panels disappear just because the CSV has one upper NFB panel.
    assert any("inner_door" in name and "panel" in name for name in names)
    assert len([name for name in names if "base_plate" in name]) == (
        2 if two else 1
    )
    assert not any("box_body" in name for name in names)
    assert len(list(tmp_path.glob("*.dxf")))==len(names)
    assert all((tmp_path/p).is_file() for p in names)


def test_real_tier_base_is_selected_as_base_not_ignored():
    assert _resolved_export_intention_key("base_plate:nfb_layer:0")=="base_plate"
    assert _resolved_export_intention_key("base_plate:nfb_layer:1")=="base_plate"
    assert _resolved_export_intention_key("base_plate:fixing_plate:left") is None


def test_missing_real_tier_fails_before_any_output(tmp_path):
    snapshot,geometry=_prepare(True)
    reduced=replace(geometry,parts=tuple(p for p in geometry.parts
        if p.part_key!="base_plate:nfb_layer:1"))
    host,_=_host(snapshot,reduced)
    with pytest.raises(ValueError):
        _export_selected_resolved_parts(host,str(tmp_path/"out"),_flags())
    assert not (tmp_path/"out").exists()


def test_stale_csv_door_vs_normal_scene_rejected_and_atomic(tmp_path):
    snapshot,geometry=_prepare(False)
    tampered=deepcopy(snapshot)
    tampered["nfb_config"]["holes"][0]["manual_x_mm"]+=20
    tampered["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        tampered["nfb_config"],
    )
    host,_=_host(tampered,geometry)
    with pytest.raises(ValueError,match="SOURCE_DRIFT|SOURCE|CONTACT"):
        _export_selected_resolved_parts(host,str(tmp_path/"out"),_flags())
    assert not (tmp_path/"out").exists()


def test_wrong_installed_base_z_cannot_publish_ear_or_side_or_nfb(tmp_path):
    snap,geom=_prepare(False)
    broken=replace(geom,parts=tuple(replace(p,offset=(
        p.offset[0],p.offset[1],p.offset[2]+2.0,
    )) if p.part_key=="base_plate" else p for p in geom.parts))
    host,_=_host(snap,broken)
    with pytest.raises(ValueError):
        _export_selected_resolved_parts(host,str(tmp_path/"bad"),_flags())
    assert not (tmp_path/"bad").exists()
