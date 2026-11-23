# -*- coding: utf-8 -*-
"""#3317 independent Ø4 CHECK delivery from TRUE Factory/project source.

Never import or invoke tests. No invented authored hole. The caller passes a
live PartRenderData from the current project, or explicitly requests an
unmodified Factory-default sample. This is NOT a production manufacturing
request, formal DXF exporter, or release of R2.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .contracts import EndCapPartSpec
from .manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene,
    fold_guides_from_final_scene,
)
from .sheetmetal_drawing import DrawingScene, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_tail_user_image_source import project_tail_illustrated_side_v90_flat
from .v_miter_tail_d4_check import project_tail_d4_source_keyed_t_check
from .v_miter_tail_d4_check_dxf import save_tail_d4_check_dxf

_NOT_CNC="D4_CHECK_NOT_CNC"


def default_vault_tail_d4_spec():
    """Explicit non-project Factory example; NOT an actual saved workpiece."""
    return EndCapPartSpec(
        width=620,depth=185,thickness=2,frame_width=25,height=600,
        model_name="金庫型",is_tail=True,
        fold_left=15,fold_right=15,fold_top=16,fold_bottom=48,
        box_fold_left=15,box_fold_right=15,
    )


def _original_factory_source(spec):
    from .ae_endcap import _build_end_cap_scene
    scene=_build_end_cap_scene(
        w=spec.width,d=spec.depth,t=spec.thickness,fw=spec.frame_width,
        yl1=spec.fold_left,yr1=spec.fold_right,
        ytop1=spec.fold_top,ybottom1=spec.fold_bottom,
        is_tail=bool(spec.is_tail),model_name=spec.model_name,
    )
    return PartRenderData(
        scene=scene,material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={"source":"WHD_UNMODIFIED_FACTORY_NO_TEST_FEATURES"},
    )


def build_tail_d4_check_from_original(
    spec, *, original_render_data=None, resolved_render_data=None,
):
    """Take the same authoritative source as native V, never test fixtures.

    resolved_render_data is optional only for an explicitly unmodified
    Factory example. A real project must provide the actual original
    PartRenderData (and resolved one whenever an independent overlay exists).
    """
    if not isinstance(spec,EndCapPartSpec) or not spec.is_tail:
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_TAIL_SPEC_REQUIRED")
    if original_render_data is None:
        if resolved_render_data is not None:
            raise GeometryError("TAIL_D4_CHECK_DELIVERY_RESOLVED_NEEDS_ORIGINAL")
        base=_original_factory_source(spec)
    elif isinstance(original_render_data,PartRenderData):
        base=original_render_data
    else:
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_ORIGINAL_RENDER_REQUIRED")

    flat=project_tail_illustrated_side_v90_flat(spec,base)
    if resolved_render_data is not None:
        if not isinstance(resolved_render_data,PartRenderData):
            raise GeometryError("TAIL_D4_CHECK_DELIVERY_RESOLVED_RENDER_INVALID")
        from .v_miter_tail_relief_replay import (
            replay_independent_lower_v_relief, _extra_features,
            _outer, _stock, _cutting_except,
        )
        raw_stock=_stock(base,"SOURCE")
        resolved_stock=_stock(resolved_render_data,"RESOLVED")
        original_outer=_outer(base.scene,raw_stock,role="SOURCE")
        resolved_outer=_outer(
            resolved_render_data.scene,resolved_stock,role="RESOLVED",
        )
        extra_cutting,extra_marks=_extra_features(
            base,resolved_render_data,
            structural_outer=original_outer,solved_outer=resolved_outer,
        )
        original_features=_cutting_except(base.scene,original_outer)
        # Some canonical resolver snapshots repeat a Factory FIXED CUTTING
        # primitive twice (same exact dataclass/source identity) even when
        # both underlying stocks are geometrically IDENTICAL. That is not
        # another through-hole. Keep the original single authored primitive,
        # but ONLY when EVERY redundant resolved entry equals an original,
        # there are NO new markings, and the physical material is unchanged.
        # Any real new cut, moved hole or marking goes through strict replay.
        redundant_exact_source=(
            raw_stock.symmetric_difference(resolved_stock).area<=1e-7
            and not extra_marks
            and all(p in original_features for p in extra_cutting)
        )
        if not redundant_exact_source:
            flat,_=replay_independent_lower_v_relief(
                flat,original_render=base,
                resolved_render=resolved_render_data,
            )
    items=tuple(flat.result_scene.primitives)
    outer=tuple(p for p in items if isinstance(p,PolylinePrimitive)
                and p.layer=="CUTTING" and p.closed
                and p.semantic_id=="OUTER_BOUNDARY")
    if len(outer)!=1:
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_OUTER_NOT_UNIQUE")
    # The ONLY allowed change to this source exterior is the two actual
    # physical-root wedges plus the Ø4 holes. Independent features and
    # finite BEND from the supplied render source are left untouched.
    removed=tuple(
        Polygon((lower,apex,upper)).union(
            Point(*apex).buffer(2.,resolution=48),
        )
        for name,lower,apex,upper in flat.opening_source_points_xy
    )
    candidate=flat.original_factory_restored_mother.difference(
        unary_union(removed)
    )
    if candidate.geom_type!="Polygon" or not candidate.is_valid:
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_SOURCE_MATERIAL_INVALID")
    perimeter=PolylinePrimitive(
        points=tuple(Vec2(float(x),float(y))
                     for x,y in candidate.exterior.coords[:-1]),
        layer="CUTTING",closed=True,semantic_id="OUTER_BOUNDARY",
    )
    scene=DrawingScene(tuple(perimeter if p is outer[0] else p for p in items))
    revised=replace(flat,result_scene=scene,result_material=candidate)
    # Verify the entire source-keyed 3D shell for both operator orders
    # using the same physical FinalScene as the 2D CHECK.
    checked={axis:project_tail_d4_source_keyed_t_check(
        revised,first_axis=axis,
    ) for axis in ("x","y")}
    if any(c.manufacturing_approved or c.bad_incidence_edges
           or c.bad_winding_edges for c in checked.values()):
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_T2_SOURCE_NOT_CLOSED")
    return revised,checked


def deliver_tail_d4_check_only(
    folder, *, spec=None, original_render_data=None, resolved_render_data=None,
):
    """Write two independently guarded CHECK files and 2D/3D proof sources.

    The two fold orders share one flat drawing, not two different CUTTINGs.
    Output folder must already exist. No formal export layers or machining.
    """
    part=spec if spec is not None else default_vault_tail_d4_spec()
    flat,checks=build_tail_d4_check_from_original(
        part,original_render_data=original_render_data,
        resolved_render_data=resolved_render_data,
    )
    folder=Path(folder)
    if not folder.is_dir():
        raise GeometryError("TAIL_D4_CHECK_DELIVERY_DIRECTORY_MISSING")
    files=[]
    for axis in ("x","y"):
        path=folder/f"vault_tail_W{part.width:g}_D{part.depth:g}_T{part.thickness:g}_D4_{axis}_{_NOT_CNC}.dxf"
        files.append(save_tail_d4_check_dxf(flat,path,first_axis=axis))
    return tuple(files),flat,checks



def _d4_ordered_corner_motion(source_uv, source_faces, stations, first_axis):
    """Actual first/second lower-V rotations of the SAME source UV faces.

    This is a source-local kinematic witness, NOT a second physical skin or
    a replacement for the original Factory world assembly. It detects a
    candidate which simply superposes independent X and Y Fold maps and
    calls their identical results different operator orders.
    """
    from .v_miter_tail_no_ba_sequential import _stages
    from .v_miter_tail_full_t_no_ba import _cross,_dot,_unit,_v3sub

    observed=[]
    for face_id,face in enumerate(source_faces):
        uv=tuple(source_uv[i] for i in face)
        if max(q[1] for q in uv)>stations.upper_start+1e-7:
            continue
        cx=sum(q[0] for q in uv)/3.
        cy=sum(q[1] for q in uv)/3.
        if cy>stations.bottom_y+20.:
            continue
        near_left=cx<=stations.bottom_guide_start+20.
        near_right=cx>=stations.bottom_guide_end-20.
        if not near_left and not near_right:
            continue
        stages=tuple(_stages(q,first_axis,stations) for q in uv)
        first=tuple(v[0] for v in stages)
        final=tuple(v[1] for v in stages)
        def face_normal(face):
            n=_cross(_v3sub(face[1],face[0]),
                     _v3sub(face[2],face[0]))
            return _unit(n) if _dot(n,n)>1e-14 else None
        n1=face_normal(first)
        n2=face_normal(final)
        # A real source triangle must not flatten at either sequential
        # stage. Do not repair a collapse by inventing a connecting face.
        if n1 is None or n2 is None:
            raise GeometryError(
                "TAIL_D4_ORDERED_CONNECTED_FACE_COLLAPSED:"
                f"face={face_id}:uv={uv}:order={first_axis}"
            )
        centroid=(cx,cy)
        _,_,normal1,normal2,carried=_stages(
            centroid,first_axis,stations,
        )
        observed.append({
            "source_face_id":face_id,
            "corner":"left" if near_left else "right",
            "source_uv":uv,
            "first_xyz":first,
            "second_xyz":final,
            "first_face_normal":n1,
            "second_face_normal":n2,
            "source_normal_first":normal1,
            "source_normal_second":normal2,
            "transported_second_axis":carried,
        })
    if not any(r["corner"]=="left" for r in observed) or not any(
        r["corner"]=="right" for r in observed
    ):
        raise GeometryError("TAIL_D4_ORDERED_CORNER_UV_SOURCE_MISSING")
    return tuple(observed)



def project_tail_d4_shared_original_fold_candidate(
    flat, *, first_axis, box_body_world,
):
    """Isolated development candidate: original EndCap owner, V CUTTING only.

    No alternate global XYZ/skin/datum solver. This exact FinalScene retains
    its original BEND, four Factory holes, and authenticated Ø4 boundary.
    The original EndCap Fold and assembly own the non-V material datum.
    At the lower true V, the actual same-source UV triangles carry the
    first fold, transported second fold and original T/2 panel skins.
    Neither stage is a label-only substitution or a manufacturing approval.
    This API is read-only CHECK, never a machining-authorized fallback.
    """
    from .assembly_geometry_folded_mesh import folded_mesh_from_polygon
    from .receiving_settings_assembly_mesh import (
        resolve_assembled_endcap_world_skins,
    )
    from .manufacturing_render_data import (
        fold_guides_from_final_scene,material_polygon_from_final_scene,
    )
    from .v_miter_tail_no_ba_sequential import (
        stations_from_real_flat,exact_tail_y_fold_profile_from_original_bends,
    )
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .v_miter_tail_d4_check import (
        _require_authored_cutting_source,
        _require_exact_d4_outer_from_trusted_sharp,
    )
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_D4_SHARED_FACTORY_FOLD_ORDER_REQUIRED")
    st=stations_from_real_flat(flat)
    source=material_polygon_from_final_scene(flat.result_scene)
    _require_authored_cutting_source(flat,source)
    _require_exact_d4_outer_from_trusted_sharp(flat,source)
    spec=flat.source_spec
    snapshot=dict(
        model=spec.model_name,w=spec.width,d=spec.depth,
        t=spec.thickness,fw=spec.frame_width,
        yl1=spec.fold_left,yr1=spec.fold_right,
        ytop1=spec.fold_top,ybottom1=spec.fold_bottom,
    )
    owned=build_endcap_xy_fold_profiles(snapshot,part_key="tail")
    exact_y=exact_tail_y_fold_profile_from_original_bends(flat,st)
    original_bends=fold_guides_from_final_scene(flat.original_scene)
    candidate_bends=fold_guides_from_final_scene(flat.result_scene)
    # The V CHECK may show extended X side endpoint PROJECTIONS, but
    # these are not a new source-authored manufacturing BEND. The true
    # original Factory finite X guide is the folding authority. The real
    # Y bottom/upper guides must still match exactly; all authorized
    # V-side source extensions are already verified by stations_from_real_flat.
    original_y=tuple(g for g in original_bends if g.axis=="y")
    candidate_y=tuple(g for g in candidate_bends if g.axis=="y")
    if original_y!=candidate_y:
        raise GeometryError("TAIL_D4_SHARED_FACTORY_Y_BEND_CHANGED")
    if len(tuple(g for g in original_bends if g.axis=="x"))!=2:
        raise GeometryError("TAIL_D4_SHARED_FACTORY_SOURCE_SIDE_BEND_MISSING")
    # No second candidate fold or skin. The final V source UV triangles
    # are built once by project_d4_original_owner_uv_solid below.
    baseline_surface=folded_mesh_from_polygon(
        material_polygon_from_final_scene(flat.original_scene),
        owned["X"],exact_y,fold_guides=original_bends,
    )
    if not baseline_surface:
        raise GeometryError("TAIL_D4_SHARED_FACTORY_BASELINE_MISSING")
    baseline=resolve_assembled_endcap_world_skins(
        baseline_surface,placement="bottom",
        box_body_world=box_body_world,thickness=spec.thickness,
        preserve_core_origin=False,
    )
    if not baseline.solid_triangles:
        raise GeometryError("TAIL_D4_SHARED_FACTORY_PHYSICAL_T_MISSING")
    from .v_miter_tail_d4_shared_uv_solid import (
        project_d4_original_owner_uv_solid,_edge_counts,
    )
    original_open_record=_edge_counts(baseline.solid_triangles)
    original_open_edges=original_open_record[0]
    developed=project_d4_original_owner_uv_solid(
        flat,source,st,first_axis,owned["X"],exact_y,
        original_bends,baseline_surface,box_body_world,spec.thickness,
    )
    ordered_corner_motion=_d4_ordered_corner_motion(
        developed["source_uv"],developed["source_faces"],st,first_axis,
    )
    walls=developed["straight_v_wall_sets"]
    original_open_keys=original_open_record[4]
    candidate_open_keys=developed["open_world_edge_keys"]
    shared_open_keys=original_open_keys & candidate_open_keys
    new_v_open_keys=candidate_open_keys - original_open_keys
    original_removed_open_keys=original_open_keys - candidate_open_keys
    new_open_uv=tuple((
        tuple(developed["source_uv"][i] for i in uv_pair)
    ) for world_edge,uv_pair in developed["open_world_edge_uv"]
        if world_edge in new_v_open_keys and uv_pair is not None)
    if len(new_open_uv)!=len(new_v_open_keys):
        raise GeometryError("TAIL_D4_SHARED_UV_OPEN_EDGE_PROVENANCE_LOST")
    return {
        "first_axis":first_axis,
        "original_surface":baseline.formed_surface,
        "original_solid":baseline.solid_triangles,
        "v_surface":developed["v_surface"],
        "v_solid":developed["v_solid"],
        "v_solid_source_ids":developed["v_solid_source_ids"],
        "v_source_uv":developed["source_uv"],
        "v_source_faces":developed["source_faces"],
        "v_world_open_edges":developed["open_world_edges"],
        "original_world_open_edges":original_open_edges,
        # A change in CUTTING can REMOVE some original open edges while
        # creating new ones. Subtracting counts (56-40) loses identity.
        "v_extra_world_open_edges":len(new_v_open_keys),
        "v_extra_world_open_edge_uv":new_open_uv,
        "shared_original_world_open_edges":len(shared_open_keys),
        "original_removed_world_open_edges":len(original_removed_open_keys),
        "v_world_four_edges":developed["four_world_edges"],
        "v_world_multi_edges":developed["multi_world_edges"],
        "v_world_open_seam_edges":developed["open_seam_world_edges"],
        "v_seam_uv_positions":developed["seam_uv_positions"],
        "original_material":material_polygon_from_final_scene(
            flat.original_scene,
        ),
        "v_material":source,
        "straight_v_wall_sets":walls,
        "ordered_corner_motion":ordered_corner_motion,
        "manufacturing_approved":False,
        "status":"D4_SHARED_ORIGINAL_FOLD_CANDIDATE_UNVERIFIED",
    }


def build_tail_d4_check_preview_render(flat, *, first_axis):
    """Read-only 2D/3D PartRenderData for the existing native Tail V renderer.

    This preview's 2D source and all 3D T-solid triangles come from the
    SAME verified FinalScene and UV identity. It is explicitly NOT the
    ordinary V90 production preview request, and never touches a normal
    output gate, PartSpec or stored project selection.
    """
    if first_axis not in ("x","y"):
        raise GeometryError("TAIL_D4_CHECK_PREVIEW_OPERATOR_AXIS_REQUIRED")
    check=project_tail_d4_source_keyed_t_check(flat,first_axis=first_axis)
    if check.manufacturing_approved or check.bad_incidence_edges or check.bad_winding_edges:
        raise GeometryError("TAIL_D4_CHECK_PREVIEW_UNVERIFIED_SHELL")
    vertices=check.inner_xyz+check.outer_xyz
    shell=tuple(tuple(vertices[i] for i in face) for face in check.shell_faces)
    source=material_polygon_from_final_scene(flat.result_scene)
    if not shell or len(source.interiors)!=check.source_hole_count:
        raise GeometryError("TAIL_D4_CHECK_PREVIEW_SOURCE_MISMATCH")
    return PartRenderData(
        scene=flat.result_scene,
        material=source,
        fold_guides=fold_guides_from_final_scene(flat.result_scene),
        metadata={
            "source":"WHD_AUTHORITATIVE_FACTORY_OR_PROJECT_D4_CHECK",
            "tail_lower_v_choice":"v90",
            "tail_lower_v_preview_only":True,
            "tail_lower_v_d4_check_only":True,
            "tail_lower_v_no_ba":True,
            "tail_lower_v_operator_first_axis":first_axis,
            "tail_lower_v_full_t_mesh":shell,
            "tail_lower_v_physical_t":float(flat.source_spec.thickness),
            "manufacturing_approved":False,
            "tail_lower_v_d4_status":"D4_CHECK_NOT_CNC_R2_MODEL_UNRESOLVED",
        },
    )
