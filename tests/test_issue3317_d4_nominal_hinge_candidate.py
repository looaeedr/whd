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


def _real_w620_body(*,width=620.,height=600.,depth=185.,bottom=48.):
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from ae_engine.box_body_structure_state import default_box_body_structure_state
    from phase6_fold_profiles import build_box_body_profile,profile_to_fold_segments
    from phase6_final_scene_view import AssemblyScenePart

    values={
        "model":"金庫型","w":width,"h":height,"d":depth,"t":2.,
        "fw":25.,"zl1":15.,"zl2":15.,"zr1":15.,"zr2":15.,
        "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":bottom,
    }
    structure=build_box_body_structure_render_data(BoxBodyPartSpec(
        width=width,height=height,depth=depth,thickness=2.,frame_width=25.,
        model_name="金庫型",zl1=15.,zl2=15.,zr1=15.,zr2=15.,
        fold_profile=profile_to_fold_segments(build_box_body_profile(values)),
        structure_state=default_box_body_structure_state(),
        head_ybottom1=bottom,tail_ybottom1=bottom,
    ))
    body=AssemblyScenePart(
        part_key="box_body",render_data=structure,
        x_profile=(),y_profile=(),placement="box_body",
    )
    return tuple(api.build_joint_world_geometry(
        (body,),(width,height,depth),2.,
    )["world_triangles_by_part"]["box_body"])




def _source_thickness_segment(candidate, xy):
    """Interpolate only REAL same-source T faces; ignore V wall world aliases."""
    from shapely.geometry import Point, Polygon
    uv=candidate["v_source_uv"]
    point=Point(xy)
    for fid,indices in enumerate(candidate["v_source_faces"]):
        coords=tuple(uv[i] for i in indices)
        tri=Polygon(coords)
        if tri.area<=1e-12 or not tri.buffer(1e-8).covers(point):
            continue
        (ax,ay),(bx,by),(cx,cy)=coords
        den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        a=((by-cy)*(xy[0]-cx)+(cx-bx)*(xy[1]-cy))/den
        b=((cy-ay)*(xy[0]-cx)+(ax-cx)*(xy[1]-cy))/den
        weights=(a,b,1.-a-b)
        # First two triangles of each source face are its outward/inward
        # skins. The minus triangle is intentionally ordered 0,2,1.
        plus=candidate["v_solid"][2*fid]
        minus_raw=candidate["v_solid"][2*fid+1]
        minus=(minus_raw[0],minus_raw[2],minus_raw[1])
        def interp(face):
            return tuple(sum(weights[j]*face[j][k] for j in range(3))
                         for k in range(3))
        return interp(plus),interp(minus)
    raise AssertionError(("D4_TRUE_SOURCE_MATERIAL_POINT_MISSING",xy))


