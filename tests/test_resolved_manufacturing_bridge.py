# -*- coding: utf-8 -*-
from types import SimpleNamespace

from shapely.geometry import box
import pytest

import fold_designer_bridge as bridge
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_designer_workspace import Phase6DesignerWorkspace


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


def _app(callback):
    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    return SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"],
            "active_part": "head",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0, "existing_parts": ["box_body", "head", "tail"]},
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={}, _phase6_endcap_fw_state={},
        assembly_ignore_fixed_corner_var=Var(False),
        assembly_show_interference_var=Var(True),
        assembly_relief_clearance_var=Var("0"),
    )


def test_bridge_exposes_one_resolved_manufacturing_geometry_for_single_and_assembly(monkeypatch):
    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    calls = []
    def callback(part_key, payload):
        calls.append((part_key, bool(payload.get("resolved_assembly_relief_cuts"))))
        return raw[part_key]

    app = _app(callback)
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))

    resolved = bridge._phase6_resolve_manufacturing_geometry(app)
    assert resolved.part("head").render_data is raw["head"]
    assert resolved.part("tail").render_data is raw["tail"]
    assert app._phase6_last_resolved_manufacturing_geometry is resolved

    # Single-part and assembly adapters must be readers of the same resolved object.
    single = bridge._phase6_query_final_render_data(app)
    bundle = bridge._phase6_query_assembly_render_data(app)
    assert single is resolved.part("head").render_data
    by_key = {part.part_key: part.render_data for part in bundle.assembly_parts}
    assert by_key["head"] is resolved.part("head").render_data
    assert by_key["tail"] is resolved.part("tail").render_data


def test_resolved_geometry_carries_joint_graph_and_rule_trace(monkeypatch):
    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    app = _app(lambda part_key, payload: raw[part_key])
    app._phase6_input_snapshot.update({
        "assembly_joint_schema_version": 1,
        "assembly_joints": [{
            "joint_id": "head-wrap-body",
            "subject_part": "head", "target_part": "box_body",
            "subject_region": "rear_edge", "target_region": "rear_mating",
            "relation": "WRAP", "source": "USER_ADDED",
        }],
    })
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))
    resolved = bridge._phase6_resolve_manufacturing_geometry(app)
    assert any(getattr(j, "relation", None).value == "WRAP" for j in resolved.joints)


def test_bridge_keeps_user_added_wrap_out_of_legacy_endcap_only_solver(monkeypatch):
    import ae_engine.assembly_collision as collision
    from ae_engine.sheetmetal_geometry import CornerTypeId
    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    app = _app(lambda part_key, payload: raw[part_key])
    app._phase6_assembly_type = CornerTypeId.INSERT_OVERLAY
    app._phase6_input_snapshot.update({
        "assembly_joint_schema_version": 1,
        "assembly_joints": [{
            "joint_id": "head-wrap-body", "subject_part": "head", "target_part": "box_body",
            "subject_region": "rear_edge", "target_region": "rear_mating",
            "relation": "WRAP", "source": "USER_ADDED",
        }],
    })
    seen = []
    def solver(**kwargs):
        seen.append((kwargs["endcap_placement"], kwargs.get("assembly_joint")))
        return SimpleNamespace(
            verified=False, trust_level="FAILED", rule_id=None, rule_revision=None,
            cut_polygon_2d=None, corner_reliefs=(), projections=(),
            solved_render_data=kwargs["endcap_render_data"],
            residual_projection=SimpleNamespace(pair_count=0),
            shadow_validation={"reason":"test"},
        )
    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", solver)
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0,80.0,40.0))
    bridge._phase6_resolve_manufacturing_geometry(app)
    head_joint = next(j for placement, j in seen if placement == "top")
    tail_joint = next(j for placement, j in seen if placement == "bottom")
    assert head_joint is None
    assert tail_joint is None


def test_generic_resolved_cut_can_apply_to_box_body_without_rebuilding_part_spec():
    from phase6_final_scene_view import AssemblyScenePart
    render = SimpleNamespace(scene=DrawingScene(), material=box(0,0,100,80), fold_guides=(), metadata={})
    # DrawingScene needs a CUTTING primitive for replacement to stay authoritative.
    render.scene.add_polyline([(0,0),(100,0),(100,80),(0,80)], layer="CUTTING", closed=True)
    part = AssemblyScenePart(
        part_key="box_body", render_data=render,
        x_profile=({"len":100.0,"core":True},), y_profile=({"len":80.0,"core":True},),
        placement="box_body",
    )
    solved = bridge._phase6_apply_resolved_cut_to_part(part, box(0,0,10,10))
    assert solved.part_key == "box_body"
    assert solved.render_data.material.area == pytest.approx(7900.0)
    assert solved.render_data.scene is not render.scene


