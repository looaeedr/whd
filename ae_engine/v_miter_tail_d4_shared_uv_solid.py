# -*- coding: utf-8 -*-
"""#3317 isolated Ø4 single-sheet fold candidate (not CHECK/CNC authority).

The ONLY changed source is the two lower V CUTTING corners.  Above their
actual upper V endpoint the same original EndCap Fold owner remains in use.
The true one-piece source UV, not coincident world XYZ, owns every T2 edge.
"""
from collections import defaultdict
from math import dist, sqrt
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .assembly_geometry import _profile_geometry, _prepare_profile_mapper
from .assembly_geometry_primitives import place_endcap_against_box_body
from .sheetmetal_geometry_core import GeometryError
from .v_miter_tail_no_ba_sequential import _single_sheet_triangles, _stages


def _diff(a,b):
    return tuple(float(x-y) for x,y in zip(a,b))


def _plus(a,b):
    return tuple(float(x+y) for x,y in zip(a,b))


def _scale(a,k):
    return tuple(float(x*k) for x in a)


def _dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def _norm(a):
    length=sqrt(_dot(a,a))
    if length<1e-12:
        raise GeometryError("TAIL_D4_SHARED_UV_SOURCE_FACE_COLLAPSED")
    return _scale(a,1./length)


def _normal(tri):
    return _norm(_cross(_diff(tri[1],tri[0]),_diff(tri[2],tri[0])))


def _key(x):
    return tuple(round(float(v),7) for v in x)


def _make_wall(a,b,normal,t):
    off=_scale(normal,t/2.)
    pa,pb,ma,mb=(_plus(a,off),_plus(b,off),
                 _diff(a,off),_diff(b,off))
    return ((pa,pb,mb),(pa,mb,ma))


def _edge_counts(triangles, source_face_ids=(), source_uv=(), seam=None):
    """World-space incidence, retaining UV identity for every open edge."""
    counts=defaultdict(list)
    for face_id,tri in enumerate(triangles):
        for i in range(3):
            a,b=tri[i],tri[(i+1)%3]
            edge=tuple(sorted((_key(a),_key(b))))
            uv_edge=None
            if source_face_ids:
                row=source_face_ids[face_id]
                uv_edge=(row[i],row[(i+1)%3])
            counts[edge].append(uv_edge)
    open_rows=tuple((edge,rows[0]) for edge,rows in counts.items()
                    if len(rows)==1)
    seam_open=0
    if source_face_ids:
        seam_open=sum(1 for _,edge in open_rows if (
            edge is not None
            and abs(source_uv[edge[0]][1]-seam)<1e-7
            and abs(source_uv[edge[1]][1]-seam)<1e-7
        ))
    return (len(open_rows),
            sum(len(v)==4 for v in counts.values()),
            sum(len(v)>2 for v in counts.values()),
            seam_open)


def _wall_contact(groups,corner):
    low=tuple(groups.get((corner,"lower"),()))
    high=tuple(groups.get((corner,"upper"),()))
    if not low or not high:
        raise GeometryError("TAIL_D4_SHARED_UV_TRUE_WALL_MISSING:"+corner)
    anchor=low[0][0]
    e0=_norm(_diff(low[0][1],anchor))
    n=_normal(low[0])
    e1=_cross(n,e0)
    def projected(tris):
        return unary_union(tuple(Polygon(tuple(
            (_dot(_diff(p,anchor),e0),_dot(_diff(p,anchor),e1))
            for p in tri
        )) for tri in tris))
    lo,hi=projected(low),projected(high)
    gap=max(abs(_dot(_diff(p,anchor),n))
            for tri in low+high for p in tri)
    opposed=sum(_dot(n,_normal(tri)) for tri in high)/len(high)
    return {
        "corner":corner,
        "lower_triangles":len(low),
        "upper_triangles":len(high),
        "lower_area":float(lo.area),
        "upper_area":float(hi.area),
        "projected_symmetric_difference_area":float(
            lo.symmetric_difference(hi).area),
        "max_out_of_plane":float(gap),
        "opposed_normal_dot":float(opposed),
        "full_face_contact_proven":(
            gap<=1e-6 and lo.symmetric_difference(hi).area<=1e-6
            and opposed<=-1.+1e-6),
    }