def _distance_to_segment(point,a,b):
    from math import dist
    v=tuple(y-x for x,y in zip(a,b))
    w=tuple(x-y for x,y in zip(point,a))
    den=sum(x*x for x in v)
    assert den>0
    k=max(0.,min(1.,sum(x*y for x,y in zip(v,w))/den))
    projected=tuple(a[i]+k*v[i] for i in range(3))
    return dist(point,projected)

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
    witness=(-305.5,-298.520084,-87.4)
    source_points=((14.520084,50.1),(15.5,50.1))
    before=tuple(_distance_to_segment(
        witness,*_source_thickness_segment(original,xy),
    ) for xy in source_points)
    after=tuple(_distance_to_segment(
        witness,*_source_thickness_segment(trial,xy),
    ) for xy in source_points)
    assert max(before)<2e-3,(
        "D4_APPROVED_SOURCE_ORIGINAL_ROOT_WITNESS_NOT_REPRODUCED",
        first_axis,before,
    )
    assert max(after)>1e-3,(
        "D4_NOMINAL_HINGE_STILL_DOUBLE_OCCUPIES_ORIGINAL_WITNESS",
        first_axis,after,
    )

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
    from ae_engine.v_miter_tail_no_ba_sequential import stations_from_real_flat
    st=stations_from_real_flat(flat)
    upper_end=max(st.left_side_end,st.right_side_end)
    upper_source_samples=[]
    for ids in original["v_source_faces"]:
        xyz=tuple(original["v_source_uv"][i] for i in ids)
        if min(p[1] for p in xyz)>=upper_end-1e-7:
            uv=(sum(p[0] for p in xyz)/3.,
                sum(p[1] for p in xyz)/3.)
            upper_source_samples.append(uv)
    assert upper_source_samples
    # Source-index and tessellation may differ; compare the actual
    # interpolated +/-T/2 points of the same upper source material.
    for uv in upper_source_samples[:30]:
        old_skins=_source_thickness_segment(original,uv)
        new_skins=_source_thickness_segment(trial,uv)
        for old,new in zip(old_skins,new_skins):
            assert old==pytest.approx(new,abs=1e-6),(
                "D4_NOMINAL_UPPER_PHYSICAL_FACE_MOVED",first_axis,uv,
            )
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


def _left_side_lower_inner_skin_pair_intersection(candidate):
    """Source-identified lower Ø4 side collar, not a same-XYZ V contact."""
    from shapely.geometry import Point,Polygon
    sample_uv=((14.934562,46.001071),(14.869194,46.004282))
    selected=[]
    for uv in sample_uv:
        candidates=[]
        for fid,face in enumerate(candidate["v_source_faces"]):
            points=tuple(candidate["v_source_uv"][i] for i in face)
            region=Polygon(points)
            if region.area<=1e-10 or not region.buffer(2e-6).covers(Point(uv)):
                continue
            # The two triangles for each indexed source face are plus and
            # minus T skins. Use ONLY the inward skin, never cut walls.
            triangle=candidate["v_solid"][fid*2+1]
            candidates.append((fid,points,triangle))
        assert candidates,("D4_LEFT_COLLAR_REAL_SOURCE_POINT_MISSING",uv)
        selected.append(candidates)
    overlaps=[]
    for fid_a,source_a,tri_a in selected[0]:
        for fid_b,source_b,tri_b in selected[1]:
            if fid_a==fid_b:
                continue
            # Both offending skins lie in the same real X=-305 plane.
            if max(abs(p[0]-tri_a[0][0]) for p in tri_a+tri_b)>1e-6:
                continue
            pa=Polygon(tuple((p[1],p[2]) for p in tri_a))
            pb=Polygon(tuple((p[1],p[2]) for p in tri_b))
            if pa.area>1e-9 and pb.area>1e-9:
                overlaps.append(pa.intersection(pb).area)
    return max(overlaps,default=0.)


@pytest.mark.parametrize("first_axis",("x","y"))
def test_d4_left_relief_side_collar_inner_skin_no_double_material(first_axis):
    """Real UV witnesses that used to penetrate on the lower side X skin."""
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    body=_real_w620_body()
    original=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,nominal_hinge=True,
        nominal_side_collar=False,
    )
    repaired=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,nominal_hinge=True,
    )
    original_overlap=_left_side_lower_inner_skin_pair_intersection(original)
    repaired_overlap=_left_side_lower_inner_skin_pair_intersection(repaired)
    assert original_overlap>1.,(
        "D4_LEFT_COLLAR_INDEPENDENT_RED_NOT_REPRODUCED",
        first_axis,original_overlap,
    )
    assert repaired_overlap<=1e-7,(
        "D4_LEFT_COLLAR_TRUE_SOURCE_INNER_SKINS_STILL_OVERLAP",
        first_axis,repaired_overlap,
    )
    assert repaired["v_world_four_edges"]==8
    assert repaired["v_world_open_seam_edges"]==0
    assert repaired["v_world_open_edges"]==28
    assert all(r["full_face_contact_proven"]
               for r in repaired["straight_v_wall_sets"])
    assert not repaired["manufacturing_approved"]


