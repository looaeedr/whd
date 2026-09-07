# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement, resolve_divider_placement
from ae_engine.manufacturing_api import save_part_render_data_dxf
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive
from phase6_designer_workspace import Phase6DesignerWorkspace
from tests.test_issue37_vault_baseplate_placement import _vault_snapshot
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part
from tests.test_issue40_divider_6p4_shared_datum import _divider_anchor_group
import fold_designer_bridge as bridge


def _solve_receiving(snapshot):
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    solved_parts, diagnostics, joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    assert diagnostics and diagnostics[0].illegal_penetration is False
    return divider, solved, tuple(solved_parts), tuple(diagnostics), tuple(joints)


def _hole_signature(render):
    return sorted(
        (
            str(getattr(p, "source_type", "") or ""),
            round(float(p.center.x), 9),
            round(float(p.center.y), 9),
            round(float(p.radius), 9),
        )
        for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
    )


def _scene_dxf_signature(render):
    polylines = []
    lines = []
    circles = []
    for p in render.scene.primitives:
        layer = str(getattr(p, "layer", "") or "").upper()
        if layer not in {"CUTTING", "BEND"}:
            continue
        if isinstance(p, PolylinePrimitive):
            polylines.append((
                layer,
                bool(p.closed),
                tuple((round(float(v.x), 9), round(float(v.y), 9)) for v in p.points),
            ))
        elif isinstance(p, LinePrimitive):
            a=(round(float(p.p1.x),9),round(float(p.p1.y),9))
            b=(round(float(p.p2.x),9),round(float(p.p2.y),9))
            lines.append((layer, tuple(sorted((a,b)))))
        elif isinstance(p, CirclePrimitive):
            circles.append((
                layer,
                round(float(p.center.x),9),
                round(float(p.center.y),9),
                round(float(p.radius),9),
            ))
    return {
        "polylines": sorted(polylines),
        "lines": sorted(lines),
        "circles": sorted(circles),
    }


def _dxf_signature(path):
    doc=ezdxf.readfile(path)
    msp=doc.modelspace()
    polylines=[]
    lines=[]
    circles=[]
    for e in msp:
        layer=str(e.dxf.layer or "").upper()
        if layer not in {"CUTTING","BEND"}:
            continue
        if e.dxftype()=="LWPOLYLINE":
            polylines.append((
                layer,
                bool(e.closed),
                tuple((round(float(x),9),round(float(y),9)) for x,y,*_ in e.get_points()),
            ))
        elif e.dxftype()=="LINE":
            a=(round(float(e.dxf.start.x),9),round(float(e.dxf.start.y),9))
            b=(round(float(e.dxf.end.x),9),round(float(e.dxf.end.y),9))
            lines.append((layer,tuple(sorted((a,b)))))
        elif e.dxftype()=="CIRCLE":
            circles.append((
                layer,
                round(float(e.dxf.center.x),9),
                round(float(e.dxf.center.y),9),
                round(float(e.dxf.radius),9),
            ))
    return {
        "polylines": sorted(polylines),
        "lines": sorted(lines),
        "circles": sorted(circles),
    }


def test_t5_serialized_state_reload_rebuilds_identical_divider_final_material_and_abc():
    snapshot=_snapshot()
    divider0, solved0, _parts0, _diag0, _joints0=_solve_receiving(snapshot)
    place0=resolve_divider_placement(snapshot, divider0.stable_id)

    physical=(
        "box_body",
        divider0.stable_id,
        "base_plate_c1_r1",
        "base_plate_c1_r2",
    )
    ws=Phase6DesignerWorkspace.from_snapshot({
        **snapshot,
        "existing_parts": list(physical),
        "active_part": divider0.stable_id,
    })
    stored=ws.resolve_and_store_assembly_placements(snapshot, resolver=resolve_assembly_placement)
    assert stored[divider0.stable_id]["world_offset"] == pytest.approx(list(place0.world_offset))

    project={**snapshot, **ws.snapshot()}
    payload=json.loads(json.dumps(project, ensure_ascii=False))
    rebuilt_ws=Phase6DesignerWorkspace.from_snapshot(payload)
    assert tuple(rebuilt_ws.available_parts)==physical
    assert rebuilt_ws.assembly_placements_snapshot()==ws.assembly_placements_snapshot()

    divider1, solved1, _parts1, _diag1, _joints1=_solve_receiving(payload)
    place1=resolve_divider_placement(payload, divider1.stable_id)

    assert divider1.stable_id==divider0.stable_id
    assert divider1.material_lengths==pytest.approx(divider0.material_lengths)
    assert divider1.signed_fold_chain==pytest.approx(divider0.signed_fold_chain)
    assert place1==place0
    assert solved1.render_data.material.symmetric_difference(
        solved0.render_data.material
    ).area == pytest.approx(0.0, abs=1e-9)
    assert _hole_signature(solved1.render_data)==_hole_signature(solved0.render_data)

    a0,b0,c0=_divider_anchor_group(solved0.render_data)
    a1,b1,c1=_divider_anchor_group(solved1.render_data)
    for before, after in ((a0,a1),(b0,b1),(c0,c1)):
        assert (float(after.center.x),float(after.center.y)) == pytest.approx(
            (float(before.center.x),float(before.center.y)), abs=1e-9
        )
    assert solved1.render_data.metadata["divider_assembly_relief"]["verified"] is True
    assert solved1.render_data.metadata["divider_endcap_shared_6p4_datum"]["datum_kind"] == "POST_RELIEF_CENTER_SPAN_CENTER"


