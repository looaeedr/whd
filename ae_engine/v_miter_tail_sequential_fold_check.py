# -*- coding: utf-8 -*-
"""#3317: same-sheet, source-paired two-STAGE finite R/BA/T Tail fold CHECK.

This is a kinematic CHECK, never a manufacturing method or approved relief.
No second independent side/bottom 3D construction is used: ONE original
Factory source triangulation is transported as a whole through the first
selected physical bend, then through the second. Its true source V-cut faces
are traced back through the paired triangulation into the final T solid.

At finite crease ends the carried connected tip is a provisional kinematic
continuation (no invented BEND). This is NOT an elastic/plastic simulation
of the physical transition at the common root. Leave such a result UNKNOWN
rather than certify contact/nonpenetration merely from a coherent mesh.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point, Polygon, box

from .assembly_geometry_primitives import thicken_triangle_surface
from .assembly_geometry import (
    diagnose_world_mesh_triangle_edge_incidence,
    diagnose_world_mesh_self_intersections,
)
from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .sheetmetal_geometry_core import GeometryError
from .v_miter_source_cut_face_trial import trace_v_miter_source_true_t_cut_faces
from .v_miter_true_t_collision import _source_triangulation


Vec3 = tuple[float, float, float]
_EPS = 1e-7
_ARC_STEPS = 16


@dataclass(frozen=True)
class TailSequentialFoldResult:
    first_axis: str
    second_axis: str
    flat_source_triangles: tuple
    first_formed_skin_triangles: tuple
    second_formed_skin_triangles: tuple
    first_thick_solid_triangles: tuple
    second_thick_solid_triangles: tuple
    # (corner, leg, fraction, original UV, after-first XYZ, after-second XYZ,
    #  first physical T +/- XYZ, final physical T +/- XYZ)
    source_cut_edge_tracks: tuple
    # (corner, first-stage upper V true T, first-stage lower V true T,
    #  final upper V true T, final lower V true T)
    true_t_cut_faces_by_corner: tuple
    source_area_mm2: float
    triangulated_area_mm2: float
    source_material_polygon: Polygon
    source_fold_parameters: tuple
    # Operator-corrected side BENDs reach the lower edge, so some
    # retained corner UV receives BOTH bends. X/Y final positions may differ.
    source_x_only_vertices: int
    source_y_only_vertices: int
    source_double_bend_vertices: int
    max_X_then_Y_vs_Y_then_X_final_delta_mm: float
    first_stage_max_duplicate_vertex_jump_mm: float
    final_stage_max_duplicate_vertex_jump_mm: float
    # Distinguish genuine non-neighbor T shell self-crossings from
    # source-shared edge/vertex contacts. A zero witness is NOT a complete
    # factory nonpenetration certification.
    stage1_shell_topology: object
    stage2_shell_topology: object
    # True source-root ROIs, not arbitrary independently invented solids.
    # Per-corner (corner, stage1, stage2, original cut-bounded region counts).
    root_true_t_self_intersection_by_corner: tuple
    # A mesh being numerically continuous does NOT prove that the finite
    # sheet carries a genuine process-supported isometric root transition.
    root_process_status: str = "FINITE_BEND_TIP_TRANSITION_KINEMATIC_ONLY"
    full_assembly_3d_status: str = "LOWER_FOLDS_ONLY_OTHER_BENDS_UNCHANGED_CHECK"
    manufacturing_status: str = "NOT_VERIFIED"


def _source_triangles(stock: Polygon, *, minx: float, maxx: float,
                      miny: float, maxy: float, left: float, right: float,
                      bottom: float, allowance: float, side_end: float,
                      bottom_span: tuple[float, float]) -> tuple:
    """Tessellate original continuous stock, never concatenate three patches.

    Source slicing at exact finite creases, their real tips, and sixteen
    physical BA arc stations keeps contact walls faithful to curved RBA.
    Cell lines refine only the CHECK tessellation, not FinalScene BEND.
    """
    if allowance <= 0 or minx >= left or left >= right or right >= maxx:
        raise GeometryError("TAIL_SEQUENTIAL_SOURCE_BOUNDARIES_INVALID")
    xs = {minx, maxx, left, right, float(bottom_span[0]), float(bottom_span[1])}
    ys = {miny, maxy, bottom, side_end}
    for i in range(_ARC_STEPS + 1):
        u = allowance * i / _ARC_STEPS
        xs.update((left-u, right+u))
        ys.add(bottom-u)
    xs = sorted(q for q in xs if minx <= q <= maxx)
    ys = sorted(q for q in ys if miny <= q <= maxy)
    parts = []
    area = 0.0
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            if x1 - x0 <= _EPS or y1 - y0 <= _EPS:
                continue
            clipped = stock.intersection(box(x0, y0, x1, y1))
            pieces = (clipped,) if clipped.geom_type == "Polygon" else tuple(
                part for part in getattr(clipped, "geoms", ())
                if part.geom_type == "Polygon" and part.area > _EPS
            )
            for piece in pieces:
                if piece.area <= _EPS:
                    continue
                if not piece.is_valid or piece.interiors:
                    raise GeometryError("TAIL_SEQUENTIAL_SOURCE_CLIP_INVALID")
                for tri in _source_triangulation(piece):
                    parts.append(tri)
                    a,b,c = tri
                    area += abs((b[0]-a[0])*(c[1]-a[1])
                                -(b[1]-a[1])*(c[0]-a[0])) / 2.0
                    if len(parts) > 16000:
                        raise GeometryError("TAIL_SEQUENTIAL_SOURCE_TRIANGLE_LIMIT")
    if not parts or abs(stock.area-area)>max(1e-5,stock.area*1e-7):
        raise GeometryError("TAIL_SEQUENTIAL_SAME_SHEET_AREA_LOST")
    return tuple(parts)


def _fold_action(source_xy, xyz, normal, *, axis: str, left: float,
                 right: float, bottom: float, minx: float, maxx: float,
                 side_end: float, allowance: float, mid_radius: float):
    """Apply ONE selected 90-degree R/BA bend to the PREVIOUS 3D frame.

    'x' follows the operator-corrected physical side BEND all the way to
    the real bottom edge. 'y' folds below the real finite horizontal guide.
    Their retained lower-corner overlap receives BOTH motions in the chosen
    order; this is a kinematic CHECK, not certified root plasticity.
    """
    x,y=source_xy
    outside=(0.0,0.0,0.0)
    u=0.0
    if axis == "x":
        if y <= side_end+_EPS:
            if x < left-_EPS:
                u=left-x
                outside=(-1.0,0.0,0.0)
            elif x > right+_EPS:
                u=x-right
                outside=(1.0,0.0,0.0)
    elif axis == "y":
        if minx-_EPS<=x<=maxx+_EPS and y < bottom-_EPS:
            u=bottom-y
            outside=(0.0,-1.0,0.0)
    else:
        raise GeometryError("TAIL_SEQUENTIAL_FIRST_AXIS_REQUIRED")
    if u<=_EPS:
        return xyz,normal
    neutral_radius=allowance/(math.pi/2.0)
    phi=min(u,allowance)/neutral_radius
    linear=max(0.0,u-allowance)
    in_plane=mid_radius*math.sin(phi)+linear*math.cos(math.pi/2)
    rise=mid_radius*(1.0-math.cos(phi))+linear*math.sin(math.pi/2)
    point=tuple(
        float(xyz[i]+(in_plane-u)*outside[i]+rise*normal[i])
        for i in range(3)
    )
    new_normal=tuple(
        float(normal[i]*math.cos(phi)-outside[i]*math.sin(phi))
        for i in range(3)
    )
    if not all(math.isfinite(v) for v in (*point,*new_normal)):
        raise GeometryError("TAIL_SEQUENTIAL_NONFINITE_GEOMETRY")
    if abs(math.sqrt(sum(v*v for v in new_normal))-1)>1e-7:
        raise GeometryError("TAIL_SEQUENTIAL_NORMAL_NOT_UNIT")
    return point,new_normal



def _advance_same_source_uv(source_xy, first_axis, parameters):
    """Actual point transformer shared by the stage mesh AND inverse gate."""
    (left,right,bottom,minx,maxx,side_end,
     allowance,mid_radius)=parameters
    base=(float(source_xy[0]),float(source_xy[1]),0.0)
    n0=(0.0,0.0,1.0)
    first,n1=_fold_action(
        source_xy,base,n0,axis=first_axis,
        left=left,right=right,bottom=bottom,minx=minx,maxx=maxx,
        side_end=side_end,allowance=allowance,mid_radius=mid_radius,
    )
    second,n2=_fold_action(
        source_xy,first,n1,
        axis=("y" if first_axis=="x" else "x"),
        left=left,right=right,bottom=bottom,minx=minx,maxx=maxx,
        side_end=side_end,allowance=allowance,mid_radius=mid_radius,
    )
    return first,second,n1,n2


def project_tail_same_sheet_staged_source_point(model, source_uv):
    """Forward-recheck a proposed inverse using RETAINED original V stock.

    A point on the original mother but inside the already removed V wedge
    is NOT sheet metal. Reject it before fold mapping; no fabricated cut
    line or material re-ownership can be inferred from that UV.
    """
    if not isinstance(model,TailSequentialFoldResult):
        raise GeometryError("TAIL_SEQUENTIAL_TYPED_STAGE_MODEL_REQUIRED")
    try:
        xy=(float(source_uv[0]),float(source_uv[1]))
    except (IndexError,TypeError,ValueError):
        raise GeometryError("TAIL_SEQUENTIAL_SOURCE_UV_INVALID") from None
    if not all(math.isfinite(v) for v in xy):
        raise GeometryError("TAIL_SEQUENTIAL_SOURCE_UV_INVALID")
    if not model.source_material_polygon.covers(Point(*xy)):
        raise GeometryError("TAIL_SEQUENTIAL_UV_REMOVED_BY_ACTUAL_V_CUTTING")
    return _advance_same_source_uv(
        xy,model.first_axis,model.source_fold_parameters,
    )


def project_tail_same_sheet_sequential_fold_check(
    restored_mother: Polygon, v_cut_stock: Polygon, *,
    left_apex, right_apex,
    left_v_hits, right_v_hits,
    guides, first_axis: str,
    thickness_mm: float, inner_r_mm: float, bend_allowance_mm: float,
) -> TailSequentialFoldResult:
    """Return one source's before/after-first/after-second finite RBA/T.

    Stage order comes ONLY from saved operator choice. This check can
    establish kinematic positions and source wall identity, but DOES NOT
    solve unknown local stretching at an intersecting finite crease root.
    """
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_SEQUENTIAL_FIRST_AXIS_REQUIRED")
    if (restored_mother.geom_type!="Polygon" or v_cut_stock.geom_type!="Polygon"
            or not restored_mother.is_valid or not v_cut_stock.is_valid
            or restored_mother.interiors or v_cut_stock.interiors
            or v_cut_stock.difference(restored_mother.buffer(_EPS)).area > _EPS):
        raise GeometryError("TAIL_SEQUENTIAL_ONE_FACTORY_SHEET_REQUIRED")
    if (not all(math.isfinite(v) and v>0 for v in (
            thickness_mm,inner_r_mm,bend_allowance_mm))
            or abs(left_apex.y-right_apex.y)>_EPS):
        raise GeometryError("TAIL_SEQUENTIAL_PHYSICAL_PARAMETERS_INVALID")
    minx,miny,maxx,maxy=map(float,restored_mother.bounds)
    left,right,bottom=float(left_apex.x),float(right_apex.x),float(left_apex.y)
    actual=tuple(guides or ())
    def physical_guide(axis,station):
        hits=tuple(g for g in actual if g.axis==axis
                   and abs(float(g.position)-station)<=_EPS)
        if len(hits)!=1:
            raise GeometryError("TAIL_SEQUENTIAL_ACTUAL_FINITE_GUIDE_MISSING")
        return hits[0]
    lg=physical_guide("x",left)
    rg=physical_guide("x",right)
    bg=physical_guide("y",bottom)
    # Source BEND was corrected by the user to reach the real bottom Y.
    if (not (abs(float(lg.span_start)-miny)<=_EPS
             and abs(float(rg.span_start)-miny)<=_EPS
             and bottom<float(lg.span_end)
             and bottom<float(rg.span_end))
            or abs(float(lg.span_end)-float(rg.span_end))>_EPS
            or not(minx<left<float(bg.span_start)
                   <float(bg.span_end)<right<maxx)):
        raise GeometryError("TAIL_SEQUENTIAL_FINITE_BEND_SOURCE_DISAGREES")
    if bend_allowance_mm>=min(left-minx,maxx-right,bottom-miny):
        raise GeometryError("TAIL_SEQUENTIAL_BA_CONSUMES_FLANGE")
    source=_source_triangles(
        v_cut_stock, minx=minx,maxx=maxx,miny=miny,maxy=maxy,
        left=left,right=right,bottom=bottom,
        allowance=bend_allowance_mm,
        side_end=float(lg.span_end),
        bottom_span=(bg.span_start,bg.span_end),
    )
    mid_r=inner_r_mm+thickness_mm/2.0
    second_axis="y" if first_axis=="x" else "x"
    parameters=(
        left,right,bottom,minx,maxx,float(lg.span_end),
        bend_allowance_mm,mid_r,
    )
    tol=float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    def forward(xy):
        return _advance_same_source_uv(xy,first_axis,parameters)
    # All triangle vertices are moved through the same two actions and
    # retain exact source UV identity; there are no separately generated
    # side/bottom solids that can hide a seam tear.
    all_first=[]
    all_final=[]
    offsets_first={}
    offsets_final={}
    source_vertices_first={}
    source_vertices_final={}
    continuity_first=continuity_final=0.0
    x_only=y_only=both=0
    order_max_delta=0.0
    unique_uv=set()
    for face in source:
        first_face=[]
        final_face=[]
        for uv in face:
            stage1,stage2,n1,n2=forward(uv)
            opposite_final=_advance_same_source_uv(
                uv,second_axis,parameters,
            )[1]
            order_max_delta=max(
                order_max_delta,math.dist(stage2,opposite_final),
            )
            source_uv_key=tuple(round(float(q)/tol) for q in uv)
            if source_uv_key not in unique_uv:
                unique_uv.add(source_uv_key)
                x,y=map(float,uv)
                fold_x=(bottom-_EPS<=y<=float(lg.span_end)+_EPS and
                        (x<left-_EPS or x>right+_EPS))
                fold_y=(minx-_EPS<=x<=maxx+_EPS and y<bottom-_EPS)
                x_only+=int(fold_x and not fold_y)
                y_only+=int(fold_y and not fold_x)
                both+=int(fold_x and fold_y)
            first_face.append(stage1)
            final_face.append(stage2)
            src_key=tuple(round(q/tol) for q in uv)
            if src_key in source_vertices_first:
                continuity_first=max(continuity_first,math.dist(
                    stage1,source_vertices_first[src_key],
                ))
                continuity_final=max(continuity_final,math.dist(
                    stage2,source_vertices_final[src_key],
                ))
            source_vertices_first[src_key]=stage1
            source_vertices_final[src_key]=stage2
            for pt,normal,table in ((stage1,n1,offsets_first),
                                    (stage2,n2,offsets_final)):
                key=tuple(int(round(v/tol)) for v in pt)
                off=tuple(q*thickness_mm/2.0 for q in normal)
                prior=table.get(key)
                if prior is not None and math.dist(prior,off)>max(tol*10,1e-7):
                    raise GeometryError("TAIL_SEQUENTIAL_T_VERTEX_NORMAL_CONFLICT")
                table[key]=off
        all_first.append(tuple(first_face))
        all_final.append(tuple(final_face))
    if max(continuity_first,continuity_final)>tol:
        raise GeometryError("TAIL_SEQUENTIAL_UNCUT_SOURCE_TEAR")
    if not x_only or not y_only or not both or order_max_delta<=tol:
        raise GeometryError(
            "TAIL_SEQUENTIAL_BOTTOM_SIDE_BEND_OVERLAP_NOT_MODELED"
        )
    thick1=thicken_triangle_surface(
        all_first,thickness_mm,smooth_vertex_normals=True,
        physical_vertex_offsets=offsets_first,tolerance=tol,
    )
    thick2=thicken_triangle_surface(
        all_final,thickness_mm,smooth_vertex_normals=True,
        physical_vertex_offsets=offsets_final,tolerance=tol,
    )
    # These checks operate on the SINGLE physical T-sheet shell,
    # never on separately clipped flange solids. Shared adjacent
    # triangulation edges cannot count as true material penetration.
    top1=diagnose_world_mesh_triangle_edge_incidence(thick1,tolerance=tol)
    top2=diagnose_world_mesh_triangle_edge_incidence(thick2,tolerance=tol)
    # Exhaustively inspect the two *source-bounded root regions*.
    # The full sheet has many shared coplanar source mesh neighbors which
    # exhaust the general-purpose global check's bounded pair budget.
    # Cropping here is OBSERVATION ONLY: no triangles are moved/trimmed;
    # original whole-sheet topology is still checked separately above.
    root_self_checks=[]
    for corner,apex,hits in (
        ("bottom_left",left_apex,left_v_hits),
        ("bottom_right",right_apex,right_v_hits),
    ):
        low=(min(float(apex.x),*(float(p.x) for p in hits))-thickness_mm,
             min(float(apex.y),*(float(p.y) for p in hits))-thickness_mm,
             -thickness_mm)
        high=(max(float(apex.x),*(float(p.x) for p in hits))+thickness_mm,
              max(float(apex.y),*(float(p.y) for p in hits))+thickness_mm,
              max(left-minx,maxx-right)+thickness_mm)
        def near_source_root(solid):
            return tuple(tri for tri in solid
                if all(
                    max(v[axis] for v in tri) >= low[axis]-tol
                    and min(v[axis] for v in tri) <= high[axis]+tol
                    for axis in range(3)
                ))
        root_first=near_source_root(thick1)
        root_final=near_source_root(thick2)
        if not root_first or not root_final:
            raise GeometryError("TAIL_SEQUENTIAL_SOURCE_ROOT_T_SHELL_MISSING")
        diag1=diagnose_world_mesh_self_intersections(root_first,tolerance=tol)
        diag2=diagnose_world_mesh_self_intersections(root_final,tolerance=tol)
        root_self_checks.append((
            corner,diag1,diag2,len(root_first),len(root_final),
        ))
    corners=[]
    tracks=[]
    for corner,apex,hits in (
        ("bottom_left",left_apex,left_v_hits),
        ("bottom_right",right_apex,right_v_hits),
    ):
        for leg,p in (("BOTTOM_LOWER",hits[0]),("SIDE_UPPER",hits[1])):
            boundary=LineString(((apex.x,apex.y),(p.x,p.y)))
            if boundary.difference(v_cut_stock.boundary.buffer(tol)).length>tol:
                raise GeometryError("TAIL_SEQUENTIAL_V_LEG_NOT_FACTORY_CUTTING")
            for fraction in (0.0,.125,.25,.5,.75,.875,1.0):
                uv=(float(apex.x+(p.x-apex.x)*fraction),
                    float(apex.y+(p.y-apex.y)*fraction))
                a,b,n1,n2=forward(uv)
                tracks.append((
                    corner,leg,fraction,uv,a,b,
                    (tuple(a[i]+n1[i]*thickness_mm/2 for i in range(3)),
                     tuple(a[i]-n1[i]*thickness_mm/2 for i in range(3))),
                    (tuple(b[i]+n2[i]*thickness_mm/2 for i in range(3)),
                     tuple(b[i]-n2[i]*thickness_mm/2 for i in range(3))),
                ))
        is_left=corner=="bottom_left"
        def own_side(face):
            return all(
                uv[0]<=left+tol if is_left else uv[0]>=right-tol
                for uv in face
            ) and all(uv[1]>=bottom-tol for uv in face)
        def own_bottom(face):
            return all(uv[1]<=bottom+tol for uv in face)
        side_ids=tuple(i for i,tri in enumerate(source) if own_side(tri))
        bottom_ids=tuple(i for i,tri in enumerate(source) if own_bottom(tri))
        if not side_ids or not bottom_ids:
            raise GeometryError("TAIL_SEQUENTIAL_SOURCE_OWNER_MISSING")
        lines=(LineString(((apex.x,apex.y),(hits[0].x,hits[0].y))),
               LineString(((apex.x,apex.y),(hits[1].x,hits[1].y))))
        def tag(indices,stage_mesh,solid,offsets):
            return trace_v_miter_source_true_t_cut_faces(
                restored_mother,v_cut_stock,
                (source[i] for i in indices),
                (stage_mesh[i] for i in indices),
                solid,thickness_mm=thickness_mm,
                physical_vertex_offsets=offsets,
                physical_v_cut_leg_lines=lines,
            ).true_cut_face_triangles
        side1=tag(side_ids,all_first,thick1,offsets_first)
        bottom1=tag(bottom_ids,all_first,thick1,offsets_first)
        side2=tag(side_ids,all_final,thick2,offsets_final)
        bottom2=tag(bottom_ids,all_final,thick2,offsets_final)
        if not all((side1,bottom1,side2,bottom2)):
            raise GeometryError("TAIL_SEQUENTIAL_TRUE_SOURCE_T_WALL_MISSING")
        corners.append((corner,side1,bottom1,side2,bottom2))
    return TailSequentialFoldResult(
        first_axis=first_axis,second_axis=second_axis,
        flat_source_triangles=source,
        first_formed_skin_triangles=tuple(all_first),
        second_formed_skin_triangles=tuple(all_final),
        first_thick_solid_triangles=tuple(thick1),
        second_thick_solid_triangles=tuple(thick2),
        source_cut_edge_tracks=tuple(tracks),
        true_t_cut_faces_by_corner=tuple(corners),
        source_area_mm2=float(v_cut_stock.area),
        triangulated_area_mm2=float(sum(
            abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
            for a,b,c in source
        )),
        source_material_polygon=v_cut_stock,
        source_fold_parameters=parameters,
        source_x_only_vertices=x_only,
        source_y_only_vertices=y_only,
        source_double_bend_vertices=both,
        max_X_then_Y_vs_Y_then_X_final_delta_mm=float(order_max_delta),
        first_stage_max_duplicate_vertex_jump_mm=float(continuity_first),
        final_stage_max_duplicate_vertex_jump_mm=float(continuity_final),
        stage1_shell_topology=top1,
        stage2_shell_topology=top2,
        root_true_t_self_intersection_by_corner=tuple(root_self_checks),
    )