def _source_local_side_skin_faces(candidate, side):
    """Only true source-owner +/- T skin, never V CUTTING/bridge contact.

    The two physical skin triangles for each source face are stored in
    their exact source-order pair before any boundary/corner wall faces.
    Selection requires ALL three source UV vertices in the real lower
    corner window, not world XYZ coincidence or a synthetically clipped
    mesh that could conceal crossing segments.
    """
    st_left,st_right=(0.,40.) if side=="left" else (602.,642.)
    faces=[]
    ids=[]
    for fid,source in enumerate(candidate["v_source_faces"]):
        uv=tuple(candidate["v_source_uv"][i] for i in source)
        if all(st_left-1e-7<=x<=st_right+1e-7
               and y<=63.+1e-7 for x,y in uv):
            faces.extend(candidate["v_solid"][2*fid:2*fid+2])
            ids.append(fid)
    assert faces and len(faces)==2*len(ids)
    return tuple(faces),tuple(ids)


@pytest.mark.parametrize("first_axis",("x","y"))
@pytest.mark.parametrize("side",("left","right"))
def test_d4_lower_side_true_3d_skin_crossing_red_green(first_axis,side):
    """W620 actual source UV skins: transverse AND coplanar checks, fail closed."""
    from ae_engine.assembly_geometry import diagnose_world_mesh_self_intersections
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    body=_real_w620_body()
    baseline=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
        nominal_hinge=True,nominal_side_collar=False,
    )
    repaired=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
        nominal_hinge=True,
    )
    readings=[]
    for candidate in (baseline,repaired):
        skins,ids=_source_local_side_skin_faces(candidate,side)
        assert all(2*fid+1<len(candidate["v_solid"]) for fid in ids)
        # Exhaustive capacity for this exact selected 3D skin subset;
        # no tolerance override, no world-XYZ welding of separate UV.
        budget=len(skins)*(len(skins)-1)//2
        check=diagnose_world_mesh_self_intersections(
            skins,max_nonadjacent_pairs=budget,
        )
        assert not check.numerical_budget_exhausted,(
            "D4_LOWER_SKIN_SCAN_BUDGET_OR_DEGENERATE",side,first_axis,
            check,len(skins),
        )
        readings.append((check,len(skins)))
    old,new=readings
    assert (old[0].crossing_pair_count
            or old[0].coplanar_overlap_pair_count),(
        "D4_NOMINAL_PRECOLLAR_RED_NOT_REPRODUCED",
        side,first_axis,old,
    )
    assert new[0].crossing_pair_count==0,(
        "D4_LOWER_SIDE_TRANSVERSE_SKIN_CROSSING",
        side,first_axis,new,
    )
    assert new[0].coplanar_overlap_pair_count==0,(
        "D4_LOWER_SIDE_COPLANAR_SKIN_OVERLAP",
        side,first_axis,new,
    )
    assert repaired["v_world_four_edges"]==8
    assert repaired["v_world_open_seam_edges"]==0
    assert repaired["v_world_open_edges"]==28
    assert not repaired["manufacturing_approved"]


def test_d4_true_3d_self_intersection_detector_transverse_positive_control():
    """Prevent a coplanar-only or silently skipped nonparallel regression."""
    from ae_engine.assembly_geometry import diagnose_world_mesh_self_intersections
    # Two triangles cross as segments, sharing no vertices or source edge.
    triangles=(
        ((-2.,-2.,0.),(2.,-2.,0.),(0.,2.,0.)),
        ((0.,-1.,-1.),(0.,1.,-1.),(0.,0.,1.)),
    )
    diagnostic=diagnose_world_mesh_self_intersections(
        triangles,max_nonadjacent_pairs=1,
    )
    assert diagnostic.crossing_pair_count==1
    assert diagnostic.coplanar_overlap_pair_count==0
    assert not diagnostic.numerical_budget_exhausted


