# -*- coding: utf-8 -*-
"""#3317 Issue A: Ø4 true CUTTING, source-keyed two-stage T2 CHECK only.

This is NOT the approved V preview, a manufacturing adapter, or a CUTTING
exporter. The original finite BEND, true through-holes and source UV are
immutable. No BA, bend R, added crease, cap, freehand thickness face or
independent two-sided offset is permitted.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point

from .assembly_geometry import diagnose_world_mesh_self_intersections
from .manufacturing_render_data import material_polygon_from_final_scene
from .sheetmetal_geometry_core import GeometryError
from .v_miter_tail_full_t_no_ba import _cross, _dot, _unit, _v3sub
from .v_miter_tail_no_ba_sequential import (
    _single_sheet_triangles, _stages, stations_from_real_flat,
    exact_tail_y_fold_profile_from_original_bends,
)
from .endcap_factory_fold import build_endcap_xy_fold_profiles
from .assembly_geometry_folded_mesh import _profile_geometry, _profile_map

_EPS = 1e-7


@dataclass(frozen=True)
class TailD4RootCheck:
    first_axis: str
    source_uv: tuple
    inner_xyz: tuple
    outer_xyz: tuple
    shell_faces: tuple
    source_triangle_faces: tuple
    source_boundary_edges: tuple
    source_hole_count: int
    arc_wall_edges_by_corner: tuple
    surviving_v_wall_edges_by_corner: tuple
    bad_incidence_edges: tuple
    bad_winding_edges: tuple
    local_interference_by_corner: tuple
    # Every face is indexed to the same original UV. An unproved surface
    # is never filled with an arbitrary triangle.
    manufacturing_approved: bool = False
    status: str = "D4_SOURCE_KEYED_SHARP_T2_CHECK_ONLY"


def _error(name, *, uv=None, face=None, detail=None):
    raise GeometryError(
        name + ("" if uv is None else f":UV={uv}")
        + ("" if face is None else f":FACE={face}")
        + ("" if detail is None else f":{detail}")
    )


def project_tail_d4_source_keyed_t_check(flat, *, first_axis):
    """Produce a CHECK mesh only if every true source boundary is T-closed.

    Source BEND-domain tessellation and source-keyed sharp thickness follow
    the existing Tail FULL-T owner, but this candidate's true circular hole
    and outer outline must be present in the same FinalScene. This does not
    call the sharp-only apex->tip witness, whose precondition is false for D4.
    """
    if first_axis not in ("x", "y"):
        _error("TAIL_D4_CHECK_FIRST_AXIS_REQUIRED")
    st = stations_from_real_flat(flat)
    if abs(float(flat.source_spec.thickness) - 2.) > _EPS:
        _error("TAIL_D4_CHECK_T2_SOURCE_REQUIRED")
    stock = material_polygon_from_final_scene(flat.result_scene)
    if stock.geom_type != "Polygon" or not stock.is_valid or not stock.interiors:
        _error("TAIL_D4_CHECK_TRUE_CUTTING_WITH_HOLES_REQUIRED")
    if len(flat.opening_source_points_xy) != 2:
        _error("TAIL_D4_CHECK_TWO_CORNER_SOURCE_REQUIRED")

    # Exactly the source arcs, not a generic 'radius at any apex'.  Reject
    # sharp-only stock disguised as D4; no holes or original features erased.
    circles = []
    for name, _low, apex, _high in flat.opening_source_points_xy:
        circle = Point(*apex).buffer(2., resolution=48)
        for uv in (
            (apex[0], apex[1] - 2.),
            (apex[0], apex[1] + 2.),
            ((apex[0] + 2.) if name.endswith("left")
             else (apex[0] - 2.), apex[1]),
        ):
            if Point(*uv).distance(stock.boundary) > _EPS*3:
                _error("TAIL_D4_CHECK_ACTUAL_ARC_MISSING", uv=uv)
        circles.append((name, circle.boundary))

    source, area = _single_sheet_triangles(stock, st)
    if abs(area - stock.area) > max(1e-5, stock.area*1e-7):
        _error("TAIL_D4_CHECK_TRIANGULATION_AREA_LOST", detail=(area,stock.area))

    spec = flat.source_spec
    snapshot = dict(
        model=spec.model_name,w=spec.width,d=spec.depth,t=spec.thickness,
        fw=spec.frame_width,yl1=spec.fold_left,yr1=spec.fold_right,
        ytop1=spec.fold_top,ybottom1=spec.fold_bottom,
    )
    profiles = build_endcap_xy_fold_profiles(snapshot, part_key="tail")
    exact_y = exact_tail_y_fold_profile_from_original_bends(flat,st)
    ybreak,yfold = _profile_geometry(exact_y)
    u0,z0 = _profile_map(st.bottom_y,ybreak,yfold)

    def formed(uv):
        x,y = uv
        if y <= st.upper_start+_EPS:
            return _stages(uv,first_axis,st)[1]
        if x < st.bottom_guide_start-_EPS or x > st.bottom_guide_end+_EPS:
            _error("TAIL_D4_CHECK_UPPER_MATERIAL_OUTSIDE_REAL_BEND",
                   uv=uv)
        uy,uz = _profile_map(y,ybreak,yfold)
        return (x,st.bottom_y+uy-u0,uz-z0)

    uv_to_index = {}
    source_uv = []
    triangles = []
    for triangle in source:
        ids = []
        for xy in triangle:
            uv = (float(xy[0]),float(xy[1]))
            key = tuple(round(v/_EPS) for v in uv)
            if key not in uv_to_index:
                uv_to_index[key] = len(source_uv)
                source_uv.append(uv)
            ids.append(uv_to_index[key])
        if len(set(ids)) != 3:
            _error("TAIL_D4_CHECK_SOURCE_DEGENERATE_FACE",
                   uv=tuple(triangle))
        triangles.append(tuple(ids))
    inner = tuple(formed(uv) for uv in source_uv)
    normals = [[] for _ in source_uv]
    for face_id,(a,b,c) in enumerate(triangles):
        v = _cross(_v3sub(inner[b],inner[a]),_v3sub(inner[c],inner[a]))
        if _dot(v,v) < _EPS**4:
            _error("TAIL_D4_CHECK_COLLAPSED_T_FACE",
                   uv=tuple(source_uv[i] for i in (a,b,c)), face=face_id)
        n = _unit(v)
        for i in (a,b,c):
            if not any(_dot(n,old) >= 1.-1e-9 for old in normals[i]):
                normals[i].append(n)

    # SAME UV thickness rule from v_miter_tail_full_t_no_ba.py:
    # deduplicate ACTUAL incident source face normals, then the one
    # outside point is inside - T * SUM(normals); never independent offset.
    for i,group in enumerate(normals):
        for j,n in enumerate(group):
            for previous in group[:j]:
                if abs(_dot(n,previous)) > _EPS:
                    _error("TAIL_D4_CHECK_NONORTHOGONAL_SHARP_ROOT",
                           uv=source_uv[i], detail=(previous,n))
    t = float(spec.thickness)
    outside = tuple(tuple(
        inner[i][component]-t*sum(n[component] for n in group)
        for component in range(3)
    ) for i,group in enumerate(normals))

    source_edges = defaultdict(list)
    for face_id,(a,b,c) in enumerate(triangles):
        for v,w in ((a,b),(b,c),(c,a)):
            source_edges[tuple(sorted((v,w)))].append((v,w,face_id))
    if any(len(group)>2 for group in source_edges.values()):
        _error("TAIL_D4_CHECK_NONMANIFOLD_SOURCE")
    boundary = tuple(group[0] for group in source_edges.values()
                     if len(group)==1)
    for a,b,face_id in boundary:
        mid = tuple((source_uv[a][i]+source_uv[b][i])/2 for i in range(2))
        if Point(*mid).distance(stock.boundary) > 3*_EPS:
            _error("TAIL_D4_CHECK_SOURCE_T_JUNCTION_OR_MISSING_EDGE",
                   uv=mid,face=face_id)

    k=len(inner)
    all_vertices = inner+outside
    shell = []
    for a,b,c in triangles:
        shell.extend(((a,b,c),(c+k,b+k,a+k)))
    wall_by_edge = {}
    for a,b,_ in boundary:
        # Follow the existing FULL-T canonical cut-wall diagonal,
        # preserve opposite source edges and do not cap missing material.
        p=tuple(round(v/_EPS) for v in inner[a])
        q=tuple(round(v/_EPS) for v in inner[b])
        if p <= q:
            faces=((a,b+k,b),(a,a+k,b+k))
        else:
            faces=((b,a,a+k),(b,a+k,b+k))
        start=len(shell)
        shell.extend(faces)
        wall_by_edge[frozenset((a,b))]=(start,start+1)

    incidence=defaultdict(list)
    for face_id,(a,b,c) in enumerate(shell):
        for v,w in ((a,b),(b,c),(c,a)):
            incidence[tuple(sorted((v,w)))].append((v,w,face_id))
    bad_incidence=tuple((e,tuple(x[2] for x in group))
                        for e,group in incidence.items() if len(group)!=2)
    bad_winding=tuple((e,tuple(x[2] for x in group))
                      for e,group in incidence.items()
                      if len(group)==2 and group[0][:2]==group[1][:2])
    if bad_incidence:
        edge, faces=bad_incidence[0]
        _error("TAIL_D4_CHECK_SHELL_EDGE_INCIDENCE",
               uv=tuple(source_uv[i%k] for i in edge),face=faces)
    if bad_winding:
        edge, faces=bad_winding[0]
        _error("TAIL_D4_CHECK_SHELL_EDGE_WINDING",
               uv=tuple(source_uv[i%k] for i in edge),face=faces)

    arc_counts=[]
    straight_counts=[]
    for name,lower,apex,upper in flat.opening_source_points_xy:
        circle = next(r for key,r in circles if key==name)
        arc_edges=[]
        straight_edges=[]
        lines=(LineString((apex,lower)),LineString((apex,upper)))
        for a,b,_ in boundary:
            seg=LineString((source_uv[a],source_uv[b]))
            key=frozenset((a,b))
            if seg.length <= _EPS: continue
            if seg.distance(circle) <= _EPS*3 and (
                Point(*source_uv[a]).distance(circle) < _EPS*3
                and Point(*source_uv[b]).distance(circle) < _EPS*3
            ):
                arc_edges.append((key,seg))
            if any(seg.difference(line.buffer(_EPS*3)).length < _EPS
                   for line in lines):
                straight_edges.append((key,seg))
        # We only certify that the real circle and both surviving V walls
        # have their source-keyed thickness walls, not an invented bridge.
        if not arc_edges or not straight_edges:
            _error("TAIL_D4_CHECK_MISSING_ARC_OR_SURVIVING_V_WALL",
                   uv=apex,detail=(len(arc_edges),len(straight_edges)))
        arc_counts.append((name,len(arc_edges)))
        straight_counts.append((name,len(straight_edges)))

    # Actual local shell triangles, with source face IDs. A genuine
    # coincident straight V cut wall is a physical seam, not penetration.
    # Candidate testing is bounded to both original lower corners.
    observed=[]
    for name,lower,apex,upper in flat.opening_source_points_xy:
        left=name.endswith("left")
        x0=st.xmin if left else st.xmax
        local_ids=tuple(j for j,face in enumerate(shell)
            if all(abs(source_uv[v%k][0]-x0)<=25. and
                   st.bottom_y-25.<=source_uv[v%k][1]<=st.bottom_y+25.
                   for v in face))
        local_triangles=tuple(tuple(all_vertices[v] for v in shell[j])
                              for j in local_ids)
        if len(local_triangles)<3:
            _error("TAIL_D4_CHECK_LOCAL_THICK_SHELL_MISSING",uv=apex)
        # Exclude only pairs of *identical* actual opposite-normal V walls
        # after their source identities were retained in the indexed shell.
        # Global boolean is NOT implied even by zero local crossings.
        fingerprint=defaultdict(list)
        for local_i,tri in enumerate(local_triangles):
            key=tuple(sorted(tuple(round(x/_EPS) for x in v)
                             for v in tri))
            fingerprint[key].append(local_i)
        excluded=set()
        for ids in fingerprint.values():
            if len(ids)==2:
                a,b=ids
                na=_unit(_cross(_v3sub(local_triangles[a][1],local_triangles[a][0]),
                                _v3sub(local_triangles[a][2],local_triangles[a][0])))
                nb=_unit(_cross(_v3sub(local_triangles[b][1],local_triangles[b][0]),
                                _v3sub(local_triangles[b][2],local_triangles[b][0])))
                if _dot(na,nb)<-1.+_EPS:
                    excluded.add(b)
        check=tuple(face for j,face in enumerate(local_triangles)
                    if j not in excluded)
        budget=max(1,len(check)*(len(check)-1)//2)
        status=diagnose_world_mesh_self_intersections(
            check,max_nonadjacent_pairs=budget)
        if (status.numerical_budget_exhausted
                or status.crossing_pair_count
                or status.coplanar_overlap_pair_count):
            pair=status.first_source_triangle_pair
            face_pair=(None if pair is None else
                       tuple(local_ids[i] for i in pair))
            _error("TAIL_D4_CHECK_LOCAL_T_INTERFERENCE_UNRESOLVED",
                   uv=apex,face=face_pair,
                   detail=(status.crossing_pair_count,
                           status.coplanar_overlap_pair_count,
                           status.numerical_budget_exhausted))
        observed.append((name,status.tested_nonadjacent_pairs))

    return TailD4RootCheck(
        first_axis=first_axis,source_uv=tuple(source_uv),inner_xyz=inner,
        outer_xyz=outside,shell_faces=tuple(shell),
        source_triangle_faces=tuple(triangles),
        source_boundary_edges=boundary,source_hole_count=len(stock.interiors),
        arc_wall_edges_by_corner=tuple(arc_counts),
        surviving_v_wall_edges_by_corner=tuple(straight_counts),
        bad_incidence_edges=bad_incidence,bad_winding_edges=bad_winding,
        local_interference_by_corner=tuple(observed),
    )