def test_t5_2d_3d_flat_owner_and_dxf_all_consume_same_solved_divider(tmp_path):
    snapshot=_snapshot()
    divider, solved, solved_parts, diagnostics, _joints=_solve_receiving(snapshot)
    render=solved.render_data

    world=bridge._phase6_build_joint_world_geometry(
        solved_parts,
        (snapshot["w"],snapshot["h"],snapshot["d"]),
        snapshot["t"],
    )
    flat3d=world["flat_material_by_part"][divider.stable_id]
    assert flat3d.symmetric_difference(render.material).area == pytest.approx(0.0, abs=1e-9)

    output=tmp_path/"divider_solved.dxf"
    save_part_render_data_dxf(render, output)
    assert output.is_file()
    assert _dxf_signature(output)==_scene_dxf_signature(render)

    assert diagnostics[0].illegal_penetration is False
    assert render.metadata["divider_assembly_relief"]["verified"] is True


def test_t5_vault_receiving_vault_base_plate_never_returns_legacy_base_transform():
    vault=_vault_snapshot()
    first=resolve_assembly_placement(vault,"base_plate")
    assert first.placement_kind=="base_plate"
    assert first.world_offset==pytest.approx((0.0,0.0,0.0))
    assert bridge._phase6_assembly_placement_for_part(vault,"base_plate") == (
        "base_plate",(0.0,0.0,0.0)
    )

    receiving=_snapshot()
    upper=resolve_assembly_placement(receiving,"base_plate_c1_r1")
    lower=resolve_assembly_placement(receiving,"base_plate_c1_r2")
    assert upper.placement_kind=="receiving_base_plate"
    assert lower.placement_kind=="receiving_base_plate"
    assert upper.world_offset==pytest.approx((0.0,250.0,0.0))
    assert lower.world_offset==pytest.approx((0.0,-550.0,0.0))
    assert bridge._phase6_assembly_placement_for_part(receiving,"base_plate_c1_r1") == (
        "receiving_base_plate",(0.0,250.0,0.0)
    )
    assert bridge._phase6_assembly_placement_for_part(receiving,"base_plate_c1_r2") == (
        "receiving_base_plate",(0.0,-550.0,0.0)
    )

    second=resolve_assembly_placement(vault,"base_plate")
    assert second==first
    assert second.placement_kind!="base"


def test_t5_source_scan_has_single_placement_and_divider_relief_owners():
    assert "base_plate" not in bridge._PHASE6_ASSEMBLY_PLACEMENTS
    assert bridge._PHASE6_ASSEMBLY_PLACEMENTS.get("box_body")=="box_body"

    bridge_source=Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    collision_source=Path("ae_engine/assembly_collision.py").read_text(encoding="utf-8")
    renderer_source=Path("phase6_final_scene_view.py").read_text(encoding="utf-8")

    assert bridge_source.count("def _phase6_resolve_family_divider_reliefs(")==1
    assert collision_source.count("def build_divider_front_fold_relief_candidate(")==1
    assert "build_divider_front_fold_relief_candidate" not in renderer_source
    assert "apply_divider_endcap_shared_6p4_datum" not in renderer_source
    assert '"base_plate": "base"' not in bridge_source