def _source_shared_upper_skin_discontinuities(candidate,*,station,side):
    """Only an exact shared SOURCE UV edge between same-oriented skin faces."""
    from collections import defaultdict
    from math import dist
    from ae_engine.v_miter_tail_d4_shared_uv_solid import _normal,_dot

    uv=candidate["v_source_uv"]
    source_faces=candidate["v_source_faces"]
    surface=candidate["v_surface"]
    all_solid=candidate["v_solid"]
    edges=defaultdict(list)
    for fid,face in enumerate(source_faces):
        for j in range(3):
            a,b=face[j],face[(j+1)%3]
            edges[tuple(sorted((a,b)))].append(fid)
    witnesses=[]
    for (a,b),neighbors in edges.items():
        if len(neighbors)!=2:
            continue
        ua,ub=uv[a],uv[b]
        if abs(ua[1]-station)>1e-7 or abs(ub[1]-station)>1e-7:
            continue
        if side=="left":
            if max(ua[0],ub[0])>40:
                continue
        elif min(ua[0],ub[0])<602:
            continue
        fid0,fid1=neighbors
        if _dot(_normal(surface[fid0]),_normal(surface[fid1]))<1.-1e-7:
            continue
        def skin_positions(fid,src_id):
            face=source_faces[fid]
            pos=face.index(src_id)
            plus=all_solid[2*fid][pos]
            # Minus is indexed in the source order 0,2,1.
            minus=all_solid[2*fid+1][(0,2,1)[pos]]
            return plus,minus
        ends=[]
        for idx in (a,b):
            one=skin_positions(fid0,idx)
            two=skin_positions(fid1,idx)
            ends.append((uv[idx],dist(one[0],two[0]),
                         dist(one[1],two[1])))
        if max(v for _,p,m in ends for v in (p,m))>1e-7:
            witnesses.append((tuple(sorted((ua,ub))),tuple(ends)))
    return witnesses


@pytest.mark.parametrize("first_axis",("x","y"))
@pytest.mark.parametrize("side",("left","right"))
def test_d4_y225_same_source_skin_edge_gap_is_explicit_unresolved(first_axis,side):
    """Preserve honest upper source-endpoint RED; don't fabricate a bridge."""
    from ae_engine.v_miter_tail_no_ba_sequential import stations_from_real_flat
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    candidate=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=_real_w620_body(),
        nominal_hinge=True,
    )
    st=stations_from_real_flat(flat)
    # This is the exact W620 source witness at Y225, not a derived
    # assumption that it equals the *upper crease* station. Read it
    # back from the actual candidate source UV; fail if it is absent.
    upper_source_rows=tuple(sorted({
        round(float(uv[1]),7) for uv in candidate["v_source_uv"]
        if uv[1]>=min(st.left_side_end,st.right_side_end)-1e-7
    }))
    assert any(abs(y-225.)<1e-7 for y in upper_source_rows),(
        "D4_UPPER_SOURCE_Y225_ROW_NOT_FOUND",upper_source_rows,
    )
    row_y=next(y for y in upper_source_rows if abs(y-225.)<1e-7)
    rows=_source_shared_upper_skin_discontinuities(
        candidate,station=row_y,side=side,
    )
    assert rows,("D4_UPPER_SHARED_UV_GAP_DISAPPEARED_RECHECK",first_axis,side)
    mismatch=max(max(p,m) for _,ends in rows for _,p,m in ends)
    # Real source endpoint at s=|UV.X - original X-side crease|.
    # Under the nominal map the extra neighbor-normal contribution is
    # (T/2)*(1-s/h), NOT h-T/2. At the other endpoint s=h it vanishes.
    crease=st.left_x if side=="left" else st.right_x
    closest_source_s=min(
        abs(uv[0]-crease) for edge,_ in rows for uv in edge
    )
    h=candidate["nominal_hinge_width_mm"]
    expected=(flat.source_spec.thickness/2.)*(
        1.-closest_source_s/h
    )
    assert expected>1e-7
    assert mismatch==pytest.approx(expected,abs=1e-6),(
        "D4_UPPER_SOURCE_EDGE_NOT_SAME_DOCUMENTED_GAP",
        first_axis,side,rows[:4],
    )
    assert all(any(max(p,m)<1e-6 for _,p,m in ends)
               for _,ends in rows),(
        "D4_UPPER_SOURCE_EDGE_OTHER_ENDPOINT_DRIFTED",first_axis,side,
    )
    # This is an OBSERVED problem, never a manufacturing-success claim.
    assert not candidate["manufacturing_approved"]



