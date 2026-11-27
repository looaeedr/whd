# -*- coding: utf-8 -*-
"""Explicit first-type assembly using the existing Fold, scene and Joint owners."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite

from ..contracts import WirePullBoxSpec, FoldProfileSegment
from ..assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource, ResolvedAssemblyGraph
from ..assembly_geometry import folded_mesh_with_flat_uv_from_polygon, diagnose_world_mesh_triangle_edge_incidence
from ..assembly_geometry_folded_mesh import _profile_geometry
from ..assembly_geometry_primitives import (
    place_assembly_triangles, thicken_orthogonal_inside_surface, triangle_bounds,
)
from ..box_body_fold_profile import apply_outside_dimension_compensation, outside_profile_to_material
from ..sheetmetal_geometry import Vec2, FoldSegment, StripFoldChain, build_strip_outline, build_strip_bend_segments
from ..sheetmetal_part_adapters import StructuralGeometryResult
from ..sheetmetal_drawing import DrawingScene, structural_result_to_primitives
from ..manufacturing_render_data import (
    PartRenderData, MaterialSegment, UnfoldedBlankTopology,
    material_polygon_from_final_scene, fold_guides_from_final_scene,
)

GAP_MM = 1.0  # confirmed first-type exterior lid in-plane gap, independent of T
PART_KEYS = ("box_body", "head", "tail", "lid")
BODY_FACES = ("front_left_return", "left", "rear", "right", "front_right_return")
NORMALS = ((0,0,1), (-1,0,0), (0,0,-1), (1,0,0), (0,0,1))
TOL = 1e-6


@dataclass(frozen=True)
class MountFace:
    """Physical face and affine unfolded material coordinates for later features.

    origin is the actual outside skin at (u_min,v_min). Directions are world
    unit vectors for increasing flat material U/V, not renderer orientation.
    The fold band itself is not approved hole material by this topology.
    """
    part_key: str
    face_id: str
    flat_bounds: tuple[float, float, float, float]
    world_origin: tuple[float, float, float]
    u_direction: tuple[float, float, float]
    v_direction: tuple[float, float, float]
    outward_normal: tuple[int, int, int]


@dataclass(frozen=True)
class PhysicalPart:
    part_key: str
    render_data: PartRenderData
    x_profile: tuple[FoldProfileSegment, ...]
    y_profile: tuple[FoldProfileSegment, ...]
    world_triangles: tuple
    mounting_faces: tuple[MountFace, ...]


@dataclass(frozen=True)
class StandardTopology:
    parts: tuple[PhysicalPart, ...]
    joint_graph: ResolvedAssemblyGraph
    outside_bounds: tuple
    manufacturing_verified: bool = False

    @property
    def joints(self):
        return self.joint_graph.joints

    def part(self, key):
        for part in self.parts:
            if part.part_key == key:
                return part
        raise KeyError(key)


def _number(value, field, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("WIRE_PULL_SOURCE_REQUIRED: " + field)
    try:
        result = float(value)
    except (ValueError, OverflowError, TypeError) as exc:
        raise ValueError("WIRE_PULL_INVALID_DIMENSION: " + field) from exc
    if not isfinite(result) or result < 0 or (not allow_zero and result <= TOL):
        raise ValueError("WIRE_PULL_INVALID_DIMENSION: " + field)
    return result


def _render(key, x_profile, height):
    """Use the same canonical structural CUTTING/BEND and material parser."""
    rows = tuple(x_profile)
    width = sum(row.length for row in rows)
    if len(rows) == 1:
        outline = tuple(Vec2(x,y) for x,y in ((0,0),(width,0),(width,height),(0,height),(0,0)))
        structural = StructuralGeometryResult(outline, (), width, height)
    else:
        chain = StripFoldChain(tuple(FoldSegment(row.phase6_key, row.length) for row in rows), height)
        structural = StructuralGeometryResult(
            tuple(build_strip_outline(chain)), tuple(build_strip_bend_segments(chain)),
            width, height, chain,
        )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural, outline_semantic_id="OUTER_BOUNDARY"))
    data = PartRenderData(
        scene=scene, material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        unfolded_topology=UnfoldedBlankTopology(
            key,
            tuple(MaterialSegment("X", row.phase6_key, row.length, "WIRE_PULL_EXPLICIT_TOPOLOGY") for row in rows),
            (MaterialSegment("Y", "span", height, "WIRE_PULL_EXPLICIT_TOPOLOGY"),),
            "WIRE_PULL_EXPLICIT_TOPOLOGY",
        ),
        metadata={"stable_id": key, "standard_cabinet_family": "拉線箱",
                  "formed_geometry_verified": False},
    )
    return data


def _mapped(data, x, y, *, exact_material=False):
    return folded_mesh_with_flat_uv_from_polygon(
        data.material, x, y, fold_guides=data.fold_guides,
        exact_material=exact_material,
    )


def _render_with_features(key, x, y, height, transform):
    source = _render(key, x, height)
    if transform is None:
        return source, False
    data = transform(key, source)
    if (data.fold_guides != source.fold_guides
            or data.unfolded_topology != source.unfolded_topology
            or data.metadata.get("stable_id") != key
            or data.metadata.get("formed_geometry_verified") is not False
            or not data.material.equals(material_polygon_from_final_scene(data.scene))):
        raise ValueError("WIRE_PULL_HOLE_RENDER_SOURCE_CHANGED")
    if data.material.equals(source.material):
        return data, False
    # P1 holes are fully interior to one real planar material cell. Never
    # fill, split or cut a hinge to rescue a feature that crosses a fold.
    from shapely.geometry import box
    if (data.material.geom_type != "Polygon" or not data.material.is_valid
            or not source.material.covers(data.material)
            or not data.material.exterior.equals(source.material.exterior)):
        raise ValueError("WIRE_PULL_HOLE_OUTER_MATERIAL_CHANGED")
    xb, _ = _profile_geometry(x)
    yb, _ = _profile_geometry(y)
    cells = tuple(box(a,c,b,d) for a,b in zip(xb,xb[1:]) for c,d in zip(yb,yb[1:]))
    cut = source.material.difference(data.material)
    components = (cut,) if cut.geom_type == "Polygon" else tuple(cut.geoms)
    for hole in components:
        if not any(cell.contains(hole) and not cell.boundary.intersects(hole) for cell in cells):
            raise ValueError("WIRE_PULL_HOLE_CROSSES_FOLD_OR_EDGE")
    return data, True


def _shift(mesh, dx=0., dy=0., dz=0.):
    return tuple(tuple((p[0]+dx, p[1]+dy, p[2]+dz) for p in tri) for tri in mesh)


def _require_closed(mesh):
    if not diagnose_world_mesh_triangle_edge_incidence(mesh).edges_manifold_closed:
        raise ValueError("WIRE_PULL_PHYSICAL_SHELL_OPEN")


def _flat(key, width, height, t, dims, placement, *, outer_plane, z_center=0., render_transform=None):
    width, height = _number(width, key+"_width"), _number(height, key+"_height")
    x = (FoldProfileSegment(width, phase6_key="flat"),)
    y = (FoldProfileSegment(height, phase6_key="span"),)
    data, exact = _render_with_features(key, x, y, height, render_transform)
    mapped = _mapped(data, x, y, exact_material=exact)
    mesh = thicken_orthogonal_inside_surface(
        tuple(m.local for m in mapped), ((0,0,1),)*len(mapped), t,
    )
    mesh = place_assembly_triangles(mesh, placement, dims)
    # The shared top placement swaps Y/Z (determinant -1). Its points
    # and UV orientation are correct; restore the outward triangle winding
    # of the closed solid after the reflection. Bottom/front preserve it.
    if placement == "top":
        mesh = tuple((a,c,b) for a,b,c in mesh)
    axis, sign = (2,1) if placement == "front" else (1,1 if placement == "top" else -1)
    bounds = triangle_bounds(mesh)
    delta = outer_plane - bounds[axis][1 if sign > 0 else 0]
    mesh = _shift(mesh, dy=delta if axis == 1 else 0.,
                  dz=delta if axis == 2 else z_center)
    _require_closed(mesh)
    b = triangle_bounds(mesh)
    if placement == "front":
        origin = (b[0][0],b[1][0],b[2][1])
        v, n = (0,1,0),(0,0,1)
    else:
        origin = (b[0][0],b[1][1 if sign>0 else 0],b[2][0])
        v, n = (0,0,1),(0,sign,0)
    face = MountFace(key, "outer", (0.,0.,width,height), origin, (1,0,0), v, n)
    return PhysicalPart(key,data,x,y,mesh,(face,))


def _body(dims, t, left, right, lid, *, render_transform=None):
    w,h,d = dims
    # Joint OVERLAY: the actual lid inner skin, not a planar gap or borrowed
    # Family D compensation, is the body front outside contact plane.
    lid_bounds = triangle_bounds(lid.world_triangles)
    rear_outer = -d/2
    front_outer = lid_bounds[2][0]
    body_depth = _number(front_outer-rear_outer, "body_outside_depth")
    rows = [
        {"len":left,"phase6_key":BODY_FACES[0],"angle":-90.},
        {"len":body_depth,"phase6_key":BODY_FACES[1],"core":"D","angle":-90.},
        {"len":w,"phase6_key":BODY_FACES[2],"core":"W","angle":-90.},
        {"len":body_depth,"phase6_key":BODY_FACES[3],"core":"D","angle":-90.},
        {"len":right,"phase6_key":BODY_FACES[4]},
    ]
    # Explicit terminal return lengths are MATERIAL. Only the operator
    # outside core spans are converted. Use the same topology-owned count
    # to express the terminal material as outside before conversion.
    rows = apply_outside_dimension_compensation(rows,t)
    for i in (0,4):
        rows[i]["len"] += rows[i].get("ui_len_add",0.)
    rows = outside_profile_to_material(rows,t)
    x = tuple(FoldProfileSegment(
        _number(row["len"],row["phase6_key"]), row.get("angle"),
        row.get("core"), row["phase6_key"],
    ) for row in rows)
    if left+right >= x[2].length-TOL:
        raise ValueError("WIRE_PULL_OPENING_BLOCKED_BY_RETURNS")
    y = (FoldProfileSegment(h,phase6_key="height"),)
    data, exact = _render_with_features("box_body",x,y,h,render_transform)
    boundaries, folded = _profile_geometry(x)
    mapped = _mapped(data,x,y,exact_material=exact)
    face_indexes = tuple(bisect_right(boundaries,sum(p[0] for p in m.flat)/3.)-1 for m in mapped)
    mesh = thicken_orthogonal_inside_surface(
        tuple(m.local for m in mapped), tuple(NORMALS[i] for i in face_indexes), t,
    )
    dz = rear_outer-triangle_bounds(mesh)[2][0]
    mesh = _shift(mesh,dz=dz)
    _require_closed(mesh)
    b = triangle_bounds(mesh)
    if any(abs(a-e)>TOL for a,e in zip(
        (b[0][0],b[0][1],b[1][0],b[1][1],b[2][0],b[2][1]),
        (-w/2,w/2,-h/2,h/2,rear_outer,front_outer),
    )):
        raise ValueError("WIRE_PULL_BODY_OUTSIDE_MISMATCH")

    faces = []
    for i,(key,n) in enumerate(zip(BODY_FACES,NORMALS)):
        a,c = folded[i],folded[i+1]
        origin = (a[0]+t*n[0],-h/2,a[1]+dz+t*n[2])
        direction = ((c[0]-a[0])/x[i].length,0.,(c[1]-a[1])/x[i].length)
        faces.append(MountFace("box_body",key,(boundaries[i],0.,boundaries[i+1],h),
                               origin,direction,(0,1,0),n))
    # Both actual planar return faces must support the lid over a nonzero
    # interval of unbent material; do not count their miter extension.
    for face in (faces[0],faces[-1]):
        x0 = face.world_origin[0]
        x1 = x0+face.u_direction[0]*(face.flat_bounds[2]-face.flat_bounds[0])
        overlap = min(max(x0,x1),lid_bounds[0][1])-max(min(x0,x1),lid_bounds[0][0])
        if overlap <= TOL or abs(face.world_origin[2]-front_outer)>TOL:
            raise ValueError("WIRE_PULL_LID_SUPPORT_MISSING: "+face.face_id)
    # These four coordinates are the actual folded inside-skin planes, not
    # generic nominal W/D deductions. INSERT caps must fit between them.
    inside = (folded[2][0],folded[3][0],folded[2][1]+dz,folded[1][1]+dz)
    return PhysicalPart("box_body",data,x,y,mesh,tuple(faces)),inside


def resolve(spec, *, render_transform=None):
    if not isinstance(spec,WirePullBoxSpec):
        raise TypeError("WIRE_PULL_EXPLICIT_SPEC_REQUIRED")
    w,h,d,t = tuple(_number(getattr(spec,name),name) for name in
                    ("width","height","depth","thickness"))
    left = _number(spec.left_return_material_mm,"left_return_material_mm")
    right = _number(spec.right_return_material_mm,"right_return_material_mm")
    # No authority for a default head/tail fold. This
    # first geometry candidate supports explicitly selected flat INSERT
    # plates only; folded sources must never silently take that path.
    for key in ("head","tail"):
        form = getattr(spec,key+"_form")
        if form != "flat":
            raise ValueError("WIRE_PULL_ENDCAP_FORM_REQUIRED_OR_UNSUPPORTED: "+key)
    hc = _number(spec.head_clearance_mm,"head_clearance_mm",allow_zero=True)
    tc = _number(spec.tail_clearance_mm,"tail_clearance_mm",allow_zero=True)
    dims = (w,h,d)
    lid = _flat("lid",w-2*GAP_MM,h-2*GAP_MM,t,dims,"front",outer_plane=d/2,
                render_transform=render_transform)
    body, (xmin,xmax,zmin,zmax) = _body(dims,t,left,right,lid,render_transform=render_transform)
    caps = []
    for key,placement,plane,clearance in (
        ("head","top",h/2,hc),("tail","bottom",-h/2,tc),
    ):
        caps.append(_flat(key,xmax-xmin-2*clearance,zmax-zmin-2*clearance,
                          t,dims,placement,outer_plane=plane,z_center=(zmin+zmax)/2,
                          render_transform=render_transform))
    head,tail = caps
    if triangle_bounds(head.world_triangles)[1][0] <= triangle_bounds(tail.world_triangles)[1][1]+TOL:
        raise ValueError("WIRE_PULL_ENDCAPS_OVERLAP")
    joints = [
        AssemblyJoint(key+":insert",key,"box_body","perimeter","inside_"+key,
                      AssemblyJointRelation.INSERT, source=AssemblyJointSource.FAMILY_GEOMETRY,
                      direction=direction,
                      clearance_policy="EXPLICIT_INSERT_PERIMETER" if clearance else "ZERO",
                      clearance_intent="EXPLICIT_INSERT_PERIMETER" if clearance else "ZERO",
                      solver_constraints={"insert_perimeter_clearance_mm": clearance} if clearance else {})
        for key,direction,clearance in (("head","+Y",hc),("tail","-Y",tc))
    ]
    joints.extend(AssemblyJoint("lid:"+face,"lid","box_body","inner",face,
                                AssemblyJointRelation.OVERLAY,
                                source=AssemblyJointSource.FAMILY_GEOMETRY,direction="+Z")
                  for face in (BODY_FACES[0],BODY_FACES[-1]))
    parts = (body,head,tail,lid)
    bounds = triangle_bounds(tuple(tri for part in parts for tri in part.world_triangles))
    if any(abs((hi-lo)-expected)>TOL for (lo,hi),expected in zip(bounds,dims)):
        raise ValueError("WIRE_PULL_ASSEMBLED_OUTSIDE_MISMATCH")
    return StandardTopology(parts,ResolvedAssemblyGraph(PART_KEYS,tuple(joints)),bounds)
