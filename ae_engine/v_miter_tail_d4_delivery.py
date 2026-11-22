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
