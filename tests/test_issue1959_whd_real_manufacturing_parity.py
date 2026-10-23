"""#1959 canonical WHD manufacturing mirror and CUTTING invariants.

Protect the real production Door exporter independently of external CADCraft,
whose v0.8.0 executable is exercised by the dedicated native CLI workflow.
"""
from collections import Counter

import ezdxf

from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import generate_part
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, RectFeature, ProfileFeature, Vec2,
)
from tools.issue1959_whd_real_manufacturing_parity import _signature


def test_whd_real_door_manufacturing_mirrors_finished_face_x_and_keeps_old_cutting(tmp_path):
    # This source convention is implemented in ae_door_indicator.export_door_dxf:
    # mirror_drawing_scene_x(scene, 0, blank_width) is REQUIRED.
    old=CircleFeature(diameter=8,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(320,350),layer="CUTTING")
    new=(
        CircleFeature(diameter=10,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(110,130),layer="CUTTING"),
        RectFeature(width=20,height=12,rotation_deg=90,
                    anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    offset=Vec2(200,160),layer="CUTTING"),
        ProfileFeature(points=(Vec2(280,230),Vec2(295,230),
                               Vec2(300,243),Vec2(280,248)),
                       anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       offset=Vec2(0,0),layer="CUTTING"),
    )
    common=dict(width=500,height=600,thickness=2,frame_width=25,
                gap_w=3.5,gap_h=3.5,fold_left=19,fold_right=19,
                fold_top=19,fold_bottom=19)
    root=tmp_path/"authority";root.mkdir()
    context=ManufacturingContext(resource_root=root,draw_stock=False)
    baseline=tmp_path/"original-door.dxf"
    confirmed=tmp_path/"confirmed-door.dxf"
    generate_part(DoorPartSpec(**common,features=(old,)),baseline,context)
    generate_part(DoorPartSpec(**common,features=(old,*new)),confirmed,context)
    a=list(ezdxf.readfile(baseline).modelspace())
    b=list(ezdxf.readfile(confirmed).modelspace())
    before=Counter(_signature(e) for e in a)
    after=Counter(_signature(e) for e in b)
    assert before-after==Counter(), "existing CUTTING/BEND/other primitives changed"
    assert sum((after-before).values())==3
    remaining=before.copy()
    added=[]
    for e in b:
        key=_signature(e)
        if remaining[key]:
            remaining[key]-=1
        else:
            added.append(e)
    assert sorted(e.dxftype() for e in added)==["CIRCLE","LWPOLYLINE","LWPOLYLINE"]
    assert {e.dxf.layer for e in added}=={"CUTTING"}
    assert all(e.closed for e in added if e.dxftype()=="LWPOLYLINE")
    c=next(e for e in added if e.dxftype()=="CIRCLE")
    # Finished-face left is +17, blank width is 469, output X mirrors.
    assert c.dxf.center.x==342
    assert c.dxf.center.y==147
    assert c.dxf.radius==5


def test_manufacturing_export_never_imports_cadcraft_source_file(tmp_path):
    # Preserve the explicit distinction between the CADCraft proof DXF and
    # canonical WHD generated part. No CADCraft file is supplied to exporter.
    root=tmp_path/"authority";root.mkdir()
    spec=DoorPartSpec(
        width=500,height=600,thickness=2,frame_width=25,
        gap_w=3.5,gap_h=3.5,
        fold_left=19,fold_right=19,fold_top=19,fold_bottom=19,
        features=(CircleFeature(diameter=10,
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(110,130),layer="CUTTING"),),
    )
    save_path=tmp_path/"WHD-door-only.dxf"
    assert not save_path.exists()
    receipt=generate_part(
        spec,save_path,ManufacturingContext(resource_root=root,draw_stock=False))
    assert save_path.is_file()
    assert receipt.exporter_name=="export_door_dxf"
    assert receipt.used_baseline is False
    assert any(e.dxftype()=="CIRCLE" and e.dxf.layer=="CUTTING"
               for e in ezdxf.readfile(save_path).modelspace())



def test_original_whd_project_file_roundtrips_cadcraft_approved_cutting_features(tmp_path):
    """Project .p6fold is authority, never the disposable CADCraft DXF."""
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

    features = (
        CircleFeature(8, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      Vec2(320, 350), layer="CUTTING"),
        CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      Vec2(110, 130), layer="CUTTING"),
        RectFeature(20, 12, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                    Vec2(200, 160), rotation_deg=90, layer="CUTTING"),
        ProfileFeature((Vec2(280, 230), Vec2(295, 230),
                        Vec2(300, 243), Vec2(280, 248)),
                       FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       Vec2(0, 0), layer="CUTTING"),
    )
    path = write_project(tmp_path / "confirmed-door.p6fold", {
        "schema": PROJECT_SCHEMA,
        "snapshot": {
            "model": "金庫型",
            "part_features": {"door": list(features)},
            "existing_parts": ["door"],
            "active_part": "door",
        },
        "final_geometry": {"must_not_survive": True},
    })
    loaded = read_project(path)
    restored = tuple(loaded["snapshot"]["part_features"]["door"])
    assert restored == features
    assert restored[0] is not features[0]
    assert [type(f) for f in restored] == [type(f) for f in features]
    assert loaded["final_geometry"] == {}

    specs = dict(width=500, height=600, thickness=2, frame_width=25,
                 gap_w=3.5, gap_h=3.5,
                 fold_left=19, fold_right=19, fold_top=19, fold_bottom=19)
    root = tmp_path / "authority"
    root.mkdir()
    context = ManufacturingContext(resource_root=root, draw_stock=False)
    before = tmp_path / "before-reload.dxf"
    after = tmp_path / "after-reload.dxf"
    generate_part(DoorPartSpec(**specs, features=features), before, context)
    generate_part(DoorPartSpec(**specs, features=restored), after, context)
    a = Counter(_signature(e) for e in ezdxf.readfile(before).modelspace())
    b = Counter(_signature(e) for e in ezdxf.readfile(after).modelspace())
    assert a == b
    assert any(kind == "CIRCLE" and layer == "CUTTING" for kind, layer, _ in b)
