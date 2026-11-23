# -*- coding: utf-8 -*-
"""#3317: corrected 522x233 Vault Tail dual-V sequential 90° sharp CHECK.

The user-confirmed specimen has NO BA. Do not ask for one, silently invent
a radius, or reuse obsolete R/BA seam gaps. The *existing* WHD material
profiles are the nominal outside-dimension owner. Source flat V walls remain
separate throughout the first and second rigid folds.

This is a read-only, sharp, radius-free kinematic/cut-wall comparison.
T=2 cut-wall coincidence is not a proof that the intersecting crease root
forms a closed physical solid, and does not authorize a machining DXF.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import box

from .sheetmetal_geometry_core import GeometryError
from .v_miter_true_t_collision import _source_triangulation

_HALF_PI=math.pi/2
_TOL=1e-7


@dataclass(frozen=True)
class LowerDualVStations:
    """Only source-derived physical fold stations, no nominal size whitelist."""
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    left_x: float
    right_x: float
    bottom_y: float
    bottom_guide_start: float
    bottom_guide_end: float
    left_side_end: float
    right_side_end: float
    upper_start: float
    upper_crease: float

    @classmethod
    def regression_522x233(cls):
        # Backward-compatible tests that exercise _stages(uv,axis) directly.
        # Real preview always calls from_flat and NEVER this fixed sample.
        return cls(0.,522.,0.,233.,15.,507.,48.,16.,506.,
                   190.,190.,192.,217.)


def stations_from_real_flat(flat) -> LowerDualVStations:
    """Derive true finite BEND, upper profile and source boundaries.

    Reject a geometrically impossible corner for the reason it is impossible,
    not because the job's W/D/T or part name differs from the 522 example.
    """
    from .manufacturing_render_data import fold_guides_from_final_scene
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .sheetmetal_geometry_core import GeometryError

    xmin,ymin,xmax,ymax=map(float,flat.result_material.bounds)
    points={row[0]:row for row in flat.opening_source_points_xy}
    if set(points)!={"bottom_left","bottom_right"}:
        raise GeometryError("V_MITER_LOWER_TWO_SOURCE_CORNER_OPENINGS_REQUIRED")
    lx,ly=points["bottom_left"][2]
    rx,ry=points["bottom_right"][2]
    if (not xmin<lx<rx<xmax or abs(ly-ry)>_TOL
            or not ymin<ly<ymax):
        raise GeometryError("V_MITER_LOWER_BEND_INTERSECTION_TOPOLOGY_INVALID")
    extensions={round(row[0],7):row for row in flat.side_bend_source_extensions}
    try:
        lend=extensions[round(lx,7)][3]
        rend=extensions[round(rx,7)][3]
    except KeyError as exc:
        raise GeometryError("V_MITER_LOWER_SIDE_BEND_SOURCE_MISSING") from exc
    guides=fold_guides_from_final_scene(flat.result_scene)
    horizontal=[
        g for g in guides if g.axis=="y" and abs(g.position-ly)<_TOL
        and g.span_start >= lx-_TOL and g.span_end <= rx+_TOL
        and g.span_end > g.span_start+_TOL
    ]
    if len(horizontal)!=1:
        raise GeometryError("V_MITER_LOWER_FINITE_BOTTOM_BEND_GUIDE_INVALID")
    segment=horizontal[0]
    spec=flat.source_spec
    snapshot=dict(model=spec.model_name,w=spec.width,d=spec.depth,
                  t=spec.thickness,fw=spec.frame_width,yl1=spec.fold_left,
                  yr1=spec.fold_right,ytop1=spec.fold_top,
                  ybottom1=spec.fold_bottom)
    owner=build_endcap_xy_fold_profiles(snapshot,part_key="tail")["Y"]
    if (len(owner)!=4
            or tuple(row.get("phase6_key") for row in owner)!=(
                "ybottom1","endcap_d_core","fw","ytop1")
            or any(
                "angle" not in row if i<3 else "angle" in row
                for i,row in enumerate(owner)
            )):
        raise GeometryError("V_MITER_LOWER_UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID:OWNER")
    # Same original finite BEND geometry as the real factory; no copied
    # rounded UI segment lengths are allowed in this physical V check.
    source_y=sorted(
        (g for g in fold_guides_from_final_scene(flat.original_scene)
         if g.axis=="y"),key=lambda g:g.position
    )
    result_y=sorted((g for g in guides if g.axis=="y"),key=lambda g:g.position)
    if (len(source_y)!=3 or len(result_y)!=3
            or any(
                abs(a.position-b.position)>_TOL
                or abs(a.span_start-b.span_start)>_TOL
                or abs(a.span_end-b.span_end)>_TOL
                for a,b in zip(source_y,result_y)
            )):
        raise GeometryError("V_MITER_LOWER_UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID:BEND_CHANGED")
    breaks=(ymin,)+tuple(float(g.position) for g in source_y)+(ymax,)
    if (abs(breaks[1]-ly)>_TOL
            or any(b<=a+_TOL for a,b in zip(breaks,breaks[1:]))):
        raise GeometryError("V_MITER_LOWER_UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID:FINITE_GUIDES")
    # Validate upper BEND against the ORIGINAL upper stepped CUTTING,
    # independently of the editor's rounded core segment value. The first
    # upper crease bisects the pair of factory notch shelf levels; the last
    # upper crease leaves exactly the unaltered terminal fold material.
    # A moved BEND with unchanged CUTTING must still be rejected.
    upper_levels=sorted({
        float(y) for _,y in flat.original_factory_material.exterior.coords
        if float(y)>max(float(lend),float(rend))+_TOL
    })
    if (abs(float(lend)-float(rend))>_TOL or
            len(upper_levels)<2 or
            abs((float(lend)+upper_levels[0])/2.-breaks[2])>_TOL or
            not breaks[2]+_TOL<upper_levels[0]<breaks[3]-_TOL or
            abs(ymax-breaks[3]-float(spec.fold_top))>_TOL):
        raise GeometryError(
            "V_MITER_LOWER_UNCHANGED_UPPER_FOLD_TOPOLOGY_INVALID:"
            f" current_CUTTING_Y={ymax:.6f}"
            f" current_BEND_Y={breaks[1:4]}"
            f" upper_CUTTING_STEP={tuple(upper_levels)}"
        )
    y_profile=owner
    # A 90-degree sharp root requires actual perpendicular source rays.
    if any(row.get("angle") is not None and abs(abs(float(row["angle"]))-90.)>_TOL
           for row in y_profile):
        raise GeometryError("V_MITER_LOWER_SHARP_ROOT_FOLD_ANGLE_NOT_90")
    return LowerDualVStations(
        xmin,xmax,ymin,ymax,float(lx),float(rx),float(ly),
        float(segment.span_start),float(segment.span_end),
        float(lend),float(rend),float(breaks[2]),float(breaks[3]),
    )


def exact_tail_y_fold_profile_from_original_bends(flat, stations=None):
    """Unrounded material segments from the same CUTTING and real finite BEND.

    Only the #3317 V projection uses this source-exact view. All four
    segments retain the existing Engine-owned phase6_key/angle/UI metadata;
    the canonical editor Fold Profile and original scene are not mutated.
    """
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .assembly_geometry_folded_mesh import _profile_geometry
    st=stations if stations is not None else stations_from_real_flat(flat)
    spec=flat.source_spec
    snapshot=dict(model=spec.model_name,w=spec.width,d=spec.depth,
                  t=spec.thickness,fw=spec.frame_width,yl1=spec.fold_left,
                  yr1=spec.fold_right,ytop1=spec.fold_top,
                  ybottom1=spec.fold_bottom)
    owned=build_endcap_xy_fold_profiles(snapshot,part_key="tail")["Y"]
    physical=(st.ymin,st.bottom_y,st.upper_start,st.upper_crease,st.ymax)
    exact=tuple(
        {**dict(row),"len":float(b-a)}
        for row,a,b in zip(owned,physical,physical[1:])
    )
    readback,_=_profile_geometry(exact)
    if (len(exact)!=4 or len(readback)!=5
            or any(abs(a-b)>_TOL for a,b in zip(readback,physical))):
        raise GeometryError("V_MITER_LOWER_EXACT_SOURCE_BEND_RECONSTRUCTION_FAILED")
    return exact


def _rotate(v, axis, theta):
    """Rigid Rodrigues operation: direction is carried with prior fold."""
    s,c=math.sin(theta),math.cos(theta)
    dot=sum(v[i]*axis[i] for i in range(3))
    cross=(axis[1]*v[2]-axis[2]*v[1],
           axis[2]*v[0]-axis[0]*v[2],
           axis[0]*v[1]-axis[1]*v[0])
    return tuple(float(c*v[i]+s*cross[i]+(1-c)*dot*axis[i])
                 for i in range(3))


def _about(p, origin, axis, theta):
    v=_rotate(tuple(p[i]-origin[i] for i in range(3)),axis,theta)
    return tuple(float(origin[i]+v[i]) for i in range(3))


def _action(flat_uv, fold, stations=None):
    st=stations or LowerDualVStations.regression_522x233()
    x,y=map(float,flat_uv)
    if fold=="y" and y<st.bottom_y-_TOL:
        # Actual horizontal BEND is ONLY x=16..506, y=48.
        # Stock beyond its endpoints is connected to the same lower lip,
        # carried with the lip; this is NOT an invented longer BEND.
        return ((x,st.bottom_y,0.),(1.,0.,0.),-_HALF_PI)
    if fold=="x" and y<=st.left_side_end+_TOL and x<st.left_x-_TOL:
        return ((st.left_x,y,0.),(0.,1.,0.),_HALF_PI)
    if fold=="x" and y<=st.right_side_end+_TOL and x>st.right_x+_TOL:
        return ((st.right_x,y,0.),(0.,1.,0.),-_HALF_PI)
    if fold not in ("x","y"):
        raise GeometryError("TAIL_V90_SHARP_UNKNOWN_AXIS")
    return None


def _stages(uv,first_axis,stations=None):
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_V90_SHARP_OPERATOR_ORDER_REQUIRED")
    p=(float(uv[0]),float(uv[1]),0.)
    n=(0.,0.,1.)
    first=_action(uv,first_axis,stations)
    if first is not None:
        origin,axis,theta=first
        p1=_about(p,origin,axis,theta)
        n1=_rotate(n,axis,theta)
    else:
        p1,n1=p,n
    second=_action(uv,"y" if first_axis=="x" else "x",stations)
    if second is None:
        return p1,p1,n1,n1,None
    origin,axis,theta=second
    # The finite BEND owner matters. If X is first, the genuine Y crease
    # x=16..506 lies in the still-flat MAIN sheet, so its world X axis
    # does NOT rotate with the outboard corner! The attached lower-lip tip
    # follows that unchanged axis as a rigid continuation, not a new BEND.
    # If Y is first, the lower portion of X=15/507 lies in the rotated
    # lip and its second axis is carried from world Y into world +/-Z.
    if first is not None and first_axis=="y":
        pvt,prior_axis,prior_theta=first
        origin=_about(origin,pvt,prior_axis,prior_theta)
        axis=_rotate(axis,prior_axis,prior_theta)
    p2=_about(p1,origin,axis,theta)
    n2=_rotate(n1,axis,theta)
    return p1,p2,n1,n2,(origin,axis,theta)


def _single_sheet_triangles(
    stock,stations=None,*,extra_x=(),extra_y=(),
):
    """Triangulate actual CUTTING at source crease/endpoint stations.

    Optional nominal T-shell splits preserve the exact CUTTING boundary and
    material area. The original call has the same source crease stations.
    """
    st=stations or LowerDualVStations.regression_522x233()
    left_delta=st.left_x-st.xmin
    right_delta=st.xmax-st.right_x
    base_x=tuple(sorted(set((
        st.xmin,st.left_x,st.bottom_guide_start,
        st.bottom_guide_end,st.right_x,st.xmax,
    ))))
    lower_x=tuple(sorted(set(base_x+tuple(float(x) for x in extra_x))))
    ys=tuple(sorted(set((
        st.ymin,st.bottom_y-left_delta,
        st.bottom_y-right_delta,st.bottom_y,
        st.bottom_y+left_delta,st.bottom_y+right_delta,
        st.left_side_end,st.right_side_end,
        st.upper_start,st.upper_crease,st.ymax,
    )+tuple(float(y) for y in extra_y))))
    out=[]
    area=0.
    for yl,yr in zip(ys,ys[1:]):
        for xl,xr in zip(lower_x,lower_x[1:]):
            cut=stock.intersection(box(xl,yl,xr,yr))
            parts=[cut] if cut.geom_type=="Polygon" else [
                g for g in getattr(cut,"geoms",())
                if g.geom_type=="Polygon" and g.area>_TOL
            ]
            for piece in parts:
                if piece.area<=_TOL:continue
                for tri in _source_triangulation(piece):
                    out.append(tri)
                    a,b,c=tri
                    area+=abs((b[0]-a[0])*(c[1]-a[1])-
                              (b[1]-a[1])*(c[0]-a[0]))/2.
    if not out or abs(area-stock.area)>max(1e-5,stock.area*1e-7):
        raise GeometryError("TAIL_V90_SHARP_SOURCE_AREA_LOST")
    return tuple(out),float(area)


@dataclass(frozen=True)
class TailNoBASharpSequentialCheck:
    first_axis: str
    original_source_triangles: tuple
    first_stage_triangles: tuple
    second_stage_triangles: tuple
    original_source_area_mm2: float
    triangulated_source_area_mm2: float
    # (corner, source-edge name, flat XY, first XYZ, final XYZ, final normal)
    midpoint_tracks: tuple
    # (corner, transported second X hinge axis after first Y action)
    carried_second_axes: tuple
    # (corner, original leg length, max +/-T/2 wall station residual)
    paired_T_wall: tuple
    nominal_outside_mm: tuple
    thickness_mm: float
    shape_reference: str = "ORIGINAL_CORRECTED_CUTTING_Y0_SIDE_BEND"
    method: str = "SHARP_RIGID_TWO_STAGE_NO_BA_NO_RADIUS_CHECK"
    root_status: str = "TRUE_T_ROOT_STILL_UNCERTIFIED"
    manufacturing_approved: bool = False


def project_tail_v90_no_ba_sequential_check(flat, *, first_axis: str):
    """One Factory material, 2 source V legs/corner, full affine sharp-wall check."""
    from .v_miter_tail_sharp_no_ba_witness import project_tail_sharp_no_ba_v_witness
    # WHD's existing sharp profile & finite BEND readback already checks
    # all five physical guides and resolves nominal outside 496/148/50/17.
    witness=project_tail_sharp_no_ba_v_witness(flat)
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_V90_SHARP_OPERATOR_ORDER_REQUIRED")
    stock=flat.result_material
    st=stations_from_real_flat(flat)
    source,area=_single_sheet_triangles(stock,st)
    first=[];final=[]
    for tri in source:
        t1=[];t2=[]
        for uv in tri:
            a,b,_,_,_=_stages(uv,first_axis,st)
            t1.append(a);t2.append(b)
        first.append(tuple(t1));final.append(tuple(t2))
    tracks=[];axes=[];walls=[]
    for corner,lower,apex,upper in flat.opening_source_points_xy:
        for tag,end in (("lower",lower),("upper",upper)):
            mid=tuple((apex[i]+end[i])/2. for i in range(2))
            a,b,_,n2,hinge=_stages(mid,first_axis,st)
            tracks.append((corner,tag,mid,a,b,n2))
            if tag=="lower":
                if hinge is None:
                    raise GeometryError("TAIL_V90_SHARP_CARRIED_SECOND_AXIS_MISSING")
                axes.append((corner,hinge[1]))
        # For two exact straight source legs, the composed rigid rotations
        # are affine along the whole leg. Compare both T=2 +/-1 mm
        # cut-wall boundaries at 33 stations including both ends.
        deviations=[]
        for station in range(33):
            f=station/32.
            uv_lo=tuple(apex[i]+f*(lower[i]-apex[i]) for i in (0,1))
            uv_hi=tuple(apex[i]+f*(upper[i]-apex[i]) for i in (0,1))
            _,low,_,nl,_=_stages(uv_lo,first_axis,st)
            _,high,_,nh,_=_stages(uv_hi,first_axis,st)
            for sign in (-1.,1.):
                p=tuple(low[i]+sign*nl[i]*witness.physical_sheet_thickness_mm/2.
                        for i in range(3))
                q=tuple(high[i]+sign*nh[i]*witness.physical_sheet_thickness_mm/2.
                        for i in range(3))
                deviations.append(math.dist(p,q))
        walls.append((
            corner,math.dist(tuple(apex),tuple(lower)),max(deviations),
        ))
    return TailNoBASharpSequentialCheck(
        first_axis=first_axis,
        original_source_triangles=source,
        first_stage_triangles=tuple(first),
        second_stage_triangles=tuple(final),
        original_source_area_mm2=float(stock.area),
        triangulated_source_area_mm2=area,
        midpoint_tracks=tuple(tracks),
        carried_second_axes=tuple(axes),
        paired_T_wall=tuple(walls),
        nominal_outside_mm=witness.nominal_outside_mm,
        thickness_mm=witness.physical_sheet_thickness_mm,
    )
