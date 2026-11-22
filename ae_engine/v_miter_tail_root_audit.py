# -*- coding: utf-8 -*-
"""#3317 Vault Tail lower double-V root audit; CHECK only, never CNC.

Keep source UV and formed world XYZ edge identities separate. Merely welding
world-coincident triangles destroys their original one-sheet ownership.
Explicitly observe whether the second fold hinge axis is carried by the
first fold, and measure ±T/2 physical outside skin points; these observations
are NOT a closed thickness root or a certified formed outer envelope.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point

from .sheetmetal_geometry_core import GeometryError
from .v_miter_tail_sequential_fold_check import _advance_same_source_uv


@dataclass(frozen=True)
class TailDoubleVRootAudit:
    first_axis: str
    source_boundary_edge_count: int
    source_nonmanifold_edge_count: int
    interior_unpaired_source_edges: int
    first_world_alias_edge_count: int
    final_world_alias_edge_count: int
    first_zero_area_face_count: int
    final_zero_area_face_count: int
    first_reversed_face_count: int
    final_reversed_face_count: int
    # (corner, original axis unit XYZ, carried second axis unit XYZ)
    second_bend_axis_witnesses: tuple
    # ±T/2 surface extents of lower-fold CHECK, not certified full EndCap outside.
    trial_t_outer_bounds_xyz_mm: tuple
    trial_t_outer_extent_xyz_mm: tuple
    # A couple of world/UV collisions for deterministic root debugging.
    final_world_alias_source_witnesses: tuple
    thick_sheet_root_status: str = "CHECK_ROOT_PHYSICAL_T_VOLUME_NOT_CERTIFIED"
    full_endcap_outside_status: str = "UNVERIFIED_UPPER_FOLDS_AND_ROOT_T_NOT_FULLY_SOLVED"
    manufacturing_approved: bool = False


def _cross(a,b):
    return (
        a[1]*b[2]-a[2]*b[1],
        a[2]*b[0]-a[0]*b[2],
        a[0]*b[1]-a[1]*b[0],
    )


def _unit(a):
    m=math.sqrt(sum(q*q for q in a))
    if not math.isfinite(m) or m<=1e-10:
        raise GeometryError("TAIL_V90_ROOT_AUDIT_DEGENERATE_AXIS")
    return tuple(q/m for q in a)


def diagnose_tail_double_v_source_root(flat, stages) -> TailDoubleVRootAudit:
    """Inspect real source UV vs world coincidences, first/second axes, T skins.

    The original #3405 thickener groups edges by *formed XYZ* only. Such a
    group may accidentally include three or more source-unrelated triangles.
    That is evidence of world aliasing, not automatically physical welding,
    a crack, or volume penetration. Source UV is the topology authority.
    """
    from .v_miter_tail_user_image_source import (
        TailIllustratedSideV90Flat, TailIllustratedSideV90NominalAndStages,
    )
    from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
    if (not isinstance(flat,TailIllustratedSideV90Flat)
            or not isinstance(stages,TailIllustratedSideV90NominalAndStages)
            or stages.manufacturing_approved
            or stages.first_axis not in ("x","y")
            or flat.source_spec.thickness!=2.0):
        raise GeometryError("TAIL_V90_AUDIT_CORRECTED_FACTORY_T2_REQUIRED")
    src=stages.original_source_faces
    first=stages.after_first_faces_xyz
    final=stages.after_second_faces_xyz
    if not src or len(src)!=len(first) or len(src)!=len(final):
        raise GeometryError("TAIL_V90_AUDIT_UNPAIRED_SOURCE_TRIANGLES")
    tol=float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    if tol<=0 or not math.isfinite(tol):
        raise GeometryError("TAIL_V90_AUDIT_INVALID_ENGINE_TOLERANCE")
    def key(p):
        return tuple(int(round(float(q)/tol)) for q in p)
    def edge(a,b):
        x,y=key(a),key(b)
        return (x,y) if x<=y else (y,x)
    source_edges=defaultdict(list)
    first_world=defaultdict(set)
    final_world=defaultdict(set)
    folded_signed_counts=[]
    folded_zero_counts=[]
    for formed,groups in ((first,first_world),(final,final_world)):
        signed=zero=0
        for triuv,trixyz in zip(src,formed):
            n1=_cross(
                tuple(trixyz[1][j]-trixyz[0][j] for j in range(3)),
                tuple(trixyz[2][j]-trixyz[0][j] for j in range(3)),
            )
            if math.sqrt(sum(q*q for q in n1))<=1e-10:
                zero+=1
            else:
                # Analytic transported normal, not a normal inferred from
                # the possibly self-folded WORLD triangle.
                normal_index=3 if formed is final else 2
                analytic=_advance_same_source_uv(
                    triuv[0],stages.first_axis,
                    (15.,507.,48.,0.,522.,190.,
                     stages.first_ba_trial_mm,
                     stages.first_inner_r_trial_mm+flat.source_spec.thickness/2),
                )[normal_index]
                if sum(n1[j]*analytic[j] for j in range(3))<0:
                    signed+=1
            for i in range(3):
                a,b=triuv[i],triuv[(i+1)%3]
                sk=edge(a,b)
                groups[edge(trixyz[i],trixyz[(i+1)%3])].add(sk)
                if formed is first:
                    source_edges[sk].append((a,b))
        folded_signed_counts.append(signed)
        folded_zero_counts.append(zero)
    source_nonmanifold=sum(len(rows)>2 for rows in source_edges.values())
    source_outer=flat.result_material.boundary
    unpaired_interior=sum(
        len(rows)==1 and
        Point((rows[0][0][0]+rows[0][1][0])/2,
              (rows[0][0][1]+rows[0][1][1])/2).distance(source_outer)>tol
        for rows in source_edges.values()
    )
    world_aliases=tuple(
        [(k,v) for k,v in final_world.items() if len(v)>1]
    )
    axis_witness=[]
    parameters=(15.,507.,48.,0.,522.,190.,
                stages.first_ba_trial_mm,
                stages.first_inner_r_trial_mm+flat.source_spec.thickness/2)
    for corner,uv in (("bottom_left",(7.5,40.5)),
                      ("bottom_right",(514.5,40.5))):
        _,_,n1,_=_advance_same_source_uv(uv,stages.first_axis,parameters)
        if stages.first_axis=="x":
            outside=(0.,-1.,0.)
        else:
            outside=(-1.,0.,0.) if corner=="bottom_left" else (1.,0.,0.)
        if abs(sum(n1[i]*outside[i] for i in range(3)))>1e-7:
            raise GeometryError("TAIL_V90_CARRIED_SECOND_AXIS_NOT_ORTHOGONAL")
        original=_unit(_cross(outside,(0.,0.,1.)))
        carried=_unit(_cross(outside,n1))
        axis_witness.append((corner,original,carried))
    extrema_min=[float("inf")]*3
    extrema_max=[float("-inf")]*3
    for triuv,trixyz in zip(src,final):
        for uv,p in zip(triuv,trixyz):
            n2=_advance_same_source_uv(uv,stages.first_axis,parameters)[3]
            for sign in (-1.,1.):
                outer=tuple(float(p[i]+sign*n2[i]*flat.source_spec.thickness/2)
                            for i in range(3))
                for i in range(3):
                    extrema_min[i]=min(extrema_min[i],outer[i])
                    extrema_max[i]=max(extrema_max[i],outer[i])
    return TailDoubleVRootAudit(
        first_axis=stages.first_axis,
        source_boundary_edge_count=sum(len(rows)==1 for rows in source_edges.values()),
        source_nonmanifold_edge_count=int(source_nonmanifold),
        interior_unpaired_source_edges=int(unpaired_interior),
        first_world_alias_edge_count=sum(len(v)>1 for v in first_world.values()),
        final_world_alias_edge_count=len(world_aliases),
        first_zero_area_face_count=folded_zero_counts[0],
        final_zero_area_face_count=folded_zero_counts[1],
        first_reversed_face_count=folded_signed_counts[0],
        final_reversed_face_count=folded_signed_counts[1],
        second_bend_axis_witnesses=tuple(axis_witness),
        trial_t_outer_bounds_xyz_mm=tuple(
            (float(extrema_min[i]),float(extrema_max[i])) for i in range(3)
        ),
        trial_t_outer_extent_xyz_mm=tuple(
            float(extrema_max[i]-extrema_min[i]) for i in range(3)
        ),
        final_world_alias_source_witnesses=tuple(
            (world_edge,tuple(sorted(uv_edges))[:4])
            for world_edge,uv_edges in world_aliases[:6]
        ),
    )
