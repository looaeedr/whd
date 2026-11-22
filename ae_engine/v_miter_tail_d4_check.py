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



def _require_authored_cutting_source(flat, stock):
    """Compare the EXACT authored Factory + resolved overlay, never hole count.

    The primary Factory blank may be replaced by this D4 CHECK perimeter.
    Every other original/overlay CUTTING must remain the *same source
    primitive* and the same physical void in resolved material.
    """
    from shapely.geometry import Polygon
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive

    original = tuple(p for p in flat.original_scene.primitives
                     if getattr(p, "layer", None) == "CUTTING")
    actual = tuple(p for p in flat.result_scene.primitives
                   if getattr(p, "layer", None) == "CUTTING")
    source_outer = tuple(p for p in original
        if isinstance(p, PolylinePrimitive) and p.closed
        and Polygon([(q.x,q.y) for q in p.points]).symmetric_difference(
            flat.original_factory_material).area <= _EPS)
    active_outer = tuple(p for p in actual
        if isinstance(p, PolylinePrimitive) and p.closed
        and getattr(p, "semantic_id", None) == "OUTER_BOUNDARY")
    if len(source_outer)!=1 or len(active_outer)!=1:
        _error("TAIL_D4_CHECK_SOURCE_OUTER_NOT_UNIQUE")
    inherited = tuple(flat.inherited_non_v_cutting_features)
    expected = tuple(p for p in original if p is not source_outer[0])+inherited
    observed = tuple(p for p in actual if p is not active_outer[0])
    if (len(observed)!=len(expected)
            or any(p is not q for p,q in zip(expected,observed))):
        _error("TAIL_D4_CHECK_AUTHORED_CUTTING_IDENTITY_CHANGED",
               detail=(len(expected),len(observed)))
    # The source-keyed identity check also pins original circle center,
    # radius, polyline points and user feature provenance. Verify their
    # *actual physical holes* have not been silently filled by the resolver.
    footprints=[]
    for p in expected:
        if isinstance(p, CirclePrimitive):
            if not math.isfinite(p.radius) or p.radius<=0:
                _error("TAIL_D4_CHECK_AUTHORED_CUTTING_INVALID")
            footprint=Point(p.center.x,p.center.y).buffer(p.radius,quad_segs=32)
        elif isinstance(p, PolylinePrimitive) and p.closed:
            footprint=Polygon([(q.x,q.y) for q in p.points])
        else:
            _error("TAIL_D4_CHECK_AUTHORED_CUTTING_UNSUPPORTED",
                   detail=type(p).__name__)
        if not footprint.is_valid or footprint.is_empty:
            _error("TAIL_D4_CHECK_AUTHORED_CUTTING_INVALID")
        footprints.append(footprint)
    holes=[Polygon(ring) for ring in stock.interiors]
    if len(holes)!=len(footprints):
        _error("TAIL_D4_CHECK_AUTHORED_HOLE_TOPOLOGY_CHANGED",
               detail=(len(footprints),len(holes)))
    remaining=list(holes)
    for i,hole in enumerate(footprints):
        matches=[j for j,actual_hole in enumerate(remaining)
                 if hole.symmetric_difference(actual_hole).area<=_EPS]
        if len(matches)!=1:
            _error("TAIL_D4_CHECK_AUTHORED_HOLE_GEOMETRY_CHANGED",
                   uv=hole.representative_point().coords[0],detail=i)
        remaining.pop(matches[0])
    return expected


def _actual_opposed_v_contact_ignores(
    local_ids, local_triangles, shell, boundary, source_uv, vertices, pairs
):
    """Only suppress duplicate faces from opposite REAL retained V legs.

    All unrelated identical/opposed faces (including hole walls) stay in the
    collision query, and source face IDs are kept through filtering.
    """
    fingerprint=defaultdict(list)
    local_faces={face_id:tri for face_id,tri in zip(local_ids,local_triangles)}
    for face_id in local_ids:
        tri=local_faces[face_id]
        key=tuple(sorted(tuple(round(v/_EPS) for v in p) for p in tri))
        fingerprint[key].append(face_id)

    ignored=set()
    for lower_ids,upper_ids in pairs:
        lower=set(lower_ids);upper=set(upper_ids)
        for source_id in sorted(lower):
            if source_id not in local_faces:
                continue
            source=local_faces[source_id]
            key=tuple(sorted(tuple(round(v/_EPS) for v in p)
                             for p in source))
            candidates=tuple(other for other in fingerprint[key]
                             if other in upper and other not in ignored)
            if len(candidates)!=1:
                continue
            other=candidates[0]
            target=local_faces[other]
            n0=_unit(_cross(_v3sub(source[1],source[0]),
                            _v3sub(source[2],source[0])))
            n1=_unit(_cross(_v3sub(target[1],target[0]),
                            _v3sub(target[2],target[0])))
            if _dot(n0,n1) < -1.+_EPS:
                ignored.add(other)
    filtered_ids=tuple(fid for fid in local_ids if fid not in ignored)
    return filtered_ids, tuple(local_faces[fid] for fid in filtered_ids)


