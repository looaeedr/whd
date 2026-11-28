from dataclasses import replace

import pytest
from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def test_rear_source_replay_cancel(tmp_path):
    spec = WirePullBoxSpec(637,411,223,3)
    body = api.resolve_standard_cabinet_topology(spec).part("box_body")
    rear = next(face for face in body.mounting_faces if face.face_id == "rear")
    left,bottom,right,top = rear.flat_bounds
    x,y = (left+right)/2,(bottom+top)/2
    hole = CircleFeature(4,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(x+65,y))
    mark = replace(hole,layer="MARKING",offset=Vec2(x-65,y))
    manual = (("box_body",(hole,mark)),)
    original = api.propose_wire_pull_holes(spec,manual=manual)
    def topology(p):
        return api.confirm_wire_pull_hole_topology(spec,p,manual=p.manual)
    before = topology(original)
    bounds = (x-50,y-40,x+50,y+40)
    updated = api.set_wire_pull_rear_opening(original,flat_bounds=bounds)
    def reopen(name, proposal):
        path = write_project(tmp_path/name,{"schema":PROJECT_SCHEMA,
                             "snapshot":api.build_wire_pull_project_snapshot(spec,proposal)})
        return path, api.restore_wire_pull_project_snapshot(read_project(path)["snapshot"])[0]
    path, replay = reopen("opened.p6fold",updated)
    assert updated == replay
    after = topology(replay)
    assert after.outside_bounds == before.outside_bounds and after.joint_graph == before.joint_graph
    for key in ("head","tail","lid"):
        assert after.part(key) == before.part(key)
    assert after.part("box_body").mounting_faces == before.part("box_body").mounting_faces
    assert after.part("box_body").render_data.fold_guides == before.part("box_body").render_data.fold_guides
    assert before.part("box_body").render_data.material.area-after.part("box_body").render_data.material.area == pytest.approx(8000)
    assert dict(replay.manual)["box_body"][:2] == (hole,mark)
    export = api.inspect_wire_pull_saved_export(path)
    assert export.manufacturing_blocker == "WIRE_PULL_REAR_COVER_JOINT_UNVERIFIED"
    with pytest.raises(ValueError,match="JOINT_UNVERIFIED"):
        api.save_wire_pull_saved_project_dxf(path,tmp_path/"dxf",expected_source_sha256=export.source_sha256)
    assert not list(tmp_path.rglob("*.dxf"))
    for bad in ((x-70,y-40,x+50,y+40),(x-50,y-40,x+70,y+40),(left-5,y,left+10,y+5)):
        with pytest.raises(ValueError,match="MATERIAL_CONFLICT"):
            api.set_wire_pull_rear_opening(replay,flat_bounds=bad)
    _, cancelled = reopen("cancelled.p6fold",api.set_wire_pull_rear_opening(replay,flat_bounds=None))
    assert cancelled == original and topology(cancelled) == before