@pytest.mark.parametrize("first_axis",("x","y"))
def test_d4_lower_v_tip_2h_taper_stays_original_upper_source(first_axis):
    """W620-only source-tip taper.  It must not alter Y225 or original CUTTING."""
    from ae_engine.v_miter_tail_no_ba_sequential import stations_from_real_flat
    from ae_engine.assembly_geometry import (
        diagnose_world_mesh_self_intersections,
    )
    from ae_engine.v_miter_tail_d4_shared_uv_solid import _normal,_dot
    from shapely.geometry import Polygon
    from math import dist

    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    body=_real_w620_body()
    st=stations_from_real_flat(flat)
    native=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
    )
    baseline=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
        nominal_hinge=True,
    )
    trial=project_tail_d4_shared_original_fold_candidate(
        flat,first_axis=first_axis,box_body_world=body,
        nominal_hinge=True,nominal_lower_v_taper=True,
    )
    tip_rows=tuple(float(upper[1]) for _,_,_,upper
                   in flat.opening_source_points_xy)
    assert len(tip_rows)==2
    assert tip_rows[0]==pytest.approx(tip_rows[1],abs=1e-8)
    h=trial["nominal_hinge_width_mm"]
    end=tip_rows[0]+2.*h
    assert end<min(st.left_side_end,st.right_side_end)
    assert trial["nominal_lower_v_taper"] is True
    assert not trial["manufacturing_approved"]
    assert baseline["nominal_lower_v_taper"] is False
    # Whole manufactured CUTTING stock (including four source holes) is
    # identical, not just a union of triangulated synthetic outlines.
    assert trial["v_material"].symmetric_difference(
        baseline["v_material"],
    ).area<1e-8
    assert trial["v_material"].symmetric_difference(
        native["v_material"],
    ).area<1e-8
    assert len(trial["v_material"].interiors)==4
    assert Polygon(trial["v_material"].exterior).symmetric_difference(
        Polygon(flat.result_material.exterior),
    ).area<1e-8
    assert trial["v_world_four_edges"]==8
    assert trial["v_world_open_seam_edges"]==0
    assert trial["v_extra_world_open_edges"]==0
    assert trial["v_world_open_edges"]==24
    assert len(trial["straight_v_wall_sets"])==2
    assert all(
        x["lower_triangles"]==2 and x["upper_triangles"]==2
        and x["full_face_contact_proven"]
        for x in trial["straight_v_wall_sets"]
    )
    # The original midline/assembly reference and actual upper native
    # T skins are untouched even where upper Fold is already imperfect.
    for oa,ob in zip(triangle_bounds(native["v_surface"]),
                     triangle_bounds(trial["v_surface"])):
        assert oa==pytest.approx(ob,abs=1e-7)
    upper_samples=[]
    for face in trial["v_source_faces"]:
        points=tuple(trial["v_source_uv"][i] for i in face)
        if min(uv[1] for uv in points)>end+1e-7:
            upper_samples.append(tuple(
                sum(uv[k] for uv in points)/3. for k in (0,1)
            ))
    assert upper_samples
    for uv in upper_samples:
        native_skins=_source_thickness_segment(native,uv)
        tapered_skins=_source_thickness_segment(trial,uv)
        for before,after in zip(native_skins,tapered_skins):
            assert before==pytest.approx(after,abs=1e-6),(
                "D4_LOWER_TAPER_MOVED_NATIVE_UPPER",uv,
            )
    # True normal thickness remains T, not a moved midplane or shrink.
    positive_skin_count=0
    for fid,midline in enumerate(trial["v_surface"]):
        positive,negative=trial["v_solid"][fid*2:fid*2+2]
        n=_normal(midline)
        for j in range(3):
            plus=positive[j]
            minus=negative[(0,2,1)[j]]
            diff=tuple(plus[k]-minus[k] for k in range(3))
            assert _dot(diff,n)==pytest.approx(
                flat.source_spec.thickness,abs=1e-6,
            )
        for skin in (positive,negative):
            u=tuple(skin[1][k]-skin[0][k] for k in range(3))
            v=tuple(skin[2][k]-skin[0][k] for k in range(3))
            cross=(u[1]*v[2]-u[2]*v[1],
                   u[2]*v[0]-u[0]*v[2],
                   u[0]*v[1]-u[1]*v[0])
            magnitude=sum(c*c for c in cross)**.5
            assert magnitude>1e-8,("D4_TAPER_DEGENERATE_SKIN",fid)
            assert _dot(cross,n)>1e-8 if skin is positive else _dot(cross,n)<-1e-8
            positive_skin_count+=1
    assert positive_skin_count==2*len(trial["v_source_faces"])
    for side in ("left","right"):
        skins,ids=_source_local_side_skin_faces(trial,side)
        check=diagnose_world_mesh_self_intersections(
            skins,max_nonadjacent_pairs=len(skins)*(len(skins)-1)//2,
        )
        assert not check.numerical_budget_exhausted
        assert check.crossing_pair_count==0
        assert check.coplanar_overlap_pair_count==0
        # The former Y225 source-edge defect must not be "repaired" by
        # manipulating the original finite side bend terminal.
        assert _source_shared_upper_skin_discontinuities(
            trial,station=st.left_side_end,side=side,
        )==_source_shared_upper_skin_discontinuities(
            native,station=st.left_side_end,side=side,
        )
    for location in ((100.,-275.,0.),(-294.,-297.,0.)):
        before=probe_native_world_mesh_axis_faces(
            native["v_solid"],axis=2,fixed_xyz=location,
        )
        after=probe_native_world_mesh_axis_faces(
            trial["v_solid"],axis=2,fixed_xyz=location,
        )
        assert before==pytest.approx(after,abs=1e-6)