def _actual_interference_source_face_pair(filtered_ids, pair):
    """Pair indices are local to FILTERED input, never unfiltered local_ids."""
    if pair is None:
        return None
    if len(pair)!=2 or any(i<0 or i>=len(filtered_ids) for i in pair):
        _error("TAIL_D4_CHECK_INVALID_COLLISION_FACE_REFERENCE",face=pair)
    return tuple(filtered_ids[i] for i in pair)


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
    if stock.geom_type != "Polygon" or not stock.is_valid:
        _error("TAIL_D4_CHECK_TRUE_CUTTING_WITH_HOLES_REQUIRED")
    _require_authored_cutting_source(flat,stock)
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
    true_v_face_pairs=[]
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
        # Provenance is the actual source UV boundary, not matching
        # world-space positions of arbitrary opposite triangles.
        lower_face_ids=set()
        upper_face_ids=set()
        for (a,b,_face) in boundary:
            seg=LineString((source_uv[a],source_uv[b]))
            for line,group in ((lines[0],lower_face_ids),
                               (lines[1],upper_face_ids)):
                if (seg.length>_EPS and
                        seg.difference(line.buffer(_EPS*3)).length<_EPS):
                    group.update(wall_by_edge[frozenset((a,b))])
        if not lower_face_ids or not upper_face_ids:
            _error("TAIL_D4_CHECK_REAL_V_WALL_PAIR_SOURCE_MISSING",uv=apex)
        true_v_face_pairs.append((
            name,tuple(sorted(lower_face_ids)),tuple(sorted(upper_face_ids))
        ))
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
        # The ONLY legal contact exemption is between matching source
        # CUTTING walls of the two actual surviving V legs of THIS corner.
        side_pair=next((a,b) for key,a,b in true_v_face_pairs if key==name)
        filtered_ids,check=_actual_opposed_v_contact_ignores(
            local_ids,local_triangles,shell,boundary,source_uv,
            all_vertices,(side_pair,),
        )
        budget=max(1,len(check)*(len(check)-1)//2)
        status=diagnose_world_mesh_self_intersections(
            check,max_nonadjacent_pairs=budget)
        if (status.numerical_budget_exhausted
                or status.crossing_pair_count
                or status.coplanar_overlap_pair_count):
            pair=status.first_source_triangle_pair
            face_pair=_actual_interference_source_face_pair(filtered_ids,pair)
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


def save_tail_d4_check_mesh_and_local_svg(check, flat, destination):
    """Write the ALREADY verified source-indexed CHECK shell and local views.

    Neither OBJ nor SVG is a formal manufacturing format. Every drawn stroke
    comes from true CUTTING/BEND or from the actual indexed T mesh: no
    synthetic joining face, circle interpolation or CAD allowance is added.
    """
    from pathlib import Path
    from .sheetmetal_drawing import LinePrimitive

    if not isinstance(check,TailD4RootCheck):
        _error("TAIL_D4_CHECK_RENDER_REQUIRES_VERIFIED_MESH")
    folder=Path(destination)
    folder.mkdir(parents=True,exist_ok=True)
    prefix=f"tail_d4_{check.first_axis}_CHECK_NOT_CNC"
    obj=folder/(prefix+".obj")
    svg=folder/(prefix+"_local.svg")
    vertices=check.inner_xyz+check.outer_xyz
    obj_rows=[
        "# WHD #3317 source-indexed D4 T2 CHECK, NOT CNC",
        f"# operator first fold {check.first_axis}",
        "# All vertices share the original source UV; no extra CAP faces",
    ]
    obj_rows.extend(
        "v "+ " ".join(f"{float(t):.10f}" for t in point)
        for point in vertices
    )
    obj_rows.extend(
        "f "+ " ".join(str(i+1) for i in tri)
        for tri in check.shell_faces
    )
    obj.write_text("\n".join(obj_rows)+"\n",encoding="utf-8")

    # Two exact-source views for each lower corner. The upper row is the
    # TRUE flat CUTTING/BEND crop, the lower row is the CHECK shell's inner,
    # outer and real boundary-wall edges in an explicit oblique projection.
    # Only source-boundary edges appear; an absent arc wall stays absent.
    def fmt(v):return f"{float(v):.3f}"
    chunks=[
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 540">',
        '<rect width="1080" height="540" fill="#fff"/>',
        '<text x="16" y="24" font-size="17" fill="#222">'
        'WHD #3317 D4 true source T2 CHECK / NOT CNC</text>',
    ]
    for ci,(name,_low,apex,_upper) in enumerate(flat.opening_source_points_xy):
        x0=float(apex[0])
        xbase=(36 if ci==0 else 565)
        ybase=34
        sign=(1 if ci==0 else -1)
        def flatp(uv):
            return (xbase+230+sign*float(uv[0]-x0)*5,
                    ybase+144-(float(uv[1])-48.)*4)
        def proj(p):
            # Oblique view is a projection of ACTUAL formed XYZ vertices.
            return (xbase+230+sign*(p[0]-x0)*3.2+(p[1]-48.)*1.65,
                    ybase+386+(p[1]-48.)*.72-p[2]*3.2)
        chunks.append(
            f'<text x="{fmt(xbase)}" y="52" font-size="14">'
            f'{name} — flat source CUTTING / BEND</text>'
        )
        for a,b,_ in check.source_boundary_edges:
            uv1=check.source_uv[a];uv2=check.source_uv[b]
            if not all(abs(uv[0]-x0)<25 and 22<uv[1]<74
                       for uv in (uv1,uv2)):
                continue
            p=flatp(uv1);q=flatp(uv2)
            chunks.append(
                f'<path d="M{fmt(p[0])} {fmt(p[1])} '
                f'L{fmt(q[0])} {fmt(q[1])}" '
                'fill="none" stroke="#075985" stroke-width="1.4"/>'
            )
        # Display actual BEND line primitives only, never a made-up crease.
        from shapely.geometry import box
        window=box(x0-25.,22.,x0+25.,74.)
        for item in flat.result_scene.primitives:
            if not isinstance(item,LinePrimitive) or item.layer!="BEND":
                continue
            source=LineString(((item.p1.x,item.p1.y),
                               (item.p2.x,item.p2.y)))
            crop=source.intersection(window)
            pieces=([crop] if crop.geom_type=="LineString" else
                    [g for g in getattr(crop,"geoms",())
                     if g.geom_type=="LineString"])
            for piece in pieces:
                if piece.length<=_EPS: continue
                p=flatp(piece.coords[0]);q=flatp(piece.coords[-1])
                chunks.append(
                    f'<path d="M{fmt(p[0])} {fmt(p[1])} '
                    f'L{fmt(q[0])} {fmt(q[1])}" '
                    'fill="none" stroke="#a16207" stroke-width="1.1"/>'
                )
        chunks.append(
            f'<text x="{fmt(xbase)}" y="315" font-size="14">'
            f'{name} — formed source-keyed T2 shell boundary (oblique)</text>'
        )
        k=len(check.inner_xyz)
        for a,b,_ in check.source_boundary_edges:
            uv1=check.source_uv[a];uv2=check.source_uv[b]
            if not all(abs(uv[0]-x0)<25 and 22<uv[1]<74
                       for uv in (uv1,uv2)):
                continue
            for vertices2,stroke in (
                (check.inner_xyz,"#075985"),(check.outer_xyz,"#be185d"),
            ):
                p=proj(vertices2[a]);q=proj(vertices2[b])
                chunks.append(
                    f'<path d="M{fmt(p[0])} {fmt(p[1])} '
                    f'L{fmt(q[0])} {fmt(q[1])}" '
                    f'fill="none" stroke="{stroke}" stroke-width="1"/>'
                )
            for v in (a,b):
                p=proj(check.inner_xyz[v]);q=proj(check.outer_xyz[v])
                chunks.append(
                    f'<path d="M{fmt(p[0])} {fmt(p[1])} '
                    f'L{fmt(q[0])} {fmt(q[1])}" '
                    'fill="none" stroke="#64748b" stroke-width=".55"/>'
                )
    chunks.append(
        '<text x="16" y="521" font-size="12" fill="#555">'
        'Blue = original source inside/CUTTING, magenta = actual indexed T outside; '
        'gold = actual finite BEND. Sharp no-BA/R CHECK only.</text>'
    )
    chunks.append('</svg>')
    svg.write_text("\n".join(chunks)+"\n",encoding="utf-8")
    return obj,svg
