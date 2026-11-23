# -*- coding: utf-8 -*-
"""#3317 isolated sharp 90-degree T-shell hinge redistribution (NOT CNC).

The same source UV material remains authoritative.  A pair of *actually
adjacent*, orthogonally folded source faces shares a thickness partition at
the real crease; world-coincident but source-unrelated V walls are never
welded.  This is a nominal section trial, not a plastic bend law, R or BA.
"""
from collections import defaultdict
from math import dist, isfinite, sqrt

from shapely.geometry import LineString, Point

from .sheetmetal_geometry_core import GeometryError


def _sub(a,b):
    return tuple(float(x-y) for x,y in zip(a,b))


def _add(a,b):
    return tuple(float(x+y) for x,y in zip(a,b))


def _mul(a,x):
    return tuple(float(y*x) for y in a)


def _dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def _normal(tri):
    n=_cross(_sub(tri[1],tri[0]),_sub(tri[2],tri[0]))
    m=sqrt(_dot(n,n))
    if m<=1e-12:
        raise GeometryError("TAIL_D4_NOMINAL_DEGENERATE_SOURCE_FACE")
    return _mul(n,1./m)


def _key(a):
    return tuple(round(float(q),7) for q in a)


def nominal_hinge_width(flat,thickness,stations):
    """Source-derived nominal h; no silently selected tool R/BA.

    Measure from each real upper V CUTTING leg to the true source side
    crease at a physical one-T station above the source apex.  For the
    approved 90-degree W620/T2 source, clearance=sqrt(2) mm.
    """
    t=float(thickness)
    if not isfinite(t) or t<=0:
        raise GeometryError("TAIL_D4_NOMINAL_THICKNESS_INVALID")
    clears=[]
    for corner,lower,apex,upper in flat.opening_source_points_xy:
        line=LineString((apex,upper))
        if line.length<=1e-7:
            raise GeometryError("TAIL_D4_NOMINAL_V_SOURCE_MISSING")
        side_x=(stations.left_x if "left" in corner else stations.right_x)
        if abs(float(apex[0])-side_x)>1e-7:
            raise GeometryError("TAIL_D4_NOMINAL_V_CREASE_NOT_SOURCE")
        clears.append(line.distance(Point(side_x,float(apex[1])+t)))
    if len(clears)!=2 or abs(clears[0]-clears[1])>1e-7:
        raise GeometryError("TAIL_D4_NOMINAL_V_CLEARANCE_ASYMMETRIC")
    h=(t/2.+min(clears))/2.
    if h<=t/2.+1e-8 or h>=min(
        stations.left_x-stations.xmin,stations.xmax-stations.right_x
    )-1e-7:
        raise GeometryError("TAIL_D4_NOMINAL_HINGE_WIDTH_NONINVERTIBLE")
    return float(h)


def nominal_section_map(s,signed_t,h,*,panel):
    """One of the two disjoint monotone section images A/B.

    A(s,t)=(s+(1-s/h)*t,t); B(s,t)=(t,s+(1-s/h)*t).
    They meet only at s=0, where both maps equal (t,t).
    """
    s,t,h=map(float,(s,signed_t,h))
    if h<=abs(t)+1e-10 or not 0<=s<=h+1e-9:
        raise GeometryError("TAIL_D4_NOMINAL_SECTION_JACOBIAN_NONPOSITIVE")
    v=s+(1.-s/h)*t
    if panel=="a":
        return (v,t)
    if panel=="b":
        return (t,v)
    raise GeometryError("TAIL_D4_NOMINAL_SECTION_PANEL_INVALID")


