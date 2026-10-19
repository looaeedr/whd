"""#1959 native CADCraft DXF -> *original* WHD Session draft / cancel / confirm trial.

The DXF already came from the official CADCraft CLI using WHD instructions.
This script only proves reversible WHD Session staging after independent
geometry verification. It never writes WHD manufacturing data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, ProfileFeature, RectFeature, Vec2,
    feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_command_session_bridge import stage_verified_cadcraft_drawing
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


def demo_source_features():
    return (
        CircleFeature(diameter=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(25,30), layer="CUTTING"),
        RectFeature(width=20,height=12, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(70,45),layer="CUTTING",rotation_deg=90),
        ProfileFeature(points=(Vec2(-20,5), Vec2(-7,4), Vec2(-5,16), Vec2(-24,20)),
                       anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       offset=Vec2(0,0),layer="CUTTING"),
    )


def prove_session_draft(output: Path) -> dict:
    surface=feature_surface_from_rect("1959-demo", Vec2(-100,-100), Vec2(200,200))
    source=demo_source_features()
    previous=CircleFeature(diameter=4,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                           offset=Vec2(-70,-70),layer="CUTTING")
    current=[previous]
    identity=id(current)
    session=Phase6HoleEditorSession("1959-safe-trial",current)
    pending=stage_verified_cadcraft_drawing(
        output=output,whd_candidates=source,session=session,
        surface=surface,width=300,height=300)
    preview_ok=len(current)==4 and session.has_active_edit
    pending.cancel()
    cancel_ok=(current==[previous] and not session.has_active_edit and id(current)==identity)
    pending=stage_verified_cadcraft_drawing(
        output=output,whd_candidates=source,session=session,
        surface=surface,width=300,height=300)
    pending.confirm()
    confirmed_ok=(len(current)==4 and not session.has_active_edit
                  and session.snapshot().undo_depth==1)
    session.execute(HoleEditorAction.undo())
    undo_ok=(current==[previous] and id(current)==identity)
    success=preview_ok and cancel_ok and confirmed_ok and undo_ok
    report={
        "kind":"ISSUE1959_NATIVE_CADCRAFT_OUTPUT_TO_ORIGINAL_WHD_SESSION",
        "status":"PASS" if success else "FAIL",
        "actual_file":output.name,
        "candidate_count":len(source),
        "old_feature_count":1,
        "preview":preview_ok,"cancel":cancel_ok,
        "confirm":confirmed_ok,"undo":undo_ok,
        "manufacturing_dxf_written":False,
        "gui_button_integrated":False,
        "scope":"isolated actual CADCraft DXF, existing WHD Phase6HoleEditorSession",
    }
    if not success:
        raise AssertionError(json.dumps(report))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True,type=Path)
    parser.add_argument("--evidence",required=True,type=Path)
    args=parser.parse_args()
    proof=prove_session_draft(args.input)
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False))


if __name__=="__main__":
    main()
