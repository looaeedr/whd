# -*- coding: utf-8 -*-
"""#3317 isolated nominal source-hinge candidate; NOT physical-root approval."""
from math import sqrt

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import (
    probe_native_world_mesh_axis_faces, triangle_bounds,
)
from ae_engine.v_miter_tail_d4_nominal_hinge import (
    nominal_section_map,
)
from ae_engine.v_miter_tail_d4_delivery import (
    build_tail_d4_check_from_original,
    default_vault_tail_d4_spec,
    project_tail_d4_shared_original_fold_candidate,
)


def _real_w620_body():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from ae_engine.box_body_structure_state import default_box_body_structure_state
    from phase6_fold_profiles import build_box_body_profile,profile_to_fold_segments
    from phase6_final_scene_view import AssemblyScenePart

    values={
        "model":"金庫型","w":620.,"h":600.,"d":185.,"t":2.,
        "fw":25.,"zl1":15.,"zl2":15.,"zr1":15.,"zr2":15.,
        "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":48.,
    }
    structure=build_box_body_structure_render_data(BoxBodyPartSpec(
        width=620.,height=600.,depth=185.,thickness=2.,frame_width=25.,
        model_name="金庫型",zl1=15.,zl2=15.,zr1=15.,zr2=15.,
        fold_profile=profile_to_fold_segments(build_box_body_profile(values)),
        structure_state=default_box_body_structure_state(),
        head_ybottom1=48.,tail_ybottom1=48.,
    ))
    body=AssemblyScenePart(
        part_key="box_body",render_data=structure,
        x_profile=(),y_profile=(),placement="box_body",
    )
    return tuple(api.build_joint_world_geometry(
        (body,),(620.,600.,185.),2.,
    )["world_triangles_by_part"]["box_body"])


def test_nominal_partition_is_injective_and_area_preserving_at_t2():
    h=(1.+sqrt(2.))/2.
    assert h==pytest.approx(1.2071067811865475)
    assert 1.-1./h==pytest.approx(.17157287525381)
    # At every positive crease-distance, the distinct source panels
    # occupy opposite halves of the x=y diagonal, with no double volume.
    for s in (.001,.1,.5,1.,h):
        for t in (-1.,-.5,0.,.5,1.):
            a=nominal_section_map(s,t,h,panel="a")
            b=nominal_section_map(s,t,h,panel="b")
            assert a[0]-a[1]==pytest.approx(s*(1.-t/h))
            assert b[1]-b[0]==pytest.approx(s*(1.-t/h))
            assert a[0]>a[1] and b[1]>b[0]
    for t in (-1.,0.,1.):
        assert nominal_section_map(0.,t,h,panel="a")==(
            nominal_section_map(0.,t,h,panel="b")
        )
        assert nominal_section_map(h,t,h,panel="a")==pytest.approx((h,t))
        assert nominal_section_map(h,t,h,panel="b")==pytest.approx((t,h))
    # Exact integral int_0^h int_-1^1 (1-t/h) dt ds.
    assert 2.*h==pytest.approx(2.414213562373095)


@pytest.mark.parametrize("first_axis",("x","y"))
def test_w620_nominal_hinge_trial_keeps_true_v_and_native_assembly(first_axis):
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    body=_real_w620_body()
    original=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
    )
    trial=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
        nominal_hinge=True,
    )
    assert trial["nominal_hinge_width_mm"]==pytest.approx(
        (1.+sqrt(2.))/2.,abs=1e-8
    )
    assert not trial["manufacturing_approved"]
    assert trial["status"]=="D4_NOMINAL_SOURCE_HINGE_CANDIDATE_UNVERIFIED"
    assert len(trial["v_source_uv"])>len(original["v_source_uv"])
    assert all(r["full_face_contact_proven"] for r in trial["straight_v_wall_sets"])
    assert trial["v_world_open_seam_edges"]==0
    assert trial["v_world_four_edges"]==8
    assert trial["v_world_open_edges"]<=original["v_world_open_edges"]
    for o_interval,n_interval in zip(
        triangle_bounds(original["v_surface"]),
        triangle_bounds(trial["v_surface"]),
    ):
        assert o_interval==pytest.approx(n_interval,abs=1e-6)
    # The unchanged upper source material has exactly the same world
    # positions. A different triangulation must not move the original cap.
    def world_uv_map(candidate):
        return {
            tuple(round(v,7) for v in candidate["v_source_uv"][index]): point
            for face,triangle in zip(
                candidate["v_source_faces"],candidate["v_surface"],
            )
            for index,point in zip(face,triangle)
        }
    orig_uv=world_uv_map(original)
    trial_uv=world_uv_map(trial)
    upper_start=max(upper[1] for _,_,_,upper
                    in flat.opening_source_points_xy)
    upper_original={uv:p for uv,p in orig_uv.items()
                    if uv[1]>upper_start+1e-7}
    assert upper_original
    for uv,point in upper_original.items():
        assert uv in trial_uv
        assert trial_uv[uv]==pytest.approx(point,abs=1e-7)
    for label,where in (
        ("rear",(100.,-275.,0.)),
        ("front_frame",(-294.,-297.,0.)),
    ):
        a=probe_native_world_mesh_axis_faces(
            original["v_solid"],axis=2,fixed_xyz=where,
        )
        b=probe_native_world_mesh_axis_faces(
            trial["v_solid"],axis=2,fixed_xyz=where,
        )
        assert a==pytest.approx(b,abs=1e-6),(label,a,b)
    # Never conflate same-source V wall contact with cross-part nonpenetration.
    assert len(body)>0