def project_d4_original_owner_uv_solid(
    flat,stock,st,first_axis,x_profile,y_profile,original_bends,
    original_surface,box_body_world,thickness,
):
    """Form the actual FinalScene sheet with sourced two-stage lower corners.

    Only the original Factory EndCap world placement and T/2 skin convention
    are used. NO hidden weld, fabricated cap, XYZ-based source adjacency or
    expanded BEND is allowed. Residual open edges remain visible as evidence.
    """
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_D4_SHARED_UV_ORDER_REQUIRED")
    source,area=_single_sheet_triangles(stock,st)
    if abs(area-stock.area)>1e-5:
        raise GeometryError("TAIL_D4_SHARED_UV_MATERIAL_AREA_LOST")
    # Y threshold is authored by the actual two V cut legs, not by a
    # hardcoded 63-mm station or inferred bounding box.
    upper_ends=tuple(float(upper[1])
                     for _,_,_,upper in flat.opening_source_points_xy)
    if len(upper_ends)!=2 or abs(upper_ends[0]-upper_ends[1])>1e-7:
        raise GeometryError("TAIL_D4_SHARED_UV_V_UPPER_ENDS_DISAGREE")
    seam=upper_ends[0]
    if abs(seam-st.bottom_y-(st.left_x-st.xmin))>1e-7:
        raise GeometryError("TAIL_D4_SHARED_UV_SEAM_NOT_FACTORY_V_ENDPOINT")
    xb,xf=_profile_geometry(x_profile)
    yb,yf=_profile_geometry(y_profile)
    xm=_prepare_profile_mapper(x_profile,axis="x",
        fold_guides=original_bends,geometry=(xb,xf))
    ym=_prepare_profile_mapper(y_profile,axis="y",
        fold_guides=original_bends,geometry=(yb,yf))
    def native(uv):
        x,y=uv
        xx,zx=xm(x,y)
        yy,zy=ym(y,x)
        return (float(xx),float(yy),float(zx+zy))
    core=((st.bottom_guide_start+st.bottom_guide_end)/2.,seam)
    anchor_delta=_diff(native(core),_stages(core,first_axis,st)[1])
    def final(uv):
        if uv[1] <= seam+1e-7:
            return _plus(_stages(uv,first_axis,st)[1],anchor_delta)
        return native(uv)
    # Every original V/upper boundary vertex is required to have exactly
    # one physical position. Do not add a bridge to hide a datum mismatch.
    seam_uv={tuple(float(x) for x in uv)
             for tri in source for uv in tri
             if abs(float(uv[1])-seam)<1e-7}
    seam_gaps=tuple((uv,dist(native(uv),
                           _plus(_stages(uv,first_axis,st)[1],anchor_delta)))
                    for uv in sorted(seam_uv))
    if not seam_gaps or max(v for _,v in seam_gaps)>1e-6:
        raise GeometryError("TAIL_D4_SHARED_UV_SEAM_DISCONTINUOUS:"
                            +repr(sorted(seam_gaps,key=lambda x:-x[1])[:5]))
    source_uv=[]
    uv_index={}
    faces=[]
    for tri in source:
        inds=[]
        for uv in tri:
            k=_key(uv)
            if k not in uv_index:
                uv_index[k]=len(source_uv)
                source_uv.append(tuple(map(float,uv)))
            inds.append(uv_index[k])
        if len(set(inds))!=3:
            raise GeometryError("TAIL_D4_SHARED_UV_TRIANGLE_COLLAPSED")
        faces.append(tuple(inds))
    local_vertices=tuple(final(uv) for uv in source_uv)
    local_surface=tuple(tuple(local_vertices[i] for i in face)
                        for face in faces)
    # The ORIGINAL uncut sheet determines the EndCap assembly origin.
    # This is the exact existing Engine placement, not a Z/T patch.
    world_surface=place_endcap_against_box_body(
        local_surface,"bottom",box_body_world,
        sheet_thickness=thickness,
        preserve_core_origin=False,reference_triangles=original_surface,
    )
    world_vertices={}
    for face,triangle in zip(faces,world_surface):
        for i,point in zip(face,triangle):
            if i in world_vertices and dist(world_vertices[i],point)>1e-7:
                raise GeometryError("TAIL_D4_SHARED_UV_WORLD_VERTEX_DRIFT")
            world_vertices[i]=point
    world_vertices=tuple(world_vertices[i] for i in range(len(source_uv)))
    normals=tuple(_normal(tri) for tri in world_surface)
    t=float(thickness)
    # Maintain the original Engine T/2 convention on EVERY physical panel;
    # finite source UV edges own edge walls, never coincident world XYZ.
    solid=[]
    solid_source_ids=[]
    edges=defaultdict(list)
    for fid,(face,tri,n) in enumerate(zip(faces,world_surface,normals)):
        off=_scale(n,t/2.)
        plus=tuple(_plus(p,off) for p in tri)
        minus=tuple(_diff(p,off) for p in tri)
        solid.extend((plus,(minus[0],minus[2],minus[1])))
        solid_source_ids.extend((face,(face[0],face[2],face[1])))
        for j in range(3):
            a,b=face[j],face[(j+1)%3]
            edges[tuple(sorted((a,b)))].append((a,b,n,fid))
    if any(len(group)>2 for group in edges.values()):
        raise GeometryError("TAIL_D4_SHARED_UV_NONMANIFOLD_SOURCE")
    groups=defaultdict(list)
    for edge,neighbors in edges.items():
        a,b,n,fid=neighbors[0]
        pa,pb=world_vertices[a],world_vertices[b]
        if len(neighbors)==1:
            walls=_make_wall(pa,pb,n,t)
            solid.extend(walls)
            solid_source_ids.extend(((a,b,b),(a,b,a)))
            line=LineString((source_uv[a],source_uv[b]))
            if line.length>1e-7:
                for corner,lower,apex,upper in flat.opening_source_points_xy:
                    for label,tip in (("lower",lower),("upper",upper)):
                        if line.difference(LineString((apex,tip)).buffer(3e-7)).length<=1e-7:
                            groups[(corner,label)].extend(walls)
        else:
            na=neighbors[1][2]
            if abs(_dot(n,na))>=1.-1e-6:
                continue
            oa,ob=_scale(n,t/2.),_scale(na,t/2.)
            aplus,bplus=_plus(pa,oa),_plus(pb,oa)
            cplus,dplus=_plus(pa,ob),_plus(pb,ob)
            aminus,bminus=_diff(pa,oa),_diff(pb,oa)
            cminus,dminus=_diff(pa,ob),_diff(pb,ob)
            solid.extend(((aplus,bplus,dplus),(aplus,dplus,cplus),
                          (aminus,cminus,dminus),(aminus,dminus,bminus)))
            solid_source_ids.extend(((a,b,b),(a,b,a),(a,a,b),(a,b,b)))
    seams=tuple(_wall_contact(groups,corner)
                for corner,_,_,_ in flat.opening_source_points_xy)
    if len(solid)!=len(solid_source_ids):
        raise GeometryError("TAIL_D4_SHARED_UV_PHYSICAL_FACE_IDENTITY_LOST")
    open_count,four_count,multi_count,seam_open=_edge_counts(
        solid,solid_source_ids,source_uv,seam,
    )
    return {
        "source_uv":tuple(source_uv),
        "source_faces":tuple(faces),
        "v_surface":tuple(world_surface),
        "v_solid":tuple(solid),
        "straight_v_wall_sets":seams,
        "open_world_edges":open_count,
        "four_world_edges":four_count,
        "multi_world_edges":multi_count,
        "open_seam_world_edges":seam_open,
        "seam_uv_positions":seam_gaps,
        "source_area_mm2":area,
        "manufacturing_approved":False,
        "status":"D4_SHARED_UV_SEQUENTIAL_ROOT_OPEN_CHECK_ONLY",
    }
