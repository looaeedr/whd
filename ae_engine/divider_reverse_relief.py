# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Reconstruct Receiving Divider CROSS relief from physical Fold + 3D contact.

The collision footprint alone is only a minimum penetrating envelope, NOT
manufacturing CUTTING: negative mating Folds also require a round-bottom slot.
This inverse path reads resolved physical Fold identities and actual pre-cut
world contact, never a certified formula record, oracle, or a fixed +1 mm.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from shapely.affinity import translate
from shapely.ops import unary_union

from .sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode,
    placed_corner_cut_polygons, resolve_corner_relief,
)


@dataclass(frozen=True)
class InverseDividerCross:
    cut_polygon_2d: object
    parameters: dict
    evidence: dict


def reconstruct_receiving_divider_cross(*, divider, box_body, candidate, thickness: float):
    """Recover a complete CROSS contour from real folds, contact and collision.

    Source Fold topology resolves slotted/non-slotted ends; physical dimensions
    convert outside FW to *flat* material space. Both ends MUST show physically
    verified pre-cut collision; missing contact or invalid topology fails closed.
    """
    if candidate is None or not getattr(candidate, "cut_polygon_2d", None):
        raise ValueError("inverse needs actual nonempty pre-cut full-thickness interference")
    t = float(thickness)
    if not isfinite(t) or t <= 0:
        raise ValueError("inverse needs a positive physical sheet thickness")

    metadata = dict(getattr(divider.render_data, "metadata", {}) or {})
    if str(metadata.get("axis", "")).upper() != "HORIZONTAL":
        raise ValueError("inverse CROSS applies to horizontal Divider only")
    if str(metadata.get("model_name", "")) != "受電箱":
        raise ValueError("inverse CROSS only handles verified Receiving topology")
    part_contract = dict(metadata.get("physical_geometry_contract") or {})
    core = dict(part_contract.get("core_physical_segment") or {})
    fw = dict(part_contract.get("fw_physical_face") or {})
    core_band = tuple(core.get("flat_band") or ())
    fw_band = tuple(fw.get("flat_band") or ())
    if len(core_band) != 2 or len(fw_band) != 2:
        raise ValueError("inverse needs core and physical FW material bands")
    core_start = float(core_band[0])
    fw_material = float(fw_band[1]) - float(fw_band[0])
    if not (core_start > 0 and fw_material > 0):
        raise ValueError("invalid actual Divider core/FW fold dimensions")

    signed = tuple(float(v) for v in metadata.get("signed_fold_chain") or ())
    material = tuple(float(v) for v in metadata.get("material_lengths") or ())
    if len(signed) != len(material) or len(signed) != 4:
        raise ValueError("inverse requires one Receiving four-segment physical Fold")
    if any(not isfinite(v) for v in (*signed, *material)):
        raise ValueError("inverse material/Fold geometry must be finite")
    if abs(fw_material - float(fw["material_dimension"])) > 1e-5:
        raise ValueError("inverse FW flat band disagrees with material segment")
    if abs(t - float(metadata.get("thickness", t))) > 1e-6:
        raise ValueError("inverse T inconsistent with physical Divider")

    pieces = {str(piece.role): piece for piece in tuple(box_body.render_data.pieces or ())}
    if not {"left_side", "right_side"}.issubset(pieces):
        raise ValueError("inverse requires both physical Receiving side sheets")
    from .divider_manufacturing import _divider_object_mating_fold_signs
    orientation = _divider_object_mating_fold_signs(divider, box_body)
    signs = dict(orientation["sign_by_end"])
    negative = [end for end in ("MIN_Y", "MAX_Y") if signs[end] < 0.0]
    if len(negative) != 1:
        raise ValueError("inverse U-slot needs unique actual negative mating Fold")
    slot_end = negative[0]

    evidence = dict(candidate.evidence or {})
    projections = dict(evidence.get("projection_by_source") or {})
    contact_u_widths = {}
    contact_v_projection = {}
    for side, key, required_edge in (
        ("MIN_Y", "box_body:left_side", "MIN_Y"),
        ("MAX_Y", "box_body:right_side", "MAX_Y"),
    ):
        source = dict(projections.get(key) or {})
        stages = tuple(
            dict(v) for v in dict(source.get("physical_stages") or {}).values()
            if str(v.get("role")) == "PHYSICAL_FW_CONTACT_PRIMARY_RELIEF"
        )
        if len(stages) != 1 or str(stages[0].get("edge")) != required_edge:
            raise ValueError("inverse requires one real FW contact per physical side")
        band = tuple(stages[0].get("fw_contact_bounds") or ())
        if len(band) != 4:
            raise ValueError("missing real FW mapped contact band")
        u_span = float(band[2]) - float(band[0])
        v_span = float(band[3]) - float(band[1])
        if u_span <= 0 or v_span <= 0:
            raise ValueError("invalid physical FW contact")
        contact_u_widths[side] = u_span
        contact_v_projection[side] = v_span
        if not source.get("penetrating_bands"):
            raise ValueError("inverse requires true-thickness penetration on both side sheets")

    # The longitudinal FW contact span is the physical MATERIAL-space mating
    # width; the orthogonal world projection (26 mm for W800/T2) is *not*
    # the final CUTTING depth.
    depths = tuple(contact_u_widths.values())
    if abs(depths[0] - depths[1]) > 1e-5:
        raise ValueError("physical left/right FW contact spans disagree")
    primary_depth = (depths[0] + depths[1]) / 2.0
    # This independent outside->flat witness must agree with actual mapped
    # contact, or the source Fold topology/placement is inconsistent.
    formed_fw = float(fw.get("outside_dimension", 0.0))
    if abs(primary_depth - (formed_fw - t)) > 1e-5:
        raise ValueError("physical FW contact contradicts outside/T conversion")

    # Complete CROSS cut envelope follows real Divider fold boundaries,
    # not just the narrow source/target triangle intersection.
    # Independent physical outside-terminal witness. In the corrected
    # left DXF, the reflected side-rear terminal reaches one sheet
    # thickness beyond the base core+FW slit. The slot/corner must cover
    # that actual true-thickness band, while old Fold order has no extra.
    left_keys = tuple(str(seg.phase6_key) for seg in pieces["left_side"].fold_profile)
    mirrored = left_keys == (
        "zl1", "d_left", "fw_left", "zl2", "side_rear_bend_left",
    )
    slotted_u = core_start + fw_material + (t if mirrored else 0.0)
    plain_u = core_start + abs(signed[-1]) + t
    first_outside = abs(signed[0])
    slot_width = fw_material - first_outside

    # The U-slot is required where the actual *object* mating Fold is negative.
    # Its straight stage follows that source Fold's formed (operator) length.
    negative_source = pieces["left_side"] if slot_end == "MIN_Y" else pieces["right_side"]
    matching = dict(orientation.get("evidence") or {}).get(slot_end)
    key = str(dict(matching or {}).get("phase6_key") or "")
    matches = [
        float(getattr(seg, "formed_length"))
        for seg in tuple(negative_source.fold_profile or ())
        if str(getattr(seg, "phase6_key", "")) == key
        and getattr(seg, "formed_length", None) is not None
    ]
    if len(matches) != 1 and key == "zl2":
        # The mirrored left sheet's actual negative Fold is zl2, but the
        # registry's U-slot straight parameter remains the original outer
        # 22-mm leg formed-length authority (zl1). Preserve that operator
        # value after remapping the topology; do not infer it from D=340.
        matches = [
            float(seg.formed_length) for seg in negative_source.fold_profile
            if str(seg.phase6_key) == "zl1" and seg.formed_length is not None
        ]
    if len(matches) != 1:
        raise ValueError("negative mating Fold has no authoritative formed length")
    slot_straight = abs(matches[0])
    if min(slotted_u, plain_u, slot_width, slot_straight) <= 0:
        raise ValueError("inverse generated impossible CROSS geometry")
    slot_radius = slot_width / 2.0

    minx, miny, maxx, maxy = map(float, divider.render_data.material.bounds)
    width, height = maxx-minx, maxy-miny
    cuts = []
    for end, corner_name in (("MIN_Y", "bottom_left"), ("MAX_Y", "top_left")):
        slotted = end == slot_end
        selection = CornerTypeSelection(
            CornerTypeId.CROSS,
            cross_mode=CrossCornerMode.STANDARD,
            **({
                "slot_width": slot_width,
                "slot_straight_depth": slot_straight,
                "slot_radius": slot_radius,
            } if slotted else {}),
        )
        relief = resolve_corner_relief(
            selection, fold_u=slotted_u if slotted else plain_u,
            fold_v=primary_depth, thickness=t, fw=fw_material,
        )
        cuts.extend(
            translate(poly, xoff=minx, yoff=miny)
            for poly in placed_corner_cut_polygons(
                corner_name=corner_name, relief=relief,
                width=width, height=height,
            )
        )
    inverse = unary_union(tuple(cuts)).intersection(divider.render_data.material)
    if inverse.is_empty or not inverse.is_valid:
        raise ValueError("inverse full CROSS is empty or invalid")
    # Real penetrating material must be covered, regardless of the topology's
    # chosen manufacturing continuation/slot. No smoothing/tolerance may hide
    # a true penetration.
    uncovered = candidate.cut_polygon_2d.difference(inverse)
    if float(uncovered.area) > 1e-4:
        raise ValueError(
            f"inverse CROSS leaves real 3D collision unrelieved: {uncovered.area}"
        )
    return InverseDividerCross(
        cut_polygon_2d=inverse,
        parameters={
            "slotted_fold_u": slotted_u, "plain_fold_u": plain_u,
            "fold_v": primary_depth, "slot_width": slot_width,
            "slot_straight_depth": slot_straight, "slot_radius": slot_radius,
            "slot_end": slot_end,
        },
        evidence={
            "dimension_source": "PHYSICAL_FW_CONTACT_AND_REAL_FOLD_TOPOLOGY",
            "contact_u_width": contact_u_widths,
            "contact_v_projection_only": contact_v_projection,
            "world_3d_collision_cut_area": float(candidate.cut_polygon_2d.area),
            "full_inverse_cut_area": float(inverse.area),
            "covered_collision": True,
            "orientation_source": orientation["evidence"],
        },
    )