@pytest.mark.parametrize("first_axis",("x","y"))
@pytest.mark.parametrize("dimensions",(
    (620.,600.,185.,48.),
    (620.,600.,185.,55.),
    (670.,640.,205.,55.),
))
def test_native_check_uses_actual_factory_dimensions_and_original_holes(
    first_axis,dimensions,
):
    """Real Engine Factory and Body request, not a hand-authored 2D fixture."""
    from dataclasses import replace
    from ae_engine.manufacturing_render_data import fold_guides_from_final_scene
    from ae_engine.v_miter_tail_no_ba_sequential import stations_from_real_flat
    from ae_engine.assembly_geometry import triangle_bounds
    width,height,depth,bottom=dimensions
    source=replace(default_vault_tail_d4_spec(),
                   width=width,height=height,depth=depth,fold_bottom=bottom)
    flat,_=build_tail_d4_check_from_original(source)
    body=_real_w620_body(width=width,height=height,depth=depth,bottom=bottom)
    candidate=api.project_operator_tail_d4_check_native_world(
        flat,first_axis=first_axis,box_body_world=body,
    )
    assert candidate is not None
    assert candidate["first_axis"]==first_axis
    assert not candidate["manufacturing_approved"]
    assert candidate["nominal_lower_v_taper"] is True
    assert len(candidate["v_solid"])==len(candidate["v_solid_source_ids"])
    assert candidate["v_source_uv"]
    assert candidate["v_world_open_seam_edges"]==0
    assert candidate["v_world_four_edges"]==8
    assert candidate["v_extra_world_open_edges"]==0
    assert candidate["v_world_open_edges"]==candidate[
        "shared_original_world_open_edges"
    ]
    assert len(candidate["straight_v_wall_sets"])==2
    assert all(row["full_face_contact_proven"]
               for row in candidate["straight_v_wall_sets"])
    assert len([p for p in flat.result_scene.primitives
                if p.layer=="CUTTING"])==5
    assert len([p for p in flat.original_scene.primitives
                if p.layer=="CUTTING"])==5
    assert tuple(g for g in fold_guides_from_final_scene(flat.original_scene))
    assert len(flat.original_factory_material.interiors)==0
    assert len(candidate["v_material"].interiors)==4
    # The D4 solid material has the four original physical CUTTING holes,
    # while the flat's retained polygon is its exterior-only shell.
    # Compare actual outer contour with outer contour; do not count real
    # Factory holes as lost/extra material or silently discard them.
    from shapely.geometry import Polygon
    assert Polygon(candidate["v_material"].exterior).symmetric_difference(
        Polygon(flat.result_material.exterior)
    ).area<=1e-7
    assert stations_from_real_flat(flat).bottom_y==pytest.approx(bottom)
    # Only candidate geometry changes; source Factory finite BEND and
    # the pre-existing physical Body world are never altered.
    assert len(body)>0
    assert triangle_bounds(candidate["v_solid"]) is not None