def test_joint_world_geometry_builds_uv_mapped_skins_for_body_and_endcap():
    from phase6_final_scene_view import AssemblyScenePart
    body_render = SimpleNamespace(scene=DrawingScene(), material=box(0,0,100,80), fold_guides=(), metadata={})
    head_render = SimpleNamespace(scene=DrawingScene(), material=box(0,0,100,40), fold_guides=(), metadata={})
    parts = [
        AssemblyScenePart("box_body", body_render, ({"len":100.0,"core":True},), ({"len":80.0,"core":True},), "box_body"),
        AssemblyScenePart("head", head_render, ({"len":100.0,"core":True},), ({"len":40.0,"core":True},), "top"),
    ]
    geom = bridge._phase6_build_joint_world_geometry(parts, (100.0,80.0,40.0), 2.0)
    assert set(geom["flat_material_by_part"]) == {"box_body","head"}
    assert geom["mapped_skin_triangles_by_part"]["box_body"]
    assert geom["mapped_skin_triangles_by_part"]["head"]
    assert geom["world_triangles_by_part"]["head"]


def test_explicit_wrap_verified_candidate_updates_relief_target_and_serializes_state(monkeypatch):
    from types import SimpleNamespace
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from phase6_final_scene_view import AssemblyScenePart
    import ae_engine.assembly_collision as collision

    def render(material):
        scene = DrawingScene()
        minx, miny, maxx, maxy = material.bounds
        scene.add_polyline([(minx,miny),(maxx,miny),(maxx,maxy),(minx,maxy)], layer="CUTTING", closed=True)
        return SimpleNamespace(scene=scene, material=material, fold_guides=(), metadata={})

    body = AssemblyScenePart(
        "box_body", render(box(0,0,100,80)),
        ({"len":100.0,"core":True},), ({"len":80.0,"core":True},), "box_body",
    )
    head = AssemblyScenePart(
        "head", render(box(0,0,100,40)),
        ({"len":100.0,"core":True},), ({"len":40.0,"core":True},), "top",
    )
    joint = AssemblyJoint(
        joint_id="head-wrap-body-corner", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="bottom_left",
        relation=AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED,
        solver_constraints={"topology_levels": 1},
    )
    cut = box(0,0,10,12)
    projection = SimpleNamespace(
        projection=SimpleNamespace(pair_count=4, segments_2d=(((10,0),(10,12)),)),
        illegal_penetration=True, has_contact=True,
        preserve_part="head", relief_part="box_body", evidence={"source":"test"},
    )
    candidate = SimpleNamespace(
        joint_id=joint.joint_id, preserve_part="head", relief_part="box_body",
        status="CANDIDATE", projection=projection, cut_polygon_2d=cut,
        corner_relief=SimpleNamespace(measurement=SimpleNamespace(
            corner_name="bottom_left", primary_u=10.0, primary_v=12.0,
            secondary_u=None, secondary_depth=None,
        )), evidence={"source":"test"},
    )
    verification = SimpleNamespace(
        verified=True, solved_material=box(0,0,100,80).difference(cut),
        residual=SimpleNamespace(
            illegal_penetration=False, has_contact=True,
            projection=SimpleNamespace(pair_count=0, segments_2d=()),
        ),
        evidence={"pre_pair_count":4,"post_pair_count":0},
    )
    monkeypatch.setattr(collision, "discover_joint_relief_candidate", lambda *a, **k: candidate)
    monkeypatch.setattr(collision, "verify_joint_candidate_replay", lambda *a, **k: verification)
    monkeypatch.setattr(bridge, "_phase6_build_joint_world_geometry", lambda *a, **k: {
        "flat_material_by_part":{"box_body":body.render_data.material,"head":head.render_data.material},
        "mapped_skin_triangles_by_part":{"box_body":("mapped",),"head":("mapped-head",)},
        "world_triangles_by_part":{"box_body":("world-body",),"head":("world-head",)},
    })

    solved_parts, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head), (joint,), finished_dimensions=(100,80,40), sheet_thickness=2.0,
        clearance=0.0, committed_state=None,
    )
    by_key = {p.part_key:p for p in solved_parts}
    assert by_key["head"].render_data.material.area == pytest.approx(head.render_data.material.area)
    assert by_key["box_body"].render_data.material.area == pytest.approx(7880.0)
    assert diagnostics[0].candidate_status == "PROVISIONAL_3D"
    assert diagnostics[0].pre_pair_count == 4
    assert diagnostics[0].post_pair_count == 0
    item = state["items"][joint.joint_id]
    assert item["verified"] is True
    assert item["relief_part"] == "box_body"
    assert item["relation"] == "WRAP"
    assert item["cut_polygons"]


