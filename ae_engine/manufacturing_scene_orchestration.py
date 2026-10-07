# -*- coding: utf-8 -*-
"""Headless manufacturing boundary for the existing AE engine.

This module is the stable public boundary inside the ``ae_engine`` package.
External callers use finished-face Features; compatibility with legacy
unfolded exporter coordinates is contained here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal, Mapping

from . import ae
from .dxf_serialization import save_scene_dxf
from . import manufacturing_verification as _manufacturing_verification
from . import manufacturing_export as _manufacturing_export
from . import manufacturing_requests as _manufacturing_requests
from . import manufacturing_render as _manufacturing_render
from .contracts import (
    FinalMaterialCollisionPart,
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    FeatureLike,
    FoldProfileSegment,
    IndicatorBoxPartSpec,
    ManufacturingContext,
    ManufacturingPolicy,
    PartExportResult,
    PartSpec,
)
from .sheetmetal_features import (
    BoxBodyFaceContext,
    CircleFeature,
    DoorIndicatorContext,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
    box_body_face_contexts_from_strip,
    feature_finished_point,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_door_indicator_layout,
)
from .sheetmetal_geometry import (
    EndCapAssemblySemantics,
    FourCornerTypePolicy,
    Vec2,
    resolve_endcap_policy_assembly_semantics,
)
from .sheetmetal_part_adapters import (
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_unknown_door_result,
    build_finished_reference_guide,
)
from .cabinet_types import policy as cabinet_family_policy



from .manufacturing_baseline_policy import (
    resolve_policy,
    _resource_root,
    _expected_baseline_path,
    _indicator_shared_expected_path,
    _indicator_shared_existing_path,
    expected_baseline_path_for,
    _baseline_path,
    _extract_endcap_shared_6p4_mother_rule,
    _divider_post_relief_center_frame,
    apply_divider_endcap_shared_6p4_datum,
    _door_baseline_model_name,
    _endcap_baseline_feature_model_name,
    _door_nameplate_datum_top,
    _scoped_ae_resource_root,
    _supported_kwargs,
    _call,
    _has_named_parameter,
)

from .manufacturing_door_indicator import (
    _resolved_door_params,
    _resolved_door_corner_policy,
    door_finished_face_size,
    door_indicator_offset_for_finished_center,
    indicator_box_unfolded_size,
    indicator_box_finished_face_size,
    indicator_box_opening_size,
    indicator_small_door_finished_size,
    indicator_box_opening_feature,
    validate_door_indicator_fit,
    _validate_door_part_indicator_fit,
    indicator_small_door_spec,
    indicator_small_door_unfolded_size,
)

from .manufacturing_endcap_compat import (
    _as_feature,
    _door_features_for_legacy_engine,
    _endcap_feature_kwargs,
    _legacy_endcap_holes,
    _endcap_scalar,
    resolve_endcap_request,
    _baseline_endcap_holes_for_request,
    _merge_baseline_endcap_holes,
    _scene_with_authoritative_fold_profiles,
)

def build_part_scene(
    spec: PartSpec, context: ManufacturingContext | None = None, *,
    _box_body_structural_result=None,
):
    """Return the authoritative pre-serialization DrawingScene for one part.

    This is the rendering boundary shared by non-DXF consumers (notably Phase6
    3D).  All manufacturing semantics stay in AE/PartSpec; callers must not
    rebuild baseline geometry, CornerType, holes, or operation ownership.
    """
    ctx = context or ManufacturingContext()
    with _scoped_ae_resource_root(ctx):
        if isinstance(spec, DoorPartSpec):
            _validate_door_part_indicator_fit(spec, ctx)
            p = _resolved_door_params(spec, ctx)
            corner_policy = _resolved_door_corner_policy(spec, p["fw"])
            features = _door_features_for_legacy_engine(spec, ctx)
            is_small = spec.indicator_window_groups is not None
            baseline = (
                _indicator_shared_existing_path("小門.dxf", ctx)
                if is_small else _baseline_path(_door_baseline_model_name(spec.model_name), "門.dxf", ctx)
            )
            if baseline is not None:
                data = _call(
                    ae.get_stretched_door_data,
                    None if is_small else _door_baseline_model_name(spec.model_name),
                    p["w"], p["h"], p["t"], p["fw"],
                    p["gap_w"], p["gap_h"],
                    p["fold_left"], p["fold_right"], p["fold_top"], p["fold_bottom"],
                    spec.indicator_hole, spec.door_indicator, spec.door_indicator_offset,
                    frame_edges=spec.frame_edges,
                    indicator_window_groups=spec.indicator_window_groups,
                    corner_policy=corner_policy,
                    nameplate_center_datum_top=_door_nameplate_datum_top(spec),
                )
                scene = ae.DrawingScene()
                scene.extend(data.scene.primitives)
                if features:
                    surface = ae.feature_surface_from_drawing_scene(
                        "indicator_door" if is_small else "door", data.scene
                    )
                    scene.extend(ae.resolved_features_to_primitives(
                        ae.resolve_surface_features(
                            surface, features, float(data.params["total_width"]),
                            float(data.params["total_depth"])
                        )
                    ))
                return scene
            if corner_policy is not None:
                result = _call(
                    build_unknown_door_result,
                    w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                    gap_w=p["gap_w"], gap_h=p["gap_h"],
                    fold_left=p["fold_left"], fold_right=p["fold_right"],
                    fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
                    corner_policy=corner_policy, frame_edges=spec.frame_edges,
                )
                return _call(
                    ae._build_door_scene,
                    w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                    gw=p["gap_w"], gh=p["gap_h"],
                    fl=p["fold_left"], fr=p["fold_right"],
                    ft=p["fold_top"], fb=p["fold_bottom"],
                    draw_stock=ctx.draw_stock, indicator_hole=spec.indicator_hole,
                    door_indicator=spec.door_indicator,
                    door_indicator_offset=spec.door_indicator_offset,
                    is_box_dist=spec.use_box_distance, user_features=features,
                    frame_edges=spec.frame_edges, structural_result=result,
                )
            return _call(
                ae._build_door_scene,
                w=p["w"], h=p["h"], t=p["t"], fw=p["fw"],
                gw=p["gap_w"], gh=p["gap_h"],
                fl=p["fold_left"], fr=p["fold_right"],
                ft=p["fold_top"], fb=p["fold_bottom"],
                draw_stock=ctx.draw_stock, indicator_hole=spec.indicator_hole,
                door_indicator=spec.door_indicator,
                door_indicator_offset=spec.door_indicator_offset,
                is_box_dist=spec.use_box_distance, user_features=features,
                frame_edges=spec.frame_edges,
            )

        if isinstance(spec, BoxBodyPartSpec):
            if not tuple(spec.fold_profile or ()):
                raise ValueError(
                    "canonical Box Body Fold Profile is required for manufacturing"
                )
            # BoxBodyPartSpec keeps legacy strip scalars optional.  The canonical
            # FinalScene path must normalize them exactly like the public DXF
            # exporter; otherwise a valid fold_profile can still crash baseline
            # feature mapping on float(None).
            zl1 = spec.zl1 if spec.zl1 is not None else ae.zl1_def
            zl2 = spec.zl2 if spec.zl2 is not None else ae.zl2_def
            zr1 = spec.zr1 if spec.zr1 is not None else ae.zr1_def
            zr2 = spec.zr2 if spec.zr2 is not None else ae.zr2_def
            z_comp = spec.z_comp if spec.z_comp is not None else ae.z_comp_def
            return _call(
                ae._build_box_body_scene,
                w=spec.width, h=spec.height, d=spec.depth, t=spec.thickness,
                fw=spec.frame_width, zl1=zl1, zl2=zl2,
                zr1=zr1, zr2=zr2, z_comp=z_comp,
                draw_stock=ctx.draw_stock, model_name=spec.model_name,
                user_features=list(spec.features),
                face_features={key: list(value) for key, value in spec.face_features.items()},
                head_corner_policy=spec.head_corner_policy,
                tail_corner_policy=spec.tail_corner_policy,
                fold_profile=spec.fold_profile or None,
                structural_result=_box_body_structural_result,
            )

        if isinstance(spec, EndCapPartSpec):
            resolved = resolve_endcap_request(spec)
            common = dict(
                w=resolved.width, d=resolved.depth, t=resolved.thickness, fw=resolved.frame_width,
                yl1=resolved.fold_left, yr1=resolved.fold_right,
                nominal_yl1=resolved.nominal_fold_left, nominal_yr1=resolved.nominal_fold_right,
                box_body_formed_fw_left=resolved.box_body_formed_fw_left,
                box_body_formed_fw_right=resolved.box_body_formed_fw_right,
                ytop1=resolved.fold_top, ybottom1=resolved.fold_bottom,
                x_topology=resolved.x_topology, depth_comp_t=resolved.depth_comp_t,
                draw_stock=ctx.draw_stock, is_tail=resolved.is_tail,
                holes=_legacy_endcap_holes(spec),
            )
            baseline = _baseline_path(resolved.model_name, "封頭尾.dxf", ctx)
            used_stretched_baseline = (
                baseline is not None and abs(float(resolved.depth_comp_t) - 3.0) <= 1e-9
            )
            if used_stretched_baseline:
                data = _call(
                    ae._build_stretched_end_cap_scene,
                    resolved.model_name, resolved.width, resolved.height or resolved.depth, resolved.depth,
                    resolved.thickness, resolved.frame_width,
                    x_topology=resolved.x_topology,
                    box_body_formed_fw_left=resolved.box_body_formed_fw_left,
                    box_body_formed_fw_right=resolved.box_body_formed_fw_right,
                    draw_stock=ctx.draw_stock, is_tail=resolved.is_tail, holes=common["holes"],
                    corner_policy=resolved.corner_policy,
                )
                scene = data.scene
            elif resolved.corner_policy is not None:
                scene = _call(
                    ae._build_unknown_end_cap_scene,
                    corner_policy=resolved.corner_policy,
                    **common,
                )
            else:
                scene = _call(ae._build_end_cap_scene, model_name=resolved.model_name, **common)
            if not used_stretched_baseline:
                scene = _merge_baseline_endcap_holes(
                    scene, _baseline_endcap_holes_for_request(resolved, ctx)
                )
            return _scene_with_authoritative_fold_profiles(
                scene, resolved.fold_profile_x, resolved.fold_profile_y
            )

        if isinstance(spec, BasePlatePartSpec):
            # Family shrink defines the nominal finished face.  Local seam
            # relief is applied afterwards to the already-resolved plate.
            # Receiving is not a special zero-shrink case.
            st = spec.shrink_top
            sb = spec.shrink_bottom
            sl = spec.shrink_left
            sr = spec.shrink_right
            if spec.corner_policy is not None:
                from .sheetmetal_part_adapters import build_unknown_base_plate_result
                result = _call(
                    build_unknown_base_plate_result,
                    w=spec.width, h=spec.height, t=spec.thickness,
                    shrink_top=st, shrink_bottom=sb,
                    shrink_left=sl, shrink_right=sr,
                    bend=spec.bend, corner_policy=spec.corner_policy,
                )
            else:
                from .sheetmetal_part_adapters import build_base_plate_result
                result = _call(
                    build_base_plate_result,
                    w=spec.width, h=spec.height, t=spec.thickness,
                    shrink_top=st, shrink_bottom=sb,
                    shrink_left=sl, shrink_right=sr,
                    bend=spec.bend,
                )
            if (spec.box_body_fold_profile and spec.box_body_structure_state) or spec.seam_positions:
                from .box_body_structure import resolve_box_body_structure, apply_base_plate_structure_reliefs
                box_structure = None
                if spec.box_body_fold_profile and spec.box_body_structure_state:
                    box_structure = resolve_box_body_structure(
                        spec.box_body_fold_profile, w=spec.width, h=spec.height, t=spec.thickness,
                        structure_state=spec.box_body_structure_state,
                    )
                result = apply_base_plate_structure_reliefs(
                    result, box_w=spec.width, shrink_left=sl, shrink_right=sr,
                    thickness=spec.thickness, structure=box_structure,
                    structure_state=spec.box_body_structure_state,
                    seam_positions=spec.seam_positions if spec.seam_positions else None,
                )
            return _call(
                ae._build_base_plate_scene,
                w=spec.width, h=spec.height, t=spec.thickness,
                st=st, sb=sb,
                sl=sl, sr=sr, bend=spec.bend,
                draw_stock=ctx.draw_stock, user_features=list(spec.features),
                structural_result=result,
            )

        if isinstance(spec, IndicatorBoxPartSpec):
            data = _call(
                ae._build_stretched_indicator_box_scene,
                None, list(spec.layer_groups), spec.thickness,
                draw_stock=ctx.draw_stock, user_features=list(spec.features),
                corner_policy=spec.corner_policy,
            )
            return data.scene

    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


from .manufacturing_render_data import (
    FoldGuide,
    fold_guides_from_final_scene,
    MaterialSegment,
    UnfoldedBlankTopology,
    _profile_material_segments,
    PartRenderData,
    collision_part_from_render_data,
    UnfoldedBlankInfo,
    _measure_one_unfolded_blank,
    measure_unfolded_blanks,
    BoxBodyPieceRenderData,
    BoxBodyStructureRenderData,
    material_polygon_from_final_scene,
    _translated_scene,
    _exploded_box_body_preview,
)

def build_inner_door_panel_render_data(panel) -> PartRenderData:
    """Build one flat physical inner-door panel from its canonical part."""
    from .inner_door_panels import InnerDoorPanelPart
    from .sheetmetal_drawing import DrawingScene, PolylinePrimitive
    from .sheetmetal_geometry import Vec2

    if not isinstance(panel, InnerDoorPanelPart):
        raise TypeError("panel must be InnerDoorPanelPart")
    w = float(panel.width)
    h = float(panel.height)
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0.0, 0.0), Vec2(w, 0.0), Vec2(w, h), Vec2(0.0, h)),
        layer="CUTTING", closed=True,
    ))
    topology = UnfoldedBlankTopology(
        piece_id=str(panel.stable_id),
        x_segments=(MaterialSegment("X", "inner_door_panel_width", w, "INNER_DOOR_PANEL_FINISHED_AREA"),),
        y_segments=(MaterialSegment("Y", "inner_door_panel_height", h, "INNER_DOOR_PANEL_FINISHED_AREA"),),
        source="INNER_DOOR_PANEL_FINISHED_AREA", revision=1,
    )
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=(),
        metadata={
            "stable_id": str(panel.stable_id),
            "inner_door_id": str(panel.inner_door_id),
            "cell_key": str(panel.cell_key),
            "thickness": float(panel.thickness),
        },
        unfolded_topology=topology,
    )


def build_inner_door_frame_render_data(frame) -> PartRenderData:
    """Build one inner-door frame FinalScene from its canonical physical part.

    This consumes the already-derived positive material chain. The signed chain
    remains metadata/direction semantics; no negative material length enters the
    drawing or manufacturing topology.
    """
    from .inner_door_frames import InnerDoorFramePart
    from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives
    from .sheetmetal_geometry import FoldSegment, StripFoldChain, build_strip_outline, build_strip_bend_segments
    from .sheetmetal_part_adapters import StructuralGeometryResult

    if not isinstance(frame, InnerDoorFramePart):
        raise TypeError("frame must be InnerDoorFramePart")
    chain = StripFoldChain(
        segments=tuple(
            FoldSegment(str(row.phase6_key or f"segment_{index}"), float(row.length), 0.0)
            for index, row in enumerate(frame.fold_profile)
        ),
        height=float(frame.span),
    )
    structural = StructuralGeometryResult(
        outline=tuple(build_strip_outline(chain)),
        bends=tuple(build_strip_bend_segments(chain)),
        width=float(chain.total_width),
        height=float(chain.height),
        topology=chain,
    )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural))

    topology = UnfoldedBlankTopology(
        piece_id=str(frame.stable_id),
        x_segments=tuple(
            MaterialSegment("X", str(row.phase6_key or f"segment_{index}"), float(row.length), "INNER_DOOR_FRAME_FOLD_CHAIN")
            for index, row in enumerate(frame.fold_profile)
        ),
        y_segments=(MaterialSegment("Y", "frame_span", float(frame.span), "INNER_DOOR_FRAME_EXPLICIT_SPAN"),),
        source="INNER_DOOR_FRAME_FOLD_CHAIN", revision=1,
    )
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={
            "stable_id": str(frame.stable_id),
            "inner_door_id": str(frame.inner_door_id),
            "frame_side": str(frame.side),
            "signed_fold_chain": tuple(float(v) for v in frame.signed_fold_chain),
            "material_lengths": tuple(float(v) for v in frame.material_lengths),
            "fold_profile": tuple(frame.fold_profile),
        },
        unfolded_topology=topology,
    )


def build_box_body_divider_render_data(
    divider, context: ManufacturingContext | None = None
) -> PartRenderData:
    """Build one canonical box-body divider from its resolved material chain.

    Divider baseline DXF owns the certified fixed-hole and CROSS relief reference.
    Runtime CUTTING is not copied as fixed vertices: the Certified Registry
    parameterizes CROSS from canonical Fold/FW/T inputs, while 3D collision is
    shadow verification only. Baseline holes keep the existing rigid mapping.
    """
    from .door_dividers import BoxBodyDividerPart
    from .sheetmetal_drawing import CirclePrimitive, DrawingScene, structural_result_to_primitives
    from .sheetmetal_geometry import FoldSegment, StripFoldChain, Vec2, build_strip_outline, build_strip_bend_segments
    from .sheetmetal_part_adapters import StructuralGeometryResult

    if not isinstance(divider, BoxBodyDividerPart):
        raise TypeError("divider must be BoxBodyDividerPart")
    ctx = context or ManufacturingContext()
    chain = StripFoldChain(
        segments=tuple(
            FoldSegment(str(row.phase6_key or f"segment_{index}"), float(row.length), 0.0)
            for index, row in enumerate(divider.fold_profile)
        ),
        height=float(divider.span),
    )
    structural = StructuralGeometryResult(
        outline=tuple(build_strip_outline(chain)),
        bends=tuple(build_strip_bend_segments(chain)),
        width=float(chain.total_width),
        height=float(chain.height),
        topology=chain,
    )
    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(structural))

    baseline_model = cabinet_family_policy.baseline_feature_model_name(
        getattr(divider, "model_name", None)
    )
    baseline_path = _baseline_path(baseline_model, "中隔.dxf", ctx)
    mother_rule = None
    if cabinet_family_policy.divider_uses_endcap_6p4_shared_datum(
        getattr(divider, "model_name", None)
    ):
        endcap_path = _baseline_path(baseline_model, "封頭尾.dxf", ctx)
        if endcap_path is None:
            raise ValueError("Receiving Divider shared Ø6.4 requires 封頭尾.dxf")
        mother_rule = _extract_endcap_shared_6p4_mother_rule(endcap_path)
        if mother_rule is None:
            raise ValueError("封頭尾.dxf shared Ø6.4 mother datum unavailable")
    baseline_hole_count = 0
    if baseline_path is not None:
        import ezdxf
        from ezdxf import bbox as ezdxf_bbox

        doc = ezdxf.readfile(baseline_path)
        msp = doc.modelspace()
        source_bounds = ezdxf_bbox.extents(msp)
        if source_bounds.has_data:
            source_min_x = float(source_bounds.extmin.x)
            source_max_x = float(source_bounds.extmax.x)
            source_min_y = float(source_bounds.extmin.y)
            source_w = source_max_x - source_min_x
            source_h = float(source_bounds.extmax.y) - source_min_y
            # Baseline long X axis maps to Divider span Y; baseline short Y
            # axis maps to fold-chain X.  Preserve the physical source-edge
            # datum under the clockwise 90-degree rigid rotation:
            #   source min-Y -> Divider min-X
            #   source max-X -> Divider min-Y
            # The baseline file owns fixed-hole offsets from those edges; a
            # larger Divider span must not re-center the old hole envelope.
            offset_x = 0.0
            offset_y = 0.0
            for index, entity in enumerate(msp.query("CIRCLE")):
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                handle = str(getattr(entity.dxf, "handle", "") or "").strip().upper()
                source_id = handle or f"XYR:{cx:.6f}:{cy:.6f}:{float(entity.dxf.radius):.6f}"
                scene.add(CirclePrimitive(
                    center=Vec2(
                        offset_x + (cy - source_min_y),
                        offset_y + (source_max_x - cx),
                    ),
                    radius=float(entity.dxf.radius),
                    layer="CUTTING",
                    source_type="baseline_divider_hole",
                    source_id=f"divider:baseline_hole:{source_id}:{index}",
                ))
                baseline_hole_count += 1
    topology = UnfoldedBlankTopology(
        piece_id=str(divider.stable_id),
        x_segments=tuple(
            MaterialSegment("X", str(row.phase6_key or f"segment_{index}"), float(row.length), "BOX_BODY_DIVIDER_FOLD_CHAIN")
            for index, row in enumerate(divider.fold_profile)
        ),
        y_segments=(MaterialSegment("Y", "divider_span", float(divider.span), "DOOR_LAYOUT_BOUNDARY_SPAN"),),
        source="BOX_BODY_DIVIDER_FOLD_CHAIN", revision=1,
    )
    return PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata={
            "stable_id": str(divider.stable_id),
            "owner": "box_body",
            "model_name": (str(divider.model_name).strip() if divider.model_name else ""),
            "axis": str(divider.axis),
            "boundary_key": str(divider.boundary_key),
            "handle_side": bool(divider.handle_side),
            "formed_core_depth": float(divider.formed_core_depth),
            "physical_geometry_contract": dict(divider.physical_geometry_contract),
            "signed_fold_chain": tuple(float(v) for v in divider.signed_fold_chain),
            "material_lengths": tuple(float(v) for v in divider.material_lengths),
            "adjacent_cells": tuple(divider.adjacent_cells),
            "baseline_feature_model": baseline_model,
            "baseline_divider_hole_count": int(baseline_hole_count),
            "endcap_shared_6p4_mother_rule": mother_rule,
        },
        unfolded_topology=topology,
    )


def build_box_body_structure_render_data(
    spec: BoxBodyPartSpec, context: ManufacturingContext | None = None
) -> BoxBodyStructureRenderData:
    """Resolve Box Body structure into independent authoritative FinalScenes.

    This is the multi-piece manufacturing boundary. The legacy integral path is
    intentionally still available through ``build_part_render_data``.
    """
    from .box_body_structure import (
        resolve_box_body_structure,
        resolve_box_body_piece_face_features,
    )
    from .sheetmetal_drawing import DrawingScene, structural_result_to_primitives, resolved_features_to_primitives

    ctx = context or ManufacturingContext()
    if not spec.fold_profile:
        raise ValueError("多件式箱身需要權威 Fold Profile")
    structure = resolve_box_body_structure(
        spec.fold_profile,
        w=float(spec.width), h=float(spec.height), t=float(spec.thickness), d=float(spec.depth),
        structure_state=spec.structure_state,
        back_panel_contract=spec.back_panel_contract,
        head_corner_policy=spec.head_corner_policy, tail_corner_policy=spec.tail_corner_policy,
        head_ybottom1=float(spec.head_ybottom1), tail_ybottom1=float(spec.tail_ybottom1),
    )
    feature_stores = resolve_box_body_piece_face_features(
        structure, face_features=spec.face_features,
        w=float(spec.width), h=float(spec.height), d=float(spec.depth), t=float(spec.thickness),
        head_corner_policy=spec.head_corner_policy, tail_corner_policy=spec.tail_corner_policy,
    )
    pieces = []
    for piece in structure.pieces:
        scene = DrawingScene()
        if ctx.draw_stock:
            scene.add(ae.build_stock_outline(piece.structural.width, piece.structural.height))
        scene.extend(structural_result_to_primitives(piece.structural))
        if piece.role == "back" and spec.back_panel_contract:
            contract = dict(spec.back_panel_contract or {})
            for profile in tuple(contract.get("fixed_slot_profiles") or ()):
                scene.add_polyline(profile, layer="CUTTING", closed=True)
            opening = contract.get("opening")
            if opening is not None:
                x0, y0, x1, y1 = map(float, opening)
                scene.add_polyline(
                    ((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                    layer="CUTTING",
                    closed=True,
                )
        resolved_features = tuple(feature_stores.get(piece.key, ()) or ())
        if resolved_features:
            scene.extend(resolved_features_to_primitives(resolved_features))
        piece_x = _profile_material_segments("X", tuple(piece.fold_profile or ()), source="BOX_BODY_PIECE_FOLD_PROFILE")
        if not piece_x:
            piece_x = (MaterialSegment("X", "piece_width", float(piece.structural.width), "BOX_BODY_STRUCTURAL_RESULT"),)
        topology = UnfoldedBlankTopology(
            piece_id=str(piece.key),
            x_segments=piece_x,
            y_segments=(MaterialSegment("Y", "piece_height", float(piece.structural.height), "BOX_BODY_STRUCTURAL_RESULT"),),
            source="BOX_BODY_PHYSICAL_PIECE", revision=1,
        )
        metadata = {}
        if piece.role == "back" and spec.back_panel_contract:
            metadata["back_panel_contract"] = dict(spec.back_panel_contract)
            metadata["back_panel_mode"] = str(spec.back_panel_contract.get("mode") or "FULL")
        render_data = PartRenderData(
            scene=scene,
            material=material_polygon_from_final_scene(scene),
            fold_guides=fold_guides_from_final_scene(scene),
            metadata=metadata,
            unfolded_topology=topology,
        )
        pieces.append(BoxBodyPieceRenderData(
            key=piece.key, role=piece.role,
            formed_w_start=float(piece.formed_w_start), formed_w_end=float(piece.formed_w_end),
            fold_profile=tuple(piece.fold_profile), render_data=render_data,
            formed_outer_width=float(piece.formed_outer_dimensions[0]),
            formed_outer_height=float(piece.formed_outer_dimensions[1]),
            formed_y_offset=float(getattr(piece, "formed_y_offset", 0.0)),
        ))
    piece_tuple = tuple(pieces)
    return BoxBodyStructureRenderData(
        structure_type=structure.structure_type, pieces=piece_tuple,
        preview_render_data=_exploded_box_body_preview(piece_tuple),
        canonical_strip_render_data=build_part_render_data(spec, ctx),
        warnings=tuple(structure.warnings),
    )


def generate_box_body_structure_parts(
    spec: BoxBodyPartSpec,
    output_dir: str | os.PathLike[str],
    context: ManufacturingContext | None = None,
) -> tuple[PartExportResult, ...]:
    """Export every physical Box Body piece from the same resolved FinalScenes."""
    ctx = context or ManufacturingContext()
    data = build_box_body_structure_render_data(spec, ctx)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    labels = {
        "left": "左箱身", "right": "右箱身", "middle": "中箱身",
        "left_side": "左側板", "right_side": "右側板", "back": "後面板",
        "integral": "箱身",
    }
    results = []
    for piece in data.pieces:
        name = labels.get(piece.role, piece.key) + ".dxf"
        path = root / name
        _manufacturing_export.save_part_render_data_dxf(piece.render_data, path, overwrite=bool(ctx.overwrite))
        results.append(PartExportResult(
            part_kind=piece.key, output_path=str(path),
            exporter_name="final_scene_box_body_structure_export", used_baseline=False,
            baseline_path=None, expected_baseline_path=None,
        ))
    return tuple(results)




def _resolved_endcap_bottom_joint_relation(spec: EndCapPartSpec):
    """Return the explicit BOTTOM relation for this EndCap, or None.

    This intentionally ignores receiving.bottom_external_wrap: that field is a
    legacy persistence/geometry mirror and is not an assembly source of truth.
    """
    from .assembly_joint import AssemblyJoint, AssemblyJointRelation

    part_key = "tail" if bool(spec.is_tail) else "head"
    for raw in tuple(getattr(spec, "assembly_joints", ()) or ()):
        try:
            joint = raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        except Exception:
            continue
        if str(getattr(joint, "subject_part", "")) != part_key and str(getattr(joint, "target_part", "")) != part_key:
            continue
        edge = str(getattr(joint, "edge", "") or "").upper()
        if edge != "BOTTOM":
            continue
        relation = getattr(joint, "relation", None)
        try:
            return relation if isinstance(relation, AssemblyJointRelation) else AssemblyJointRelation(str(relation))
        except Exception:
            return None
    return None


def _replace_receiving_bottom_relief_from_registry(render_data, spec: EndCapPartSpec):
    """Replace the legacy receiving bottom corner cut with certified Joint geometry.

    Receiving lower external wrap is a dedicated lower-face manufacturing relation.
    It is independent from the EndCap's INSERT / OVERLAY / INSERT_OVERLAY selector;
    those high-level intents must not choose or redefine the WRAP relief algorithm.
    """
    if not spec.box_body_structure_state:
        return render_data
    try:
        from .assembly_joint import AssemblyJointRelation
        if not cabinet_family_policy.bottom_relief_registry_applicable(
            spec.model_name, spec.box_body_structure_state
        ):
            return render_data
        if _resolved_endcap_bottom_joint_relation(spec) is not AssemblyJointRelation.WRAP:
            return render_data
    except Exception:
        return render_data

    policy = spec.corner_policy
    if policy is None:
        return render_data

    from shapely.ops import unary_union
    from .assembly_collision import _corner_name_for_component, _scene_with_replaced_primary_cutting
    from .assembly_geometry import restore_unrelieved_endcap_material
    from .certified_relief_registry import lookup_certified_endcap_relief

    resolved = resolve_endcap_request(spec)
    certified = lookup_certified_endcap_relief(
        assembly_intent=policy.bottom_left.type_id,
        endcap_render_data=render_data,
        box_body_x_profile=(),
        endcap_x_profile=resolved.fold_profile_x,
        endcap_y_profile=resolved.fold_profile_y,
        sheet_thickness=resolved.thickness,
        cabinet_family=spec.model_name or "ANY",
        joint_face="BOTTOM",
        joint_signature_relations=("WRAP",),
        box_body_structure_state=spec.box_body_structure_state,
    )
    if certified is None:
        return render_data

    restored = restore_unrelieved_endcap_material(render_data.material)
    if restored is None or getattr(restored, "is_empty", True):
        return render_data
    legacy_removed = restored.difference(render_data.material)
    components = (legacy_removed,) if getattr(legacy_removed, "geom_type", "") == "Polygon" else tuple(
        geom for geom in getattr(legacy_removed, "geoms", ())
        if getattr(geom, "geom_type", "") == "Polygon" and float(geom.area) > 1e-9
    )
    bottom_names = {str(item.corner_name) for item in tuple(certified.corner_reliefs or ())}
    retained = []
    for component in components:
        corner_name = _corner_name_for_component(component, restored.bounds)
        if corner_name not in bottom_names:
            retained.append(component)
    all_cuts = tuple(retained) + tuple(certified.cut_polygons or ())
    solved_material = restored.difference(unary_union(all_cuts)) if all_cuts else restored
    if solved_material.is_empty:
        raise ValueError("certified receiving bottom relief removed all EndCap material")
    if not solved_material.is_valid:
        solved_material = solved_material.buffer(0)
    solved_scene = _scene_with_replaced_primary_cutting(render_data.scene, solved_material)
    solved_scene = _scene_with_authoritative_fold_profiles(
        solved_scene, resolved.fold_profile_x, resolved.fold_profile_y
    )
    metadata = dict(getattr(render_data, "metadata", {}) or {})
    metadata["receiving_bottom_relief_rule"] = {
        "rule_id": certified.rule_id,
        "revision": certified.rule_revision,
        "trust_level": certified.trust_level.value,
        "geometry_evidence": dict(certified.geometry_evidence or {}),
    }
    return PartRenderData(
        scene=solved_scene,
        material=material_polygon_from_final_scene(solved_scene),
        fold_guides=fold_guides_from_final_scene(solved_scene),
        metadata=metadata,
        unfolded_topology=getattr(render_data, "unfolded_topology", None),
    )

def _unfolded_topology_for_spec(spec: PartSpec, *, piece_id: str = "") -> UnfoldedBlankTopology | None:
    """Build blank envelope only from authoritative PartSpec/Fold Profile semantics."""
    if isinstance(spec, EndCapPartSpec):
        resolved = resolve_endcap_request(spec)
        x_rows = tuple(resolved.fold_profile_x or ())
        y_rows = tuple(resolved.fold_profile_y or ())
        if not x_rows:
            if resolved.x_topology == "flat":
                x_rows = (FoldProfileSegment(resolved.width, phase6_key="endcap_w_flat"),)
            else:
                # Scalar compatibility: explicit physical segments, not relieved polygon bounds.
                core = max(0.0, resolved.width - 4.0 * resolved.thickness)
                x_rows = (
                    FoldProfileSegment(resolved.nominal_fold_left, phase6_key="yl1"),
                    FoldProfileSegment(core, phase6_key="endcap_w_core"),
                    FoldProfileSegment(resolved.nominal_fold_right, phase6_key="yr1"),
                )
        if not y_rows:
            core = max(0.0, resolved.depth - resolved.depth_comp_t * resolved.thickness)
            y_rows = (
                FoldProfileSegment(resolved.fold_top, phase6_key="ytop1"),
                FoldProfileSegment(resolved.frame_width, phase6_key="fw"),
                FoldProfileSegment(core, phase6_key="endcap_d_core"),
                FoldProfileSegment(resolved.fold_bottom, phase6_key="ybottom1"),
            )
        return UnfoldedBlankTopology(
            piece_id=str(piece_id or ("tail" if resolved.is_tail else "head")),
            x_segments=_profile_material_segments("X", x_rows, source="ENDCAP_FOLD_PROFILE"),
            y_segments=_profile_material_segments("Y", y_rows, source="ENDCAP_FOLD_PROFILE"),
            source="ENDCAP_FOLD_PROFILE", revision=1,
        )
    if isinstance(spec, BoxBodyPartSpec) and spec.fold_profile:
        return UnfoldedBlankTopology(
            piece_id=str(piece_id or "box_body"),
            x_segments=_profile_material_segments("X", spec.fold_profile, source="BOX_BODY_FOLD_PROFILE"),
            y_segments=(MaterialSegment("Y", "box_body_height", float(spec.height), "BOX_BODY_PART_SPEC"),),
            source="BOX_BODY_FOLD_PROFILE", revision=1,
        )
    return None


def build_part_render_data(
    spec: PartSpec, context: ManufacturingContext | None = None
) -> PartRenderData:
    """Return final manufacturing material + scene through the bounded render owner."""
    return _manufacturing_render.build_part_render_data(
        spec,
        context,
        render_data_type=PartRenderData,
        build_box_body_result_from_fold_profile=build_box_body_result_from_fold_profile,
        build_part_scene=build_part_scene,
        box_body_face_contexts_from_strip=box_body_face_contexts_from_strip,
        material_polygon_from_final_scene=material_polygon_from_final_scene,
        fold_guides_from_final_scene=fold_guides_from_final_scene,
        unfolded_topology_for_spec=_unfolded_topology_for_spec,
        endcap_scalar=_endcap_scalar,
        default_fold_left=ae.yl1_def,
        default_fold_right=ae.yr1_def,
        replace_receiving_bottom_relief_from_registry=_replace_receiving_bottom_relief_from_registry,
        resolve_endcap_request=resolve_endcap_request,
        scene_with_authoritative_fold_profiles=_scene_with_authoritative_fold_profiles,
        recursive_build_part_render_data=build_part_render_data,
    )