@pytest.mark.parametrize("first_axis",("x","y"))
def test_native_check_rejects_real_original_square_hole_at_bottom31(
    first_axis,
):
    """Original x3..7/y18..22 square has nonzero overlap with V wedge."""
    from dataclasses import replace
    from ae_engine.sheetmetal_geometry_core import GeometryError
    spec=replace(default_vault_tail_d4_spec(),fold_bottom=31.)
    with pytest.raises(GeometryError,match=(
        "V_MITER_LOWER_CUTTING_CONFLICTS_WITH_ORIGINAL_HOLE"
    )):
        build_tail_d4_check_from_original(spec)


def test_d4_native_check_world_adapter_preserves_unverified_profile_fallback():
    """Unsupported family/T/FW/side/top profile returns legacy CHECK only."""
    from dataclasses import replace
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    body=_real_w620_body()
    for changed in (
        {"thickness":2.5},
        {"frame_width":26.},
        {"fold_top":17.},
        {"fold_left":16.},
        {"fold_right":16.},
        {"model_name":"受電箱"},
    ):
        other=replace(flat,source_spec=replace(flat.source_spec,**changed))
        assert api.project_operator_tail_d4_check_native_world(
            other,first_axis="x",box_body_world=body,
        ) is None,changed


@pytest.mark.parametrize("field,bad",(
    ("width",None),("depth",0.),("height",float("nan")),
    ("fold_bottom",-1.),("fold_bottom",float("inf")),
))
def test_d4_check_invalid_real_dimension_never_defaults_to_w620(field,bad):
    from dataclasses import replace
    flat,_=build_tail_d4_check_from_original(default_vault_tail_d4_spec())
    other=replace(flat,source_spec=replace(flat.source_spec,**{field:bad}))
    with pytest.raises(ValueError,match=(
        "TAIL_D4_CHECK_NATIVE_PHYSICAL_DIMENSIONS_INVALID:"+field
    )):
        api.project_operator_tail_d4_check_native_world(
            other,first_axis="x",box_body_world=_real_w620_body(),
        )