def nominal_adjacent_source_skins(faces,source_uv,world_surface,t,st,h):
    """Face-vertex +/-T/2 locations from real source-adjacent crease faces.

    The only input neighbors are two faces sharing a genuine source UV
    hinge edge.  Do not merge unrelated V walls even if XYZ is identical.
    The source triangulation must be split at x/y=crease +/- h; this keeps
    nominal offsets linear per triangle without changing CUTTING.
    """
    if len(faces)!=len(world_surface) or t<=0 or h<=t/2.:
        raise GeometryError("TAIL_D4_NOMINAL_SOURCE_GEOMETRY_INVALID")
    normals=tuple(_normal(tri) for tri in world_surface)
    source_edges=defaultdict(list)
    for fid,face in enumerate(faces):
        for j in range(3):
            a,b=face[j],face[(j+1)%3]
            source_edges[tuple(sorted((a,b)))].append((fid,a,b))
    hinge_segments=[]
    for (a,b),neighbor in source_edges.items():
        if len(neighbor)!=2:
            continue
        na,nb=(normals[row[0]] for row in neighbor)
        if abs(_dot(na,nb))>1e-6:
            continue
        ua,ub=source_uv[a],source_uv[b]
        axis=None
        station=None
        if abs(ua[0]-ub[0])<1e-7:
            for x in (st.left_x,st.right_x):
                if abs(ua[0]-x)<1e-7:
                    axis=0
                    station=x
                    break
        elif abs(ua[1]-ub[1])<1e-7 and abs(ua[1]-st.bottom_y)<1e-7:
            axis=1
            station=st.bottom_y
        if axis is None:
            continue
        along=1-axis
        lo,hi=sorted((ua[along],ub[along]))
        if hi-lo<=1e-8:
            continue
        if axis==0:
            end=st.left_side_end if station==st.left_x else st.right_side_end
            if lo>end+1e-7:
                continue
        elif hi<st.bottom_guide_start-1e-7 or lo>st.bottom_guide_end+1e-7:
            continue
        hinge_segments.append((axis,station,lo,hi,na,nb))
    if not hinge_segments:
        raise GeometryError("TAIL_D4_NOMINAL_SOURCE_ADJACENT_HINGE_MISSING")
    used_hinges=set()
    layers=[]
    upper_cutoff=max(st.left_side_end,st.right_side_end)
    for fid,(face,tri,n) in enumerate(zip(faces,world_surface,normals)):
        # Do not deform the ORIGINAL upper cap side of the finite X-BEND
        # endpoint. The lower-to-upper transition may remain physically
        # unresolved; it must not be hidden by changing native upper skins.
        if min(source_uv[i][1] for i in face)>=upper_cutoff-1e-7:
            off=_mul(n,t/2.)
            layers.append(tuple((_add(p,off),_sub(p,off)) for p in tri))
            continue
        vlayers=[]
        for vertex_id,p in zip(face,tri):
            uv=source_uv[vertex_id]
            candidates=[]
            for axis,station,lo,hi,na,nb in hinge_segments:
                s=abs(uv[axis]-station)
                if s>h+1e-7 or uv[1-axis]<lo-1e-7 or uv[1-axis]>hi+1e-7:
                    continue
                if _dot(n,na)>=1.-1e-6:
                    other=nb
                elif _dot(n,nb)>=1.-1e-6:
                    other=na
                else:
                    continue
                candidates.append((axis,station,other,max(0.,s)))
            unique={(axis,round(station,7)) for axis,station,_,_ in candidates}
            if len(unique)>1:
                # Genuine three-panel crease crossings need their OWN
                # volumetric law; a 2-panel transition is not sufficient.
                raise GeometryError(
                    "TAIL_D4_NOMINAL_TWO_HINGE_SOURCE_MATERIAL_OVERLAP:"
                    +repr((uv,tuple(sorted(unique))))
                )
            shift=n
            if candidates:
                axis,station,other,s=candidates[0]
                blend=max(0.,min(1.,1.-s/h))
                shift=_add(n,_mul(other,blend))
                used_hinges.add((axis,round(station,7)))
            offset=_mul(shift,t/2.)
            vlayers.append((_add(p,offset),_sub(p,offset)))
        layers.append(tuple(vlayers))
    if not {(0,round(st.left_x,7)),(0,round(st.right_x,7)),
            (1,round(st.bottom_y,7))}.issubset(used_hinges):
        raise GeometryError("TAIL_D4_NOMINAL_SOURCE_HINGE_SCOPE_INCOMPLETE")
    return tuple(layers)
