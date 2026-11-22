# -*- coding: utf-8 -*-
"""#3317 Vault Tail full one-sheet T2 sharp-fold lower V CHECK, no BA/R.

Reuses the unchanged WHD upper Y Fold Profile and the verified dual-order
lower rigid motion. Physical hole CUTTING is resolved from the SAME corrected
FinalScene, not the outer-only `flat.result_material`. The fold-coordinate
surface is the WHD inside material datum; the outer face is displaced by
the actual material thickness ONCE, consistent with CURRENT 07 outside
readback. No imaginary +/-T/2 mid-surface or BA is introduced.

The shell has source-keyed vertices. Two different V CUTTING edges may
coincide in world XYZ as a real contacting miter, but are NEVER welded
together or used as evidence of volumetric nonpenetration.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point

from .sheetmetal_geometry_core import GeometryError
from .manufacturing_render_data import material_polygon_from_final_scene
from .v_miter_tail_no_ba_sequential import _single_sheet_triangles, _stages
from .v_miter_tail_sharp_no_ba_witness import project_tail_sharp_no_ba_v_witness

_EPS=1e-7


@dataclass(frozen=True)
class TailV90FullT2SolidCheck:
    first_axis: str
    source_material_with_holes: object
    source_triangles: tuple
    world_inside_skin_triangles: tuple
    # Indexed source topology: not welded merely because two V faces touch.
    vertices_xyz: tuple
    indexed_triangle_faces: tuple
    source_boundary_edge_count: int
    source_hole_count: int
    source_hole_wall_segment_counts: tuple
    source_nonmanifold_edge_count: int
    shell_nonmanifold_edge_count: int
    shell_winding_error_edge_count: int
    shell_signed_volume_mm3: float
    formed_outer_bounds_xyz_mm: tuple
    formed_outer_extents_xyz_mm: tuple
    formed_side_outside_reach_mm: float
    formed_bottom_outside_reach_mm: float
    # (corner, upper/lower source V CUTTING-wall triangle counts,
    #  world positional mismatch, opposing actual wall normals)
    true_t_v_seam_contact: tuple
    actual_upper_fold_sample_xyz: tuple
    nominal_outside_mm: tuple
    thickness_mm: float
    hole_wall_status: str = "SAME_SOURCE_INNER_WALLS_PRESENT"
    root_topology_status: str = "SOURCE_KEYED_WATERTIGHT_SHELL"
    volume_nonpenetration_status: str = "NOT_YET_CERTIFIED_BY_SOLID_INTERSECTION"
    manufacturing_approved: bool = False


def _v3sub(a,b):
    return tuple(a[i]-b[i] for i in range(3))


def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def _dot(a,b):
    return sum(a[i]*b[i] for i in range(3))


def _unit(v):
    length=math.sqrt(_dot(v,v))
    if length<=1e-10 or not math.isfinite(length):
        raise GeometryError("TAIL_V90_T2_ZERO_OR_FOLDED_BACK_TRIANGLE")
    return tuple(v[i]/length for i in range(3))


def project_tail_v90_full_t_no_ba(flat, *, first_axis: str):
    """One real 522x233 corrected FinalScene -> full top+bottom T2 sheet.

    The cut wall remains a boundary of the original source sheet. The upper
    fold geometry is read from WHD's owner; nothing in the Y upper profile
    or its independent CUTTING is edited. Only the lower Y0 dual V uses
    the already-verified two-stage sharp transform.
    """
    from .v_miter_tail_user_image_source import TailIllustratedSideV90Flat
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .assembly_geometry_folded_mesh import _profile_geometry, _profile_map

    if (not isinstance(flat,TailIllustratedSideV90Flat)
            or first_axis not in ("x","y") or flat.manufacturing_approved):
        raise GeometryError("TAIL_V90_T2_FULL_CORRECTED_FACTORY_REQUIRED")
    qualified=project_tail_sharp_no_ba_v_witness(flat)
    thickness=float(qualified.physical_sheet_thickness_mm)
    if abs(thickness-2.)>_EPS:
        raise GeometryError("TAIL_V90_T2_FULL_THICKNESS_DRIFT")
    stock=material_polygon_from_final_scene(flat.result_scene)
    if (stock.geom_type!="Polygon" or not stock.is_valid or stock.is_empty
            or len(stock.interiors)!=4
            or stock.symmetric_difference(flat.result_material).area < 0.5):
        raise GeometryError("TAIL_V90_T2_FULL_HOLES_OR_SOURCE_MISSING")
    outer_only=flat.result_material
    if (not outer_only.covers(stock) or
            stock.difference(outer_only).area>_EPS or
            outer_only.difference(stock).area<=0):
        raise GeometryError("TAIL_V90_T2_FULL_NOT_SAME_FACTORY_CUTTING")
    source,area=_single_sheet_triangles(stock)
    if abs(area-stock.area)>max(1e-5,stock.area*1e-7):
        raise GeometryError("TAIL_V90_T2_FULL_CUTTING_AREA_LOST")

    s=flat.source_spec
    snapshot=dict(model=s.model_name,w=s.width,d=s.depth,t=s.thickness,
                  fw=s.frame_width,yl1=s.fold_left,yr1=s.fold_right,
                  ytop1=s.fold_top,ybottom1=s.fold_bottom)
    profiles=build_endcap_xy_fold_profiles(snapshot,part_key="tail")
    _,yfold=_profile_geometry(profiles["Y"])
    ybreak,_=_profile_geometry(profiles["Y"])
    if len(ybreak)!=5 or any(abs(ybreak[i]-q)>_EPS for i,q in enumerate(
            (0.,48.,192.,217.,233.))):
        raise GeometryError("TAIL_V90_T2_FULL_UPPER_PROFILE_CHANGED")
    u0,z0=_profile_map(48.,ybreak,yfold)

    def formed(uv):
        x,y=map(float,uv)
        if y<=192.+_EPS:
            # Corrected lower material and the unchanged central datum.
            return _stages((x,y),first_axis)[1]
        # All source material above y=192 is between x=16 and x=506.
        # No fabricated side BEND is allowed in this original upper band.
        if x<16.-_EPS or x>506.+_EPS:
            raise GeometryError("TAIL_V90_T2_FULL_UPPER_STOCK_CHANGED")
        uy,uz=_profile_map(y,ybreak,yfold)
        return (x,float(48.+uy-u0),float(uz-z0))

    uv_index={}
    vertices_uv=[]
    index_faces=[]
    for tri in source:
        face=[]
        for xy in tri:
            key=tuple(round(float(q)/_EPS) for q in xy)
            if key not in uv_index:
                uv_index[key]=len(vertices_uv)
                vertices_uv.append(tuple(map(float,xy)))
            face.append(uv_index[key])
        index_faces.append(tuple(face))
    inside=tuple(formed(uv) for uv in vertices_uv)
    face_normals=[]
    average_normals=[[0.,0.,0.] for _ in vertices_uv]
    skin=[]
    for a,b,c in index_faces:
        normal=_unit(_cross(
            _v3sub(inside[b],inside[a]),_v3sub(inside[c],inside[a]),
        ))
        face_normals.append(normal)
        skin.append((inside[a],inside[b],inside[c]))
        for index in (a,b,c):
            for component in range(3):
                average_normals[index][component]+=normal[component]
    # At a sharp hinge, use a single source-owned miter offset shared by
    # all incident skin faces. Offset length is exactly T (one side), never
    # +/- T/2. This gives an indexed closed shell without welding contact.
    normal_at_source=tuple(_unit(n) for n in average_normals)
    outside=tuple(
        tuple(inside[i][component]-thickness*normal_at_source[i][component]
              for component in range(3))
        for i in range(len(inside))
    )
    vertices=inside+outside
    k=len(inside)
    shell=[]
    for a,b,c in index_faces:
        shell.extend(((a,b,c),(c+k,b+k,a+k)))
    source_edges=defaultdict(list)
    for a,b,c in index_faces:
        for p,q in ((a,b),(b,c),(c,a)):
            key=(min(p,q),max(p,q))
            source_edges[key].append((p,q))
    nonmanifold=sum(len(v)>2 for v in source_edges.values())
    boundary=[row[0] for row in source_edges.values() if len(row)==1]
    missing=sum(
        Point((vertices_uv[a][0]+vertices_uv[b][0])/2.,
              (vertices_uv[a][1]+vertices_uv[b][1])/2.).distance(stock.boundary)>_EPS*3
        for a,b in boundary
    )
    if nonmanifold or missing:
        raise GeometryError("TAIL_V90_T2_FULL_SOURCE_EDGE_NOT_CONTIGUOUS")
    for a,b in boundary:
        # With source CCW, the wall winding points toward the missing
        # material. Hole boundaries therefore receive INTERNAL sidewalls.
        shell.extend(((a,b+k,b),(a,a+k,b+k)))

    edge_faces=defaultdict(list)
    for a,b,c in shell:
        for p,q in ((a,b),(b,c),(c,a)):
            edge_faces[(min(p,q),max(p,q))].append((p,q))
    bad_edges=sum(len(v)!=2 for v in edge_faces.values())
    bad_winding=sum(len(v)==2 and v[0]==v[1] for v in edge_faces.values())
    if bad_edges or bad_winding:
        raise GeometryError("TAIL_V90_T2_FULL_ROOT_T_SHELL_NOT_CLOSED")
    signed_volume=sum(
        _dot(vertices[a],_cross(vertices[b],vertices[c]))/6.
        for a,b,c in shell
    )
    if not math.isfinite(signed_volume) or signed_volume<=0.:
        raise GeometryError("TAIL_V90_T2_FULL_NONPOSITIVE_SHELL_VOLUME")

    # Actual source hole loops have their OWN closure walls (not visual
    # fake holes painted on an outer-only polygon).
    holes=tuple(LineString(ring.coords) for ring in stock.interiors)
    hole_counts=tuple(
        sum(LineString((vertices_uv[a],vertices_uv[b])).distance(hole)<=_EPS*3
            for a,b in boundary)
        for hole in holes
    )
    if any(n<4 for n in hole_counts):
        raise GeometryError("TAIL_V90_T2_FULL_HOLE_WALL_MISSING")

    bounds=tuple(
        (min(v[axis] for v in vertices),max(v[axis] for v in vertices))
        for axis in range(3)
    )
    extents=tuple(x[1]-x[0] for x in bounds)
    nominal=dict(qualified.nominal_outside_mm)
    for actual,want in (
            (extents[0],nominal["main_face_w"]),
            (extents[1],nominal["main_face_d"]),
            (extents[2],nominal["bottom"])):
        if abs(actual-want)>_EPS*10:
            raise GeometryError("TAIL_V90_T2_FULL_OUTSIDE_REAL_MESH_MISMATCH")
    # The side flange material reaches z=15; the main outside face is z=-T.
    # Use actual world vertices, not the 15-mm material len alone.
    side_end=max(
        inside[i][2] for i,xy in enumerate(vertices_uv)
        if ((abs(xy[0])<=_EPS or abs(xy[0]-522.)<=_EPS)
            and 63.-_EPS<=xy[1]<=190.+_EPS)
    )
    side_reach=side_end-bounds[2][0]
    if abs(side_reach-nominal["side_left"])>_EPS*10:
        raise GeometryError("TAIL_V90_T2_FULL_SIDE_OUTSIDE_MISMATCH")

    # Each real V wall has two oppositely oriented copies, each with its
    # own original CUTTING source IDs. Compare their ENTIRE triangle sets,
    # including the physical outer face corners, not midpoint distances.
    cut_contacts=[]
    for corner,lower,apex,upper in flat.opening_source_points_xy:
        leg_walls=[]
        for endpoint in (lower,upper):
            ideal=LineString((apex,endpoint))
            selected=[]
            for a,b in boundary:
                seg=LineString((vertices_uv[a],vertices_uv[b]))
                if seg.length<=_EPS or seg.difference(ideal.buffer(_EPS*3)).length>_EPS:
                    continue
                selected.extend((
                    (vertices[a],vertices[b+k],vertices[b]),
                    (vertices[a],vertices[a+k],vertices[b+k]),
                ))
            if not selected:
                raise GeometryError("TAIL_V90_T2_FULL_CUT_WALL_SOURCE_NOT_FOUND")
            leg_walls.append(tuple(selected))
        lower_world,upper_world=leg_walls
        def canonical(tri):
            return tuple(sorted(
                tuple(round(v/_EPS) for v in point)
                for point in tri
            ))
        if set(map(canonical,lower_world)) != set(map(canonical,upper_world)):
            raise GeometryError("TAIL_V90_T2_FULL_REAL_CUT_WALLS_NOT_COINCIDENT")
        cut_contacts.append((corner,len(lower_world),len(upper_world),0.0,True))
    return TailV90FullT2SolidCheck(
        first_axis=first_axis,
        source_material_with_holes=stock,
        source_triangles=source,
        world_inside_skin_triangles=tuple(skin),
        vertices_xyz=tuple(vertices),
        indexed_triangle_faces=tuple(shell),
        source_boundary_edge_count=len(boundary),
        source_hole_count=len(holes),
        source_hole_wall_segment_counts=hole_counts,
        source_nonmanifold_edge_count=nonmanifold,
        shell_nonmanifold_edge_count=bad_edges,
        shell_winding_error_edge_count=bad_winding,
        shell_signed_volume_mm3=float(signed_volume),
        formed_outer_bounds_xyz_mm=bounds,
        formed_outer_extents_xyz_mm=extents,
        formed_side_outside_reach_mm=float(side_reach),
        formed_bottom_outside_reach_mm=float(extents[2]),
        true_t_v_seam_contact=tuple(cut_contacts),
        actual_upper_fold_sample_xyz=formed((261.,228.)),
        nominal_outside_mm=qualified.nominal_outside_mm,
        thickness_mm=thickness,
    )
