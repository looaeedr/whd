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

from shapely.geometry import LineString, Point, Polygon

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
    forbidden_crossing_pair_count: int
    unexpected_coplanar_overlap_pair_count: int
    tested_nonadjacent_world_face_pairs: int
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
    volume_nonpenetration_status: str = "NUMERICAL_WORLD_TRUE_T_NONCONTACT_SURFACE_CROSSING_CLEAR_NOT_BOOLEAN_CERTIFICATE"
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
    from .v_miter_tail_no_ba_sequential import (
        stations_from_real_flat,exact_tail_y_fold_profile_from_original_bends,
    )

    st=stations_from_real_flat(flat)

    if (not isinstance(flat,TailIllustratedSideV90Flat)
            or first_axis not in ("x","y") or flat.manufacturing_approved):
        raise GeometryError("TAIL_V90_T2_FULL_CORRECTED_FACTORY_REQUIRED")
    qualified=project_tail_sharp_no_ba_v_witness(flat)
    thickness=float(qualified.physical_sheet_thickness_mm)
    if thickness<=0. or not math.isfinite(thickness):
        raise GeometryError("V_MITER_LOWER_PHYSICAL_T_REQUIRED")
    stock=material_polygon_from_final_scene(flat.result_scene)
    original_stock=material_polygon_from_final_scene(flat.original_scene)
    # The *authored CUTTING primitives* are hole provenance, not whichever
    # interior rings happened to be inside the OLD four-corner trimmed sheet.
    # An unchanged hole can be hidden by the old cut and become fully
    # visible in the newly restored V mother without moving a single hole.
    # Matching interior rings of two different stock polygons falsely
    # rejected this exact source despite identical original hole entities.
    original_primitives=tuple(flat.original_scene.primitives)
    formed_primitives=tuple(flat.result_scene.primitives)
    original_cutting=tuple(
        p for p in original_primitives if getattr(p,"layer",None)=="CUTTING"
    )
    restored_cutting=tuple(
        p for p in formed_primitives if getattr(p,"layer",None)=="CUTTING"
    )
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    source_outer=tuple(
        p for p in original_cutting
        if isinstance(p,PolylinePrimitive) and p.closed
        and abs(Polygon([(v.x,v.y) for v in p.points]).symmetric_difference(
            flat.original_factory_material).area)<=_EPS
    )
    final_outer=tuple(
        p for p in restored_cutting
        if isinstance(p,PolylinePrimitive) and p.closed
        and abs(Polygon([(v.x,v.y) for v in p.points]).symmetric_difference(
            flat.result_material).area)<=_EPS
    )
    if len(source_outer)!=1 or len(final_outer)!=1:
        raise GeometryError("TAIL_V90_T2_FULL_HOLES_OR_SOURCE_MISSING:OUTER_ID")
    original_hole_features=tuple(p for p in original_cutting if p is not source_outer[0])
    final_hole_features=tuple(p for p in restored_cutting if p is not final_outer[0])
    inherited=tuple(flat.inherited_non_v_cutting_features)
    if (stock.geom_type!="Polygon" or not stock.is_valid or stock.is_empty
            or original_stock.geom_type!="Polygon" or not original_stock.is_valid
            or len(final_hole_features)!=len(original_hole_features)+len(inherited)
            or any(p is not q for p,q in zip(
                original_hole_features,
                final_hole_features[:len(original_hole_features)]))
            or tuple(final_hole_features[len(original_hole_features):])!=inherited
            or stock.difference(flat.result_material).area>_EPS):
        raise GeometryError("TAIL_V90_T2_FULL_HOLES_OR_SOURCE_MISSING:RAW_CUTTING_CHANGED")
    # Every source hole in this V blank MUST be a real physical cutout in
    # the final material; merely drawing an unchanged circle in FinalScene
    # is insufficient if a geometry bug silently fills its interior.
    for hole in original_hole_features:
        if isinstance(hole,CirclePrimitive):
            cut=Point(hole.center.x,hole.center.y).buffer(
                float(hole.radius),quad_segs=32,
            )
        elif isinstance(hole,PolylinePrimitive) and hole.closed:
            cut=Polygon([(v.x,v.y) for v in hole.points])
        else:
            continue
        if (cut.is_empty or not cut.is_valid
                or (flat.result_material.intersection(cut).area>_EPS
                    and stock.intersection(cut).area>_EPS)):
            raise GeometryError("TAIL_V90_T2_FULL_HOLES_OR_SOURCE_MISSING:CUTOUT_FILLED")
    outer_only=flat.result_material
    if (not outer_only.covers(stock) or
            stock.difference(outer_only).area>_EPS or
            outer_only.difference(stock).area<=0):
        raise GeometryError("TAIL_V90_T2_FULL_NOT_SAME_FACTORY_CUTTING")
    source,area=_single_sheet_triangles(stock,st)
    if abs(area-stock.area)>max(1e-5,stock.area*1e-7):
        raise GeometryError("TAIL_V90_T2_FULL_CUTTING_AREA_LOST")

    s=flat.source_spec
    snapshot=dict(model=s.model_name,w=s.width,d=s.depth,t=s.thickness,
                  fw=s.frame_width,yl1=s.fold_left,yr1=s.fold_right,
                  ytop1=s.fold_top,ybottom1=s.fold_bottom)
    profiles=build_endcap_xy_fold_profiles(snapshot,part_key="tail")
    # The real Factory CUTTING/BEND is the precision authority, not the
    # integer display lengths in the unchanged editor Fold Profile.
    exact_y=exact_tail_y_fold_profile_from_original_bends(flat,st)
    ybreak,yfold=_profile_geometry(exact_y)
    if len(ybreak)!=5 or any(abs(ybreak[i]-q)>_EPS for i,q in enumerate(
            (st.ymin,st.bottom_y,st.upper_start,st.upper_crease,st.ymax))):
        raise GeometryError("V_MITER_LOWER_UNCHANGED_UPPER_PROFILE_NOT_MATCHED")
    u0,z0=_profile_map(st.bottom_y,ybreak,yfold)

    def formed(uv):
        x,y=map(float,uv)
        if y<=st.upper_start+_EPS:
            # The lower V owns only source-corrected material. Upper crease
            # profile remains the unmodified native Engine chain.
            return _stages((x,y),first_axis,st)[1]
        if x<st.bottom_guide_start-_EPS or x>st.bottom_guide_end+_EPS:
            raise GeometryError("V_MITER_LOWER_UPPER_MATERIAL_NOT_ON_CORE")
        uy,uz=_profile_map(y,ybreak,yfold)
        return (x,float(st.bottom_y+uy-u0),float(uz-z0))

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
    source_plane_normals=[[] for _ in vertices_uv]
    skin=[]
    for a,b,c in index_faces:
        normal=_unit(_cross(
            _v3sub(inside[b],inside[a]),_v3sub(inside[c],inside[a]),
        ))
        face_normals.append(normal)
        skin.append((inside[a],inside[b],inside[c]))
        for index in (a,b,c):
            if not any(_dot(normal,prior)>=1.-1e-9
                       for prior in source_plane_normals[index]):
                source_plane_normals[index].append(normal)
    # A T2 *sharp miter corner* is at the INTERSECTION of the unchanged
    # source face's one-sided T offsets, not at a normalized average of
    # their normals. At a perpendicular two-plane crease, move by T along
    # BOTH normals; at the 3-plane physical root, move by all THREE.
    # This uses no R, no BA and no invented CUTTING. It keeps the original
    # one-sheet UV vertex shared, while exact outside faces meet without
    # smoothed-normal outer-skin crossings at the finite-root corner.
    if any(
        abs(_dot(n,m))>1e-7 for normals in source_plane_normals
        for i,n in enumerate(normals) for m in normals[i+1:]
    ):
        raise GeometryError("TAIL_V90_T2_FULL_NONORTHOGONAL_SHARP_ROOT")
    outside=tuple(
        tuple(inside[i][component]-thickness*sum(
            normal[component] for normal in source_plane_normals[i]
        ) for component in range(3))
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
    physical_wall_faces_by_source_edge={}
    physical_wall_face_ids_by_source_edge={}
    for a,b in boundary:
        # With source CCW the wall winding points toward missing
        # material (including the ORIGINAL through-holes). Two opposite
        # V-cut wall edges have reversed source directions but COINCIDENT
        # formed endpoints. Canonicalize only the triangulation diagonal
        # of their actual physical quadrilateral, not their geometry:
        # otherwise the two nonplanar T2 quads use opposite diagonals and
        # falsely claim a surface gap/penetration despite equal vertices.
        if inside[a] <= inside[b]:
            faces=((a,b+k,b),(a,a+k,b+k))
        else:
            faces=((b,a,a+k),(b,a+k,b+k))
        face_start=len(shell)
        shell.extend(faces)
        physical_wall_faces_by_source_edge[frozenset((a,b))]=faces
        physical_wall_face_ids_by_source_edge[frozenset((a,b))]=(
            face_start,face_start+1,
        )

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
    side_reaches=[]
    for name,side_x,top_station,expected in (
        ("left",st.xmin,st.left_side_end,nominal["side_left"]),
        ("right",st.xmax,st.right_side_end,nominal["side_right"]),
    ):
        delta=(st.left_x-st.xmin) if name=="left" else (st.xmax-st.right_x)
        sides=[
            inside[i][2] for i,xy in enumerate(vertices_uv)
            if abs(xy[0]-side_x)<=_EPS
            and st.bottom_y+delta-_EPS<=xy[1]<=top_station+_EPS
        ]
        if not sides:
            raise GeometryError("V_MITER_LOWER_SIDE_FLANGE_SOURCE_MISSING:"+name)
        reach=max(sides)-bounds[2][0]
        side_reaches.append(reach)
        if abs(reach-expected)>_EPS*10:
            raise GeometryError("V_MITER_LOWER_SIDE_OUTSIDE_MISMATCH:"+name)
    side_reach=side_reaches[0]

    # Each real V wall has two oppositely oriented copies, each with its
    # own original CUTTING source IDs. Compare their ENTIRE triangle sets,
    # including the physical outer face corners, not midpoint distances.
    cut_contacts=[]
    # Only ONE of each source-proven coincident opposite-side V face is
    # excluded from the GLOBAL self-intersection diagnostic. The genuine
    # paired sidewall remains in the actual shell and in the contact proof.
    # It must not be mistaken for positive-volume self-penetration.
    duplicate_contact_faces_to_ignore=set()
    for corner,lower,apex,upper in flat.opening_source_points_xy:
        leg_walls=[]
        leg_face_ids=[]
        for endpoint in (lower,upper):
            ideal=LineString((apex,endpoint))
            selected=[]
            selected_ids=[]
            for a,b in boundary:
                seg=LineString((vertices_uv[a],vertices_uv[b]))
                if seg.length<=_EPS or seg.difference(ideal.buffer(_EPS*3)).length>_EPS:
                    continue
                source_key=frozenset((a,b))
                selected.extend(tuple(
                    tuple(vertices[vi] for vi in face)
                    for face in physical_wall_faces_by_source_edge[source_key]
                ))
                selected_ids.extend(
                    physical_wall_face_ids_by_source_edge[source_key]
                )
            if not selected:
                raise GeometryError("TAIL_V90_T2_FULL_CUT_WALL_SOURCE_NOT_FOUND")
            leg_walls.append(tuple(selected))
            leg_face_ids.append(tuple(selected_ids))
        lower_world,upper_world=leg_walls
        def canonical(tri):
            return tuple(sorted(
                tuple(round(v/_EPS) for v in point)
                for point in tri
            ))
        low_faces={canonical(tri):tri for tri in lower_world}
        high_faces={canonical(tri):tri for tri in upper_world}
        if set(low_faces)!=set(high_faces) or len(low_faces)!=len(lower_world) or len(high_faces)!=len(upper_world):
            raise GeometryError("TAIL_V90_T2_FULL_REAL_CUT_WALLS_NOT_COINCIDENT")
        # Both walls physically meet over the *same area*, yet face in
        # opposite directions. A same-direction duplicate is invalid.
        for key in low_faces:
            a,b,c=low_faces[key]
            d,e,f=high_faces[key]
            nlow=_unit(_cross(_v3sub(b,a),_v3sub(c,a)))
            nhigh=_unit(_cross(_v3sub(e,d),_v3sub(f,d)))
            if _dot(nlow,nhigh)>-1.+1e-7:
                raise GeometryError("TAIL_V90_T2_FULL_V_WALL_NORMALS_NOT_OPPOSED")
        duplicate_contact_faces_to_ignore.update(leg_face_ids[1])
        cut_contacts.append((corner,len(lower_world),len(upper_world),0.0,True))

    # WORLD self-intersection is checked AFTER separating source-proven V
    # face contact from the rest of the still-complete indexed shell.
    # All actual hole walls, both outside skins, and the true root stay in
    # the diagnostic. No old R/BA or in-plane midpoint gap is used.
    from .assembly_geometry import diagnose_world_mesh_self_intersections
    checked_world_faces=tuple(
        tuple(vertices[v] for v in face) for j,face in enumerate(shell)
        if j not in duplicate_contact_faces_to_ignore
    )
    # The common general-purpose 12,000-pair diagnostic budget was proven
    # insufficient for this four-hole full blank (it returned UNKNOWN even
    # with zero crossings). Give THIS bounded exact-source verification
    # the exhaustive finite pair capacity; do not loosen spatial tolerance.
    pair_capacity=len(checked_world_faces)*(len(checked_world_faces)-1)//2
    observed=diagnose_world_mesh_self_intersections(
        checked_world_faces,max_nonadjacent_pairs=pair_capacity,
    )
    if (observed.numerical_budget_exhausted
            or observed.crossing_pair_count
            or observed.coplanar_overlap_pair_count):
        raise GeometryError(
            "TAIL_V90_T2_FULL_ROOT_FORBIDDEN_SURFACE_INTERSECTION:"
            f" crossings={observed.crossing_pair_count}"
            f" overlap={observed.coplanar_overlap_pair_count}"
            f" exhausted={observed.numerical_budget_exhausted}"
        )
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
        forbidden_crossing_pair_count=observed.crossing_pair_count,
        unexpected_coplanar_overlap_pair_count=observed.coplanar_overlap_pair_count,
        tested_nonadjacent_world_face_pairs=observed.tested_nonadjacent_pairs,
        formed_outer_bounds_xyz_mm=bounds,
        formed_outer_extents_xyz_mm=extents,
        formed_side_outside_reach_mm=float(side_reach),
        formed_bottom_outside_reach_mm=float(extents[2]),
        true_t_v_seam_contact=tuple(cut_contacts),
        actual_upper_fold_sample_xyz=formed((
            (st.left_x+st.right_x)/2.,
            st.ymax-min(5.,(st.ymax-st.upper_crease)/2.),
        )),
        nominal_outside_mm=qualified.nominal_outside_mm,
        thickness_mm=thickness,
    )
