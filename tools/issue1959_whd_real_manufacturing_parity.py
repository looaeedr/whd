"""#1959: real CADCraft commands -> verified WHD session -> original door manufacturing.

Runs only in an isolated disposable directory. It never calls CADCraft to
save/rewrite a manufacturing DXF and does not update any project, baseline or
installed application. The actual manufacturing output is created exclusively
by ae_engine.manufacturing_api.generate_part (existing production authority).
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

import ezdxf

from ae_engine import ae
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import generate_part
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, ProfileFeature, RectFeature, Vec2,
    feature_surface_from_rect, resolve_surface_features,
)
from ae_engine.sheetmetal_part_adapters import (
    build_door_result, build_finished_reference_guide,
)
from gui_modules.editors.cadcraft_command_session_bridge import stage_verified_cadcraft_drawing
from phase6_hole_editor_session import Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import from_whd_resolved, run_proof


def _features():
    old = CircleFeature(
        diameter=8,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(320,350),layer="CUTTING")
    added=(
        CircleFeature(
            diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(110,130),layer="CUTTING"),
        RectFeature(
            width=20,height=12,rotation_deg=90,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(200,160),layer="CUTTING"),
        ProfileFeature(
            points=(Vec2(280,230),Vec2(295,230),Vec2(300,243),Vec2(280,248)),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0,0),layer="CUTTING"),
    )
    return old,added


def _norm(value):
    if isinstance(value,(int,float)):
        return round(float(value),6)
    if hasattr(value,"x") and hasattr(value,"y"):
        return tuple(round(float(v),6) for v in value)
    if isinstance(value,(tuple,list)):
        return tuple(_norm(v) for v in value)
    return value


def _signature(entity):
    kind=entity.dxftype()
    attrs={k:_norm(v) for k,v in entity.dxfattribs().items()
           if k not in ("handle","owner","material_handle","plotstyle_handle",
                        "visualstyle_handle","shadow_mode","transparency")}
    if kind=="LWPOLYLINE":
        attrs["points"] = tuple(tuple(round(float(v),6) for v in pt)
                                for pt in entity.get_points("xyseb"))
        attrs["closed"] = bool(entity.closed)
    elif kind=="POLYLINE":
        attrs["points"]=tuple(
            (_norm(v.dxf.location),_norm(v.dxf.get("bulge",0)))
            for v in entity.vertices)
    return (kind,entity.dxf.layer,
            tuple(sorted((key,repr(val)) for key,val in attrs.items())))


def _point_close(pt,x,y):
    return abs(float(pt[0])-x)<1e-5 and abs(float(pt[1])-y)<1e-5


def prove(cli: Path, work: Path):
    work.mkdir(parents=True,exist_ok=True)
    if any(work.iterdir()):
        raise ValueError("REFUSE_NONEMPTY_TRIAL_DIR")
    whd_baselines=work/"empty-authority-root"
    whd_baselines.mkdir()
    old,candidates=_features()
    # WHD's actual finished size, not a CADCraft guessed panel size.
    finished_w,finished_h=ae.calculate_door_finished_size(
        500,600,25,3.5,3.5,2)
    surface=feature_surface_from_rect(
        "manufacturing-door-finished-face",
        Vec2(0,0),Vec2(finished_w,finished_h))
    commands=from_whd_resolved(tuple(resolve_surface_features(
        surface,candidates,finished_w,finished_h)))
    cad_dxf=work/"CADCraft-commands-ONLY-not-manufacturing.dxf"
    cad_png=work/"CADCraft-commands-preview.png"
    cad_proof=run_proof(str(cli),commands,cad_dxf,cad_png)
    originals=[old]
    original_list_id=id(originals)
    session=Phase6HoleEditorSession("door-finished-face",originals)
    staged=stage_verified_cadcraft_drawing(
        output=cad_dxf,whd_candidates=candidates,session=session,
        surface=surface,width=finished_w,height=finished_h)
    if len(originals)!=4 or not session.has_active_edit:
        raise AssertionError("CADCRAFT_PREVIEW_NOT_STAGED")
    staged.confirm()
    if len(originals)!=4 or session.has_active_edit or id(originals)!=original_list_id:
        raise AssertionError("ORIGINAL_WHD_SESSION_CONFIRM_FAILED")
    session.finish(commit=True)

    specs=dict(
        width=500,height=600,thickness=2,frame_width=25,
        gap_w=3.5,gap_h=3.5,fold_left=19,fold_right=19,
        fold_top=19,fold_bottom=19,
    )
    context=ManufacturingContext(resource_root=whd_baselines,draw_stock=False)
    before_spec=DoorPartSpec(**specs,features=(old,))
    after_spec=DoorPartSpec(**specs,features=tuple(originals))
    # Real production export, NOT a new DXF serializer or render mock.
    original_file=work/"WHD-original-authoritative-door.dxf"
    new_file=work/"WHD-confirmed-authoritative-door.dxf"
    generate_part(before_spec,original_file,context)
    generate_part(after_spec,new_file,context)
    previous=ezdxf.readfile(original_file)
    manufactured=ezdxf.readfile(new_file)
    before=Counter(_signature(e) for e in previous.modelspace())
    after=Counter(_signature(e) for e in manufactured.modelspace())
    missing=before-after
    additions=after-before
    if missing:
        raise AssertionError("WHD_MANUFACTURING_PREEXISTING_GEOMETRY_CHANGED: "+repr(missing))
    if sum(additions.values())!=3:
        raise AssertionError("WHD_MANUFACTURING_EXPECTED_THREE_NEW_HOLES: "+repr(additions))
    # Difference entities recovered independently from real exported DXF.
    added_entities=[]
    baseline_remaining=before.copy()
    for e in manufactured.modelspace():
        signature=_signature(e)
        if baseline_remaining[signature]:
            baseline_remaining[signature]-=1
        else:
            added_entities.append(e)
    if sorted(e.dxftype() for e in added_entities)!=[
            "CIRCLE","LWPOLYLINE","LWPOLYLINE"]:
        raise AssertionError("MANUFACTURING_HOLE_ENTITY_TYPE_DRIFT")
    if any(e.dxf.layer!="CUTTING" for e in added_entities):
        raise AssertionError("HOLE_NOT_ON_CUTTING")
    if any(not e.closed for e in added_entities if e.dxftype()=="LWPOLYLINE"):
        raise AssertionError("WHD_UNCLOSED_MANUFACTURING_OUTLINE")

    # Coordinate origin is set by WHD finished-face mapping, not CADCraft.
    result=build_door_result(
        w=500,h=600,t=2,fw=25,gap_w=3.5,gap_h=3.5,
        fold_left=19,fold_right=19,fold_top=19,fold_bottom=19)
    guide=build_finished_reference_guide(
        "door",result,finished_width=finished_w,finished_height=finished_h)
    shift_x,shift_y=guide.min_point.x,guide.min_point.y
    circle=next(e for e in added_entities if e.dxftype()=="CIRCLE")
    if (not _point_close(circle.dxf.center,110+shift_x,130+shift_y)
            or abs(circle.dxf.radius-5)>1e-5):
        raise AssertionError(
            "WHD_MANUFACTURING_CIRCLE_COORDINATE_DRIFT "
            + json.dumps({
                "source_finished_xy": [110,130],
                "expected_finished_face_to_unfolded_shift": [shift_x,shift_y],
                "expected_exported_xy": [110+shift_x,130+shift_y],
                "actual_exported_xyz": list(circle.dxf.center),
                "actual_exported_radius": circle.dxf.radius,
                "finished_dimensions": [finished_w,finished_h],
                "guide_bounds": [guide.min_point.x,guide.min_point.y,
                                 guide.max_point.x,guide.max_point.y],
                "all_cutting_entities": [
                    [e.dxftype(),e.dxf.layer,
                     list(e.dxf.center) if e.dxftype()=="CIRCLE"
                     else list(e.get_points("xy"))[:4]]
                    for e in added_entities],
            }, ensure_ascii=False, default=str)
        )
    expected_polygons=[
        [(200+6,160-10),(200+6,160+10),(200-6,160+10),(200-6,160-10)],
        [(280,230),(295,230),(300,243),(280,248)],
    ]
    got_polygons=[tuple((float(x),float(y)) for x,y,*_ in e.get_points("xy"))
                  for e in added_entities if e.dxftype()=="LWPOLYLINE"]
    for expected in expected_polygons:
        shifted=tuple((x+shift_x,y+shift_y) for x,y in expected)
        if not any(len(poly)==len(shifted) and all(
                _point_close(p,*v) for p,v in zip(poly,shifted))
                for poly in got_polygons):
            raise AssertionError("WHD_MANUFACTURING_RECT_OR_PROFILE_COORDINATE_DRIFT")

    return {
        "status":"PASS",
        "scope":"real WHD manufacturing DoorPartSpec export, isolated test-only DXFs",
        "source":"official CADCraft v0.8.0 drawing from WHD commands",
        "whd_session":"Phase6HoleEditorSession.preview_all/commit_active/finish",
        "manufacturing_owner":"ae_engine.manufacturing_api.generate_part",
        "cadcraft_geometry_proof":cad_proof["status"],
        "preexisting_entities_preserved":len(before)-sum(missing.values()),
        "new_cutting_holes":len(added_entities),
        "types":sorted(e.dxftype() for e in added_entities),
        "finished_face_shift_mm":[shift_x,shift_y],
        "manufacturing_cutting_from_whd":True,
        "cadcraft_dxf_used_as_manufacturing_source":False,
        "installed_cadcraft_modified":False,
        "product_or_baseline_modified":False,
        "windows_gui_uat_completed":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cadcraft-cli",required=True,type=Path)
    p.add_argument("--work",required=True,type=Path)
    p.add_argument("--evidence",required=True,type=Path)
    args=p.parse_args()
    evidence=prove(args.cadcraft_cli,args.work)
    args.evidence.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False))


if __name__=="__main__":
    main()
