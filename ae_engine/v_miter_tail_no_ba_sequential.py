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


def _action(flat_uv, fold):
    x,y=map(float,flat_uv)
    if fold=="y" and y<48.-_TOL:
        # Actual horizontal BEND is ONLY x=16..506, y=48.
        # Stock beyond its endpoints is connected to the same lower lip,
        # carried with the lip; this is NOT an invented longer BEND.
        return ((x,48.,0.),(1.,0.,0.),-_HALF_PI)
    if fold=="x" and y<=190.+_TOL and x<15.-_TOL:
        return ((15.,y,0.),(0.,1.,0.),_HALF_PI)
    if fold=="x" and y<=190.+_TOL and x>507.+_TOL:
        return ((507.,y,0.),(0.,1.,0.),-_HALF_PI)
    if fold not in ("x","y"):
        raise GeometryError("TAIL_V90_SHARP_UNKNOWN_AXIS")
    return None


def _stages(uv,first_axis):
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_V90_SHARP_OPERATOR_ORDER_REQUIRED")
    p=(float(uv[0]),float(uv[1]),0.)
    n=(0.,0.,1.)
    first=_action(uv,first_axis)
    if first is not None:
        origin,axis,theta=first
        p1=_about(p,origin,axis,theta)
        n1=_rotate(n,axis,theta)
    else:
        p1,n1=p,n
    second=_action(uv,"y" if first_axis=="x" else "x")
    if second is None:
        return p1,p1,n1,n1,None
    origin,axis,theta=second
    if first is not None:
        pvt,prior_axis,prior_theta=first
        origin=_about(origin,pvt,prior_axis,prior_theta)
        axis=_rotate(axis,prior_axis,prior_theta)
    p2=_about(p1,origin,axis,theta)
    n2=_rotate(n1,axis,theta)
    return p1,p2,n1,n2,(origin,axis,theta)


def _single_sheet_triangles(stock):
    """Triangulate SAME source stock; lines subdivide tessellation, not BEND."""
    xs=(0.,15.,16.,40.,482.,506.,507.,522.)
    ys=(0.,33.,48.,63.,190.,192.,217.,233.)
    out=[]
    area=0.
    for xl,xr in zip(xs,xs[1:]):
        for yl,yr in zip(ys,ys[1:]):
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
    source,area=_single_sheet_triangles(stock)
    first=[];final=[]
    for tri in source:
        t1=[];t2=[]
        for uv in tri:
            a,b,_,_,_=_stages(uv,first_axis)
            t1.append(a);t2.append(b)
        first.append(tuple(t1));final.append(tuple(t2))
    tracks=[];axes=[];walls=[]
    for corner,lower,apex,upper in flat.opening_source_points_xy:
        for tag,end in (("lower",lower),("upper",upper)):
            mid=tuple((apex[i]+end[i])/2. for i in range(2))
            a,b,_,n2,hinge=_stages(mid,first_axis)
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
            _,low,_,nl,_=_stages(uv_lo,first_axis)
            _,high,_,nh,_=_stages(uv_hi,first_axis)
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
