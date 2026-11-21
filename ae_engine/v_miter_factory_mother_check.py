# -*- coding: utf-8 -*-
"""#3317: replace one old factory CornerType cut from its *actual* mother blank.

This is an Engine-only CHECK projection. It DOES NOT manufacture a fifth
CornerType, change the canonical CUTTING, or presume a measured inside R/BA.
Both the original factory-generated contour and its parent blank are rebuilt
from the same immutable PartSpec/Factory code used for ordinary production.
A mismatch, ambiguous removed component or extra non-factory relief blocks
the replacement rather than guessing missing sheet metal.
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point, Polygon, box

from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck,
    _single_source_material,
    project_v_miter_sharp_source_perimeter_check,
)
from .v_miter_ideal_mating import VMiterIdealMatingCandidate


@dataclass(frozen=True)
class VMiterFactoryMotherReplacementCheck:
    """Identity of reconstructed factory mother and one selected original cut."""

    actual_original_material_area_mm2: float
    restored_corner_material_area_mm2: float
    restored_source_material_area_mm2: float
    source_check: VMiterSourceBoundSharpCheck
    source_kind: str = "PARTSPEC_REBUILT_FACTORY_MOTHER_SINGLE_CORNER_REPLACEMENT_CHECK"
    manufacturing_status: str = "V_MITER_FACTORY_MOTHER_CHECK_ONLY_UNCERTIFIED"


def _factory_original_shape(spec) -> tuple[Polygon, float, float]:
    """Re-evaluate existing typed Factory; never derive a blank from view bounds."""
    if isinstance(spec, DoorPartSpec) and spec.corner_policy is not None:
        from .manufacturing_door_indicator import (
            _resolved_door_params, _resolved_door_corner_policy,
        )
        from .sheetmetal_part_adapters import build_unknown_door_result

        physical = _resolved_door_params(spec)
        corner = _resolved_door_corner_policy(spec, physical["fw"])
        result = build_unknown_door_result(
            w=physical["w"], h=physical["h"],
            t=physical["t"], fw=physical["fw"],
            gap_w=physical["gap_w"], gap_h=physical["gap_h"],
            fold_left=physical["fold_left"], fold_right=physical["fold_right"],
            fold_top=physical["fold_top"], fold_bottom=physical["fold_bottom"],
            corner_policy=corner, frame_edges=spec.frame_edges,
        )
        points = result.outline
        # Rebuild the *uncut* manufacturing Fold using the SAME original
        # FourSide factory, with a zero-corner reference policy. No new
        # stand-in coordinates or GUI-created physical crease.
        from .sheetmetal_four_side_geometry import (
            RectCornerReliefPolicy, build_four_side_bend_segments,
        )
        zero_relief = RectCornerReliefPolicy(
            bottom_left_x=0.0, bottom_right_x=0.0,
            top_left_x=0.0, top_right_x=0.0,
            bottom_y=0.0, top_y=0.0,
        )
        uncut_bends = build_four_side_bend_segments(
            result.topology, zero_relief,
        )
    elif isinstance(spec, EndCapPartSpec) and spec.corner_policy is not None:
        from .manufacturing_endcap_compat import resolve_endcap_request
        from .sheetmetal_part_adapters import build_unknown_endcap_result

        current = resolve_endcap_request(spec)
        if current.corner_policy is None:
            raise GeometryError("V_MITER_MOTHER_ORIGINAL_CORNER_POLICY_REQUIRED")
        result = build_unknown_endcap_result(
            w=current.width, d=current.depth, t=current.thickness,
            fw=current.frame_width,
            yl1=current.fold_left, yr1=current.fold_right,
            ytop1=current.fold_top, ybottom1=current.fold_bottom,
            corner_policy=current.corner_policy, x_topology=current.x_topology,
            depth_comp_t=current.depth_comp_t,
            nominal_yl1=current.nominal_fold_left,
            nominal_yr1=current.nominal_fold_right,
            box_body_formed_fw_left=current.box_body_formed_fw_left,
            box_body_formed_fw_right=current.box_body_formed_fw_right,
        )
        points = (
            result.outline if current.is_tail else
            tuple(Vec2(p.x, float(result.height) - p.y) for p in result.outline)
        )
        from .sheetmetal_geometry import build_endcap_topology
        source_fold = build_endcap_topology(result.topology)
        axes = (
            source_fold.left_bend, source_fold.right_bend,
            source_fold.bottom_bend, source_fold.top_chain_bend_1,
            source_fold.top_chain_bend_2,
        )
        if current.is_tail:
            uncut_bends = axes
        else:
            # Mirror once, as the existing formal EndCap Factory does:
            # the Head final scene has the opposite Y orientation.
            uncut_bends = tuple(type(row)(
                row.name,
                Vec2(row.p1.x, float(result.height) - row.p1.y),
                Vec2(row.p2.x, float(result.height) - row.p2.y),
            ) for row in axes)
    else:
        raise GeometryError("V_MITER_MOTHER_REQUIRES_EDITABLE_FOUR_SIDE_FACTORY")
    stock = Polygon([(p.x, p.y) for p in points])
    if not stock.is_valid or stock.is_empty or stock.area <= 0 or stock.interiors:
        raise GeometryError("V_MITER_MOTHER_REBUILT_ORIGINAL_INVALID")
    return stock, float(result.width), float(result.height), tuple(uncut_bends)


def _selected_original_corner_component(
    original: Polygon, mother: Polygon, corner_key: str,
) -> Polygon:
    minx, miny, maxx, maxy = mother.bounds
    corners = {
        "bottom_left": Point(minx, miny),
        "bottom_right": Point(maxx, miny),
        "top_left": Point(minx, maxy),
        "top_right": Point(maxx, maxy),
    }
    if corner_key not in corners:
        raise GeometryError("V_MITER_MOTHER_CORNER_KEY_INVALID")
    missing = mother.difference(original)
    if missing.is_empty:
        raise GeometryError("V_MITER_MOTHER_ALREADY_UNCUT_NO_CORNER_TO_REPLACE")
    components = (
        (missing,) if missing.geom_type == "Polygon"
        else tuple(getattr(missing, "geoms", ()))
    )
    if not components or any(
        item.geom_type != "Polygon" or item.is_empty or item.area <= 0
        for item in components
    ):
        raise GeometryError("V_MITER_MOTHER_CUT_COMPONENTS_INVALID")
    chosen = tuple(item for item in components
                   if item.distance(corners[corner_key]) <= 1e-7)
    if len(chosen) != 1:
        raise GeometryError("V_MITER_MOTHER_SELECTED_FACTORY_CORNER_NOT_UNIQUE")
    cut = chosen[0]
    if any(
        cut.distance(point) <= 1e-7
        for key, point in corners.items() if key != corner_key
    ):
        raise GeometryError("V_MITER_MOTHER_FACTORY_RELIEF_SPANS_MULTIPLE_CORNERS")
    return cut


def project_v_miter_replaced_factory_corner_check(
    spec: DoorPartSpec | EndCapPartSpec,
    render_data: PartRenderData,
    corner_key: str,
    ideal: VMiterIdealMatingCandidate,
) -> VMiterFactoryMotherReplacementCheck:
    """Rebuild and compare exact old factory CUTTING before substituting V.

    Replaces ONLY the selected old factory corner cut in a detached trial.
    All other corners, real holes and unchanged physical BEND are retained
    by the original FinalScene. This is CHECK candidate material, not a new
    production CUTTING or repaired physical crease.
    """
    if not isinstance(render_data, PartRenderData):
        raise GeometryError("V_MITER_MOTHER_CANONICAL_RENDER_DATA_REQUIRED")
    original = _single_source_material(render_data.scene)
    factory_original, width, height, _factory_uncut_bends = _factory_original_shape(spec)
    original_delta = factory_original.symmetric_difference(original).area
    if original_delta > 1e-6:
        raise GeometryError("V_MITER_MOTHER_FINALSCENE_DIFFERS_FROM_FACTORY")
    mother = box(0.0, 0.0, width, height)
    if mother.is_empty or mother.area <= 0 or original.difference(mother).area > 1e-6:
        raise GeometryError("V_MITER_MOTHER_FACTORY_BLANK_NOT_SOURCE_SUPERSET")
    cut = _selected_original_corner_component(original, mother, corner_key)
    restored = original.union(cut)
    if (
        restored.geom_type != "Polygon" or not restored.is_valid or
        restored.is_empty or restored.interiors or restored.area <= original.area
        or restored.difference(mother).area > 1e-6
    ):
        raise GeometryError("V_MITER_MOTHER_LOCAL_CORNER_RESTORE_INVALID")
    new_area = restored.area - original.area
    if abs(new_area - cut.area) > max(1e-6, mother.area * 1e-10):
        raise GeometryError("V_MITER_MOTHER_REPLACED_CORNER_AREA_NOT_CONSERVED")
    # This single detached CUTTING is an explicitly verified factory mother
    # *candidate* only. Never share it with production renderer/exporters.
    candidate = DrawingScene([
        PolylinePrimitive(
            tuple(Vec2(float(x), float(y))
                  for x, y in restored.exterior.coords),
            layer="CUTTING", closed=True,
            semantic_id="v_miter_factory_mother_check_source_only",
        )
    ])
    result = project_v_miter_sharp_source_perimeter_check(candidate, ideal)
    return VMiterFactoryMotherReplacementCheck(
        actual_original_material_area_mm2=original.area,
        restored_corner_material_area_mm2=new_area,
        restored_source_material_area_mm2=restored.area,
        source_check=result,
    )