def test_explicit_wrap_unfitted_region_never_changes_material(monkeypatch):
    from types import SimpleNamespace
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from phase6_final_scene_view import AssemblyScenePart
    import ae_engine.assembly_collision as collision

    render = SimpleNamespace(scene=DrawingScene(), material=box(0,0,100,80), fold_guides=(), metadata={})
    render.scene.add_polyline([(0,0),(100,0),(100,80),(0,80)], layer="CUTTING", closed=True)
    body = AssemblyScenePart("box_body", render, ({"len":100.0,"core":True},), ({"len":80.0,"core":True},), "box_body")
    head_render = SimpleNamespace(scene=DrawingScene(), material=box(0,0,100,40), fold_guides=(), metadata={})
    head_render.scene.add_polyline([(0,0),(100,0),(100,40),(0,40)], layer="CUTTING", closed=True)
    head = AssemblyScenePart("head", head_render, ({"len":100.0,"core":True},), ({"len":40.0,"core":True},), "top")
    joint = AssemblyJoint(
        joint_id="wrap-rear", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="rear_mating",
        relation=AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED,
        solver_constraints={"topology_levels":1},
    )
    projection = SimpleNamespace(
        projection=SimpleNamespace(pair_count=3, segments_2d=(((10,0),(10,12)),)),
        illegal_penetration=True, has_contact=True,
        preserve_part="head", relief_part="box_body", evidence={},
    )
    candidate = SimpleNamespace(
        joint_id=joint.joint_id, preserve_part="head", relief_part="box_body",
        status="UNFITTED_REGION", projection=projection, cut_polygon_2d=None,
        corner_relief=None, evidence={"reason":"RELIEF_OWNER_REGION_NOT_A_STABLE_CORNER"},
    )
    monkeypatch.setattr(collision, "discover_joint_relief_candidate", lambda *a, **k: candidate)
    monkeypatch.setattr(bridge, "_phase6_build_joint_world_geometry", lambda *a, **k: {
        "flat_material_by_part":{"box_body":body.render_data.material,"head":head.render_data.material},
        "mapped_skin_triangles_by_part":{"box_body":("mapped",),"head":("mapped-head",)},
        "world_triangles_by_part":{"box_body":("world-body",),"head":("world-head",)},
    })
    solved_parts, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body,head),(joint,),finished_dimensions=(100,80,40),sheet_thickness=2.0,clearance=0.0,
    )
    assert next(p for p in solved_parts if p.part_key=="box_body").render_data.material.area == pytest.approx(8000.0)
    assert diagnostics[0].candidate_status == "UNFITTED_REGION"
    assert state["items"] == {}


