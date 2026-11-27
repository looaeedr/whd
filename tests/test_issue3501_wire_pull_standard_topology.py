# -*- coding: utf-8 -*-
"""Explicit headless first-type source; not a factory certificate or GUI test."""
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import (
    WirePullBoxSpec, BoxBodyPartSpec, ManufacturingContext, DoorPartSpec, EndCapPartSpec,
    BasePlatePartSpec, IndicatorBoxPartSpec, ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from ae_engine.cabinet_types import resolve_cabinet_type
from ae_engine.assembly_geometry import diagnose_world_mesh_triangle_edge_incidence
from ae_engine.assembly_geometry_primitives import triangle_bounds
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene


def source(t=2.):
    # Test inputs, deliberately asymmetric, not a default shop source.
    return WirePullBoxSpec(637.,411.,223.,t,27.,34.,"flat","flat",0.,0.)


@pytest.mark.parametrize("t",[1.5,3.])
def test_first_type_real_scene_fold_assembly_outside_and_mounting_faces(t):
    spec = source(t)
    result = api.resolve_standard_cabinet_topology(spec)
    assert [p.part_key for p in result.parts] == ["box_body","head","tail","lid"]
    assert result.manufacturing_verified is False
    assert [hi-lo for lo,hi in result.outside_bounds] == pytest.approx([637.,411.,223.])
    measured = triangle_bounds(tuple(tri for p in result.parts for tri in p.world_triangles))
    assert measured == result.outside_bounds
    body,head,tail,lid = result.parts
    for p in result.parts:
        assert p.render_data.metadata["stable_id"] == p.part_key
        assert p.render_data.material.equals(material_polygon_from_final_scene(p.render_data.scene))
        assert diagnose_world_mesh_triangle_edge_incidence(p.world_triangles).edges_manifold_closed
        assert p.render_data.unfolded_topology.width == pytest.approx(sum(s.length for s in p.x_profile))
    assert len(body.render_data.fold_guides) == 4
    assert tuple(g.position for g in body.render_data.fold_guides) == pytest.approx(
        [sum(row.length for row in body.x_profile[:i]) for i in range(1,5)])
    assert body.x_profile[0].length == pytest.approx(27.)
    assert body.x_profile[-1].length == pytest.approx(34.)
    b,l = triangle_bounds(body.world_triangles),triangle_bounds(lid.world_triangles)
    assert l[0][0]-b[0][0] == pytest.approx(1.)
    assert b[0][1]-l[0][1] == pytest.approx(1.)
    assert l[1][0]-b[1][0] == pytest.approx(1.)
    assert b[1][1]-l[1][1] == pytest.approx(1.)
    assert l[2][0] == pytest.approx(b[2][1])  # actual OVERLAY contact
    assert l[2][1]-l[2][0] == pytest.approx(t)
    assert [f.face_id for f in body.mounting_faces] == [
        "front_left_return","left","rear","right","front_right_return"]
    for f in (body.mounting_faces[0],body.mounting_faces[-1]):
        assert f.outward_normal == (0,0,1)
        assert f.world_origin[2] == pytest.approx(l[2][0])
        assert f.u_direction == pytest.approx((-1,0,0))
    assert head.mounting_faces[0].outward_normal == (0,1,0)
    assert tail.mounting_faces[0].outward_normal == (0,-1,0)
    assert triangle_bounds(head.world_triangles)[1][1] == pytest.approx(b[1][1])
    assert triangle_bounds(tail.world_triangles)[1][0] == pytest.approx(b[1][0])
    assert {j.relation.value for j in result.joints} == {"INSERT","OVERLAY"}
    assert len(result.joints) == 4
    # Actual inserted cap perimeter fits the body inside physical planes.
    rear,left,right = body.mounting_faces[2],body.mounting_faces[1],body.mounting_faces[3]
    for cap in (head,tail):
        cb=triangle_bounds(cap.world_triangles)
        assert cb[0][0] == pytest.approx(left.world_origin[0]+t)
        assert cb[0][1] == pytest.approx(right.world_origin[0]-t)
        assert cb[2][0] == pytest.approx(rear.world_origin[2]+t)
        assert cb[2][1] == pytest.approx(l[2][0]-t)


@pytest.mark.parametrize("change,match",[
    ({"width":True},"SOURCE_REQUIRED"),
    ({"height":float("nan")},"INVALID_DIMENSION"),
    ({"depth":float("inf")},"INVALID_DIMENSION"),
    ({"thickness":0},"INVALID_DIMENSION"),
    ({"left_return_material_mm":None},"SOURCE_REQUIRED"),
    ({"right_return_material_mm":None},"SOURCE_REQUIRED"),
    ({"head_form":None},"ENDCAP_FORM_REQUIRED"),
    ({"tail_form":"folded"},"ENDCAP_FORM_REQUIRED"),
    ({"head_clearance_mm":None},"SOURCE_REQUIRED"),
    ({"tail_clearance_mm":-1},"INVALID_DIMENSION"),
    ({"left_return_material_mm":610},"OPENING_BLOCKED"),
    ({"depth":1},"INVALID_DIMENSION"),
    ({"model_name":"unknown"},"FAMILY_SOURCE_REQUIRED"),
])
def test_missing_or_invalid_source_refused(change,match):
    with pytest.raises(ValueError,match=match):
        api.resolve_standard_cabinet_topology(replace(source(),**change))


def test_missing_support_refused():
    with pytest.raises(ValueError,match="LID_SUPPORT_MISSING"):
        api.resolve_standard_cabinet_topology(replace(source(.25),left_return_material_mm=.2))


def test_candidate_family_and_actual_render_cannot_enter_production(tmp_path):
    assert resolve_cabinet_type("WIRE_PULL").implemented is False
    result = api.resolve_standard_cabinet_topology(source())
    path = tmp_path/"out"/"lid.dxf"
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.save_part_render_data_dxf(result.part("lid").render_data,path)
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.save_resolved_manufacturing_geometry_dxf(result,path.parent)
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.generate_part(BoxBodyPartSpec(637,411,223,2,25,model_name="拉線箱"),
                          path,ManufacturingContext())
    assert not path.parent.exists()


@pytest.mark.parametrize("family", ["拉線箱", "WIRE_PULL"])
def test_no_legacy_single_part_or_structure_fallback(family):
    source_box = api.resolve_standard_cabinet_topology(source()).part("box_body")
    body = BoxBodyPartSpec(637,411,223,2,25,model_name=family,
                           fold_profile=source_box.x_profile)
    specs = (
        body,
        DoorPartSpec(637,411,2,25,model_name=family),
        EndCapPartSpec(637,223,2,25,model_name=family),
        BasePlatePartSpec(637,411,2,0,0,0,0,20,model_name=family),
        IndicatorBoxPartSpec((2,3),2,model_name=family),
    )
    for spec in specs:
        for entry in (api.build_part_scene, api.build_part_render_data,
                      api.build_operator_part_render_data):
            with pytest.raises(ValueError,match="STANDARD_CABINET_TOPOLOGY_SOURCE_REQUIRED"):
                entry(spec)
    with pytest.raises(ValueError,match="STANDARD_CABINET_TOPOLOGY_SOURCE_REQUIRED"):
        api.build_box_body_structure_render_data(body)


def test_candidate_cannot_bypass_via_verified_batch_or_composed_existing_target(tmp_path):
    result = api.resolve_standard_cabinet_topology(source())
    # Metadata-dropping adapters do not turn a preview source into production.
    render = replace(result.part("lid").render_data,metadata={})
    normal_path = tmp_path/"lid.dxf"
    composed_path = tmp_path/"combined.dxf"
    normal_path.write_bytes(b"existing single DXF")
    composed_path.write_bytes(b"existing composed DXF")
    guard_calls=[]
    def guard():
        guard_calls.append(True)
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.save_part_render_data_dxf(render,normal_path,overwrite=True,verify_reopen=True)
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.save_verified_final_scene_batch_dxf(
            (("lid",render),),tmp_path,pre_commit_guard=guard,overwrite=True)
    geometry=ResolvedManufacturingGeometry((ResolvedManufacturingPart("lid",render),))
    with pytest.raises(ValueError,match="CABINET_FAMILY_NOT_IMPLEMENTED"):
        api.save_composed_panel_dxf((("P1",geometry),),composed_path,
                                    pre_commit_guard=guard,overwrite=True)
    assert normal_path.read_bytes() == b"existing single DXF"
    assert composed_path.read_bytes() == b"existing composed DXF"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["combined.dxf","lid.dxf"]
    assert not guard_calls


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


@pytest.mark.parametrize("t",[1.5,3.])
def test_installed_shell_winding_and_cap_outward_normals(t):
    result = api.resolve_standard_cabinet_topology(source(t))
    for part in result.parts:
        # Signed tetrahedral volume from the actual installed triangles,
        # not declared face metadata or bounding boxes alone.
        volume = sum(sum(x*y for x,y in zip(a,_cross(b,c)))
                     for a,b,c in part.world_triangles)/6.
        assert volume > 0, part.part_key
    for key,axis,sign in (("head",1,1),("tail",1,-1),("lid",2,1)):
        part = result.part(key)
        bounds = triangle_bounds(part.world_triangles)
        for plane,direction in ((bounds[axis][1],1),(bounds[axis][0],-1)):
            faces = [(a,b,c) for a,b,c in part.world_triangles
                     if all(abs(p[axis]-plane)<1e-6 for p in (a,b,c))]
            assert faces
            for a,b,c in faces:
                normal = _cross(tuple(y-x for x,y in zip(a,b)),
                                tuple(y-x for x,y in zip(a,c)))
                assert normal[axis]*direction > 0, key
        assert part.mounting_faces[0].outward_normal[axis] == sign
        volume = sum(sum(x*y for x,y in zip(a,_cross(b,c)))
                     for a,b,c in part.world_triangles)/6.
        assert volume == pytest.approx(part.render_data.material.area*t)


@pytest.mark.parametrize("t", [1.5, 3.])
def test_standard_insert_without_clearance_matches_explicit_zero(t):
    omitted = api.resolve_standard_cabinet_topology(
        WirePullBoxSpec(637., 411., 223., t, 27., 34., "flat", "flat")
    )
    explicit = api.resolve_standard_cabinet_topology(source(t))
    assert omitted.joint_graph.to_dict() == explicit.joint_graph.to_dict()
    for a, b in zip(omitted.parts, explicit.parts):
        assert a.world_triangles == b.world_triangles
        assert a.render_data.material.equals(b.render_data.material)
    assert tuple(hi - lo for lo, hi in omitted.outside_bounds) == (637., 411., 223.)
    body, head, tail, lid = [triangle_bounds(p.world_triangles) for p in omitted.parts]
    for axis in (0, 1):
        assert (lid[axis][0]-body[axis][0], body[axis][1]-lid[axis][1]) == pytest.approx((1., 1.))
    assert lid[2][0] == pytest.approx(body[2][1])
    assert lid[2][1]-lid[2][0] == pytest.approx(t)
    assert all(j.clearance_policy == j.clearance_intent == "ZERO" for j in omitted.joints)


def test_legacy_explicit_clearance_is_not_labeled_zero_or_released():
    result = api.resolve_standard_cabinet_topology(
        replace(source(3.), head_clearance_mm=.5)
    )
    assert result.manufacturing_verified is False
    assert result.joints[0].clearance_policy == result.joints[0].clearance_intent == "EXPLICIT_INSERT_PERIMETER"
    assert result.joints[0].solver_constraints == {"insert_perimeter_clearance_mm": .5}
    assert result.joints[1].clearance_policy == result.joints[1].clearance_intent == "ZERO"