def test_verified_joint_relief_state_replays_without_rediscovery_when_raw_geometry_matches(monkeypatch):
    from types import SimpleNamespace
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from phase6_final_scene_view import AssemblyScenePart
    import ae_engine.assembly_collision as collision

    def make_render(material):
        scene=DrawingScene(); minx,miny,maxx,maxy=material.bounds
        scene.add_polyline([(minx,miny),(maxx,miny),(maxx,maxy),(minx,maxy)],layer="CUTTING",closed=True)
        return SimpleNamespace(scene=scene,material=material,fold_guides=(),metadata={})
    body=AssemblyScenePart("box_body",make_render(box(0,0,100,80)),({"len":100.0,"core":True},),({"len":80.0,"core":True},),"box_body")
    head=AssemblyScenePart("head",make_render(box(0,0,100,40)),({"len":100.0,"core":True},),({"len":40.0,"core":True},),"top")
    joint=AssemblyJoint("wrap","head","box_body","rear_edge","bottom_left",AssemblyJointRelation.WRAP,source=AssemblyJointSource.USER_ADDED,solver_constraints={"topology_levels":1})
    state={"schema_version":1,"items":{"wrap":{
        "joint_id":"wrap","subject_part":"head","target_part":"box_body","relation":"WRAP","source":"USER_ADDED",
        "relief_part":"box_body","topology_levels":1,"verified":True,"trust_level":"PROVISIONAL_3D",
        "source_material_bounds":[0,0,100,80],"source_material_area":8000.0,
        "cut_polygons":[[[0,0],[10,0],[10,12],[0,12]]],"evidence":{"pre_pair_count":4,"post_pair_count":0},
    }}}
    monkeypatch.setattr(collision,"discover_joint_relief_candidate",lambda *a,**k: (_ for _ in ()).throw(AssertionError("must not rediscover")))
    solved, diagnostics, saved=bridge._phase6_resolve_explicit_joint_reliefs((body,head),(joint,),finished_dimensions=(100,80,40),sheet_thickness=2.0,committed_state=state)
    assert next(p for p in solved if p.part_key=="box_body").render_data.material.area == pytest.approx(7880.0)
    assert diagnostics[0].candidate_status == "PROVISIONAL_3D_REPLAYED"
    assert saved["items"]["wrap"]["verified"] is True


def test_verified_joint_relief_state_is_invalidated_when_raw_geometry_changes(monkeypatch):
    from types import SimpleNamespace
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from phase6_final_scene_view import AssemblyScenePart
    import ae_engine.assembly_collision as collision
    def make_render(material):
        scene=DrawingScene(); minx,miny,maxx,maxy=material.bounds
        scene.add_polyline([(minx,miny),(maxx,miny),(maxx,maxy),(minx,maxy)],layer="CUTTING",closed=True)
        return SimpleNamespace(scene=scene,material=material,fold_guides=(),metadata={})
    # Width changed to 110, so the persisted 100x80 raw fingerprint is stale.
    body=AssemblyScenePart("box_body",make_render(box(0,0,110,80)),({"len":110.0,"core":True},),({"len":80.0,"core":True},),"box_body")
    head=AssemblyScenePart("head",make_render(box(0,0,110,40)),({"len":110.0,"core":True},),({"len":40.0,"core":True},),"top")
    joint=AssemblyJoint("wrap","head","box_body","rear_edge","rear_mating",AssemblyJointRelation.WRAP,source=AssemblyJointSource.USER_ADDED,solver_constraints={"topology_levels":1})
    state={"schema_version":1,"items":{"wrap":{
        "joint_id":"wrap","subject_part":"head","target_part":"box_body","relation":"WRAP","source":"USER_ADDED",
        "relief_part":"box_body","topology_levels":1,"verified":True,"trust_level":"PROVISIONAL_3D",
        "source_material_bounds":[0,0,100,80],"source_material_area":8000.0,
        "cut_polygons":[[[0,0],[10,0],[10,12],[0,12]]],"evidence":{},
    }}}
    candidate=SimpleNamespace(
        status="UNFITTED_REGION", cut_polygon_2d=None, corner_relief=None,
        projection=SimpleNamespace(relief_part="box_body",preserve_part="head",illegal_penetration=True,has_contact=True,projection=SimpleNamespace(pair_count=1,segments_2d=())),
        evidence={"reason":"stale-recompute"},
    )
    monkeypatch.setattr(collision,"discover_joint_relief_candidate",lambda *a,**k:candidate)
    monkeypatch.setattr(bridge,"_phase6_build_joint_world_geometry",lambda *a,**k:{"flat_material_by_part":{"box_body":body.render_data.material,"head":head.render_data.material},"mapped_skin_triangles_by_part":{"box_body":("m",),"head":("h",)},"world_triangles_by_part":{"box_body":("w",),"head":("wh",)}})
    solved, diagnostics, saved=bridge._phase6_resolve_explicit_joint_reliefs((body,head),(joint,),finished_dimensions=(110,80,40),sheet_thickness=2.0,committed_state=state)
    assert next(p for p in solved if p.part_key=="box_body").render_data.material.area == pytest.approx(8800.0)
    assert diagnostics[0].candidate_status == "UNFITTED_REGION"
    assert saved["items"] == {}
