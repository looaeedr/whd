# -*- coding: utf-8 -*-
"""#1502/#1503: independently verify base Z, but FIX ear Z by brand maximum.

The ear Z for every tier shares one physical datum resolved from the active
brand's entire current numeric CSV, NOT the selected models or tier depths.
Uncompensated Base Plate / ear gaps remain unverified and unreleasable.
Nothing here certifies ear source BEND, welded contact or manufacturing DXF.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
from .receiving_weld_ear_policy import (
    LARGE_EAR_MATERIAL_THICKNESS_MM, receiving_source_fixing_pitch_x_mm,
)


@dataclass(frozen=True)
class ReceivingTierBaseZTarget:
    layer_index: int
    parent_base_id: str
    world_offset_z_mm: float | None
    base_back_skin_world_z_mm: float | None
    source_depths_mm: tuple[float, ...]
    physical_skin_z_resolved: bool


@dataclass(frozen=True)
class ReceivingTierEarContactTarget:
    ear_id: str
    parent_base_id: str
    layer_index: int
    side: str
    fixing_hole_world_x_mm: float
    fixing_hole_world_y_mm: tuple[float, float]
    side_inside_weld_x_mm: float
    base_back_skin_world_z_mm: float | None
    target_ear_contact_world_z_mm: float | None
    base_skin_z_source_verified: bool
    source_bend_verified: bool = False
    formed_weld_contact_verified: bool = False
    side_plate_marking_export_approved: bool = False
    manufacturing_ready: bool = False


def _current_brand_config(snapshot):
    from .receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
    layout = snapshot.get("receiving_layout")
    sets = layout.get("sets") if isinstance(layout, Mapping) else None
    if not isinstance(sets, (tuple, list)) or not sets:
        raise ValueError("EAR_Z_SOURCE_SET_MISSING")
    active = snapshot.get(RECEIVING_RUNTIME_SELECTION_KEY)
    if isinstance(active, Mapping):
        si, bi = active.get("set_index"), active.get("bay_index")
        # An immutable Phase6 manufacturing DTO transports numeric integers
        # as floats. Normalize only integral, finite quantity indices; the
        # independent persisted Set/Bay stable-ID checks below stay strict.
        # Set/Bay snapshots and fractional/forged selectors are NOT rescued.
        if snapshot.get("active_mode") == "quantity":
            for label, number in (("set_index", si), ("bay_index", bi)):
                if (type(number) is float and isfinite(number)
                        and number.is_integer()):
                    if label == "set_index":
                        si = int(number)
                    else:
                        bi = int(number)
        if (type(si) is not int or si < 0 or si >= len(sets)
                or not isinstance(sets[si], Mapping)
                or sets[si].get("stable_id") != active.get("set_id")):
            raise ValueError(
                "EAR_Z_SET_IDENTITY_DRIFT:"
                f" selected_index={si!r} selected_id={active.get('set_id')!r}"
                f" current_ids={tuple(row.get('stable_id') if isinstance(row, Mapping) else None for row in sets)!r}"
            )
        selected_set = sets[si]
        bays = selected_set.get("bays")
        if (not isinstance(bays, (tuple, list)) or type(bi) is not int
                or bi < 0 or bi >= len(bays)
                or not isinstance(bays[bi], Mapping)
                or bays[bi].get("stable_id") != active.get("bay_id")):
            raise ValueError("EAR_Z_BAY_IDENTITY_DRIFT")
        bay = bays[bi]
    elif (len(sets) == 1 and isinstance(sets[0], Mapping)
          and isinstance(sets[0].get("bays"), (tuple, list))
          and len(sets[0]["bays"]) == 1
          and isinstance(sets[0]["bays"][0], Mapping)):
        selected_set = sets[0]
        bay = selected_set["bays"][0]
    else:
        raise ValueError("EAR_Z_SOURCE_BAY_AMBIGUOUS")
    config = bay.get("nfb_config")
    # switch_brand is an OPTIONAL legacy Set field. Current receiving Set
    # has no such key: saved per-switch source_brand / nfbv5:brand:model own
    # source identity. Never require obsolete Set.brand for a physical tier.
    legacy_brand = selected_set.get("switch_brand")
    if (bay.get("nfb_config_submitted") is not True
            or snapshot.get("nfb_config") != config
            or not isinstance(config, Mapping)):
        raise ValueError("EAR_Z_NFB_SOURCE_IDENTITY_DRIFT")
    return legacy_brand, config


def _tier_source_depths(legacy_brand, config, layer_index):
    """Every physical switch reads its OWN brand/model CSV source.

    Current Set schema does not have switch_brand; layer/slot overrides may
    intentionally use different brands. Missing or inconsistent identity
    blocks only that tier's Z readiness rather than borrowing another model.
    """
    from .receiving_nfb_model_identity import (
        parse_numeric_model_ref, selected_numeric_spec,
    )
    from .receiving_switch_model_catalog import model_depth_mm

    count = config.get("layer_count")
    # Tier identity controls the real NFB depth and therefore the Base Plate
    # world Z. Python considers True == 1 and 1.0 == 1; neither is an
    # authoritative physical tier index from a saved configuration.
    if (type(count) is not int or count <= 0
            or type(layer_index) is not int
            or not 0 <= layer_index < count):
        return ()
    depths = []
    holes = config.get("holes")
    if holes is None:
        return ()
    if not isinstance(holes, (list, tuple)):
        raise ValueError("EAR_Z_SOURCE_HOLE_INVALID")
    for hole in holes:
        if not isinstance(hole, Mapping):
            raise ValueError("EAR_Z_SOURCE_HOLE_INVALID")
        tier = hole.get("layer_index", 0 if count == 1 else None)
        if type(tier) is not int or not 0 <= tier < count:
            return ()
        if tier != layer_index:
            continue
        filename = hole.get("model_filename")
        if not isinstance(filename, str) or not filename:
            return ()
        # V5 encodes a canonical physical brand inside the model ID.
        # Do not require an obsolete Set.switch_brand field or borrow a
        # different Bay's brand for the same physical switch.
        if filename.startswith("nfbv5:"):
            identity = parse_numeric_model_ref(filename)
            if identity is None or hole.get("source_brand") not in (None, identity[0]):
                return ()
            brand = identity[0]
        else:
            brand = hole.get("source_brand", legacy_brand)
        if not isinstance(brand, str) or not brand:
            return ()
        try:
            if filename.startswith("nfbv5:"):
                spec = selected_numeric_spec(brand, filename)
                depth = None if spec is None else spec.depth_mm
            else:
                depth = model_depth_mm(brand, filename)
        except (ValueError, KeyError, TypeError, OSError):
            return ()
        if depth is None:
            return ()
        number = float(depth)
        if not isfinite(number) or number <= 0:
            return ()
        depths.append(number)
    if not depths:
        return ()
    # Many different NFB depths on one FLAT tier are supported by independent
    # PAD patterns. CENTER double-fold uses at most two physical faces and
    # is explicitly rejected by the resolver when more are encountered.
    return tuple(sorted(set(depths), reverse=True))


def committed_receiving_ear_brand_max_depth_mm(
    snapshot: Mapping[str, object],
) -> float:
    """One physical ear Z anchor for the selected Bay, regardless of NFB tiers.

    The entire selected brand numeric CSV owns the maximum depth. Legacy DXF
    hole references can identify the brand but never supply the maximum from
    their own selected dimensions. Mixed brands have no approved single-ear
    Z policy and must fail closed, rather than silently taking a maximum.
    """
    legacy_brand, config = _current_brand_config(snapshot)
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import brand_max_depth_mm

    holes = config.get("holes")
    if not isinstance(holes, (list, tuple)) or not holes:
        raise ValueError("EAR_Z_BRAND_SOURCE_HOLES_MISSING")
    brands = set()
    for hole in holes:
        if not isinstance(hole, Mapping):
            raise ValueError("EAR_Z_BRAND_SOURCE_HOLE_INVALID")
        model_ref = hole.get("model_filename")
        if not isinstance(model_ref, str) or not model_ref:
            raise ValueError("EAR_Z_BRAND_MODEL_MISSING")
        if model_ref.startswith("nfbv5:"):
            parsed = parse_numeric_model_ref(model_ref)
            if parsed is None or hole.get("source_brand") not in (None, parsed[0]):
                raise ValueError("EAR_Z_BRAND_IDENTITY_DRIFT")
            source_brand = parsed[0]
        else:
            source_brand = hole.get("source_brand") or legacy_brand
        if not isinstance(source_brand, str) or not source_brand:
            raise ValueError("EAR_Z_BRAND_SOURCE_MISSING")
        brands.add(source_brand)
    if len(brands) != 1:
        raise ValueError("EAR_Z_MIXED_BRANDS_REQUIRE_APPROVED_RULE")
    return brand_max_depth_mm(next(iter(brands)))


def resolve_receiving_tier_base_z_targets(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingTierBaseZTarget, ...]:
    """Evaluate the identical real-inner-door/real-base-skin formula per tier."""
    ears = resolve_receiving_tier_ear_mating_xy(snapshot)
    if not ears:
        return ()
    brand, config = _current_brand_config(snapshot)
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
    from .receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums

    physical = receiving_base_plate_values(snapshot)
    if physical is None:
        raise ValueError("EAR_Z_REAL_BASE_SOURCE_MISSING")
    upper = tuple(row for row in tuple(snapshot.get("inner_doors") or ())
                  if isinstance(row, Mapping)
                  and str(row.get("cell_key") or "").split(":")[-1] == "0"
                  and str(row.get("stable_id") or "").strip())
    if len(upper) != 1:
        raise ValueError("EAR_Z_UNIQUE_INNER_DOOR_REQUIRED")
    door_id = str(upper[0]["stable_id"])
    t = float(snapshot["t"])
    if not isfinite(t) or t <= 0:
        raise ValueError("EAR_Z_BASE_THICKNESS_INVALID")
    groups = {}
    for ear in ears:
        key = (ear.layer_index, ear.parent_base_id)
        groups.setdefault(key, []).append(ear)
    targets = []
    for (tier, part_id), pair in sorted(groups.items()):
        if len(pair) != 2 or {row.side for row in pair} != {"left", "right"}:
            raise ValueError("EAR_Z_SOURCE_PAIR_INCOMPLETE")
        depths = _tier_source_depths(brand, config, tier)
        if not depths:
            targets.append(ReceivingTierBaseZTarget(tier, part_id, None, None, (), False))
            continue
        local_physical = dict(physical)
        # A single NFB/depth in each tier uses the same original base source
        # folded skin, not the other tier's model or its placement Z.
        from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
        center_fold = (local_physical["receiving_bend_pattern"]
                       == RECEIVING_BASE_PATTERN_CENTER)
        inverted = bool(local_physical.get("receiving_center_brand_anchor_inverted"))
        if center_fold and not inverted and len(depths) == 1:
            # Two physical layers may each have a different shallow CSV depth.
            # They use their OWN CENTER blank/fold but share the one ear Z.
            maximum = committed_receiving_ear_brand_max_depth_mm(snapshot)
            if maximum - depths[0] > t + 1e-9:
                inverted = True
                local_physical["receiving_center_brand_anchor_inverted"] = True
                local_physical["receiving_nfb_depth_pair_mm"] = (maximum, depths[0])
        if inverted and (not center_fold or len(depths) != 1):
            raise ValueError("EAR_Z_CENTER_BRAND_ANCHOR_SOURCE_MISMATCH")
        if center_fold and len(depths) > 2:
            raise ValueError("EAR_Z_CENTER_ONLY_TWO_PHYSICAL_FACES")
        if inverted:
            # One same-depth shallow NFB tier: physical CENTER part's outer
            # tabs land at the fixed brand-max ear Z, not the NFB web Z.
            if local_physical.get("receiving_nfb_depth_pair_mm") is None:
                raise ValueError("EAR_Z_CENTER_BRAND_ANCHOR_PAIR_MISSING")
        elif center_fold and len(depths) == 2:
            # CENTER source owns both physical depth faces.
            local_physical["receiving_nfb_depth_pair_mm"] = depths
        else:
            # A flat web owns ONLY the deepest real mounting face;
            # shallower switches require separate parametric PAD bodies.
            local_physical["receiving_nfb_depth_pair_mm"] = None
        local_front, shallow = receiving_base_actual_local_nfb_skins(
            snapshot, local_physical,
        )
        world = resolve_receiving_nfb_world_skin_datums(
            snapshot, inner_door_id=door_id,
            reference_nfb_depth_mm=depths[0],
            secondary_nfb_depth_mm=(
                depths[1] if center_fold and len(depths) == 2 and not inverted else None
            ),
        )
        offset_z = world.base_nfb_face_world_z_mm - local_front
        back_z = offset_z + (shallow if inverted else local_front) - t
        if inverted:
            brand_pair = local_physical["receiving_nfb_depth_pair_mm"]
            predicted_support = world.base_nfb_face_world_z_mm - (
                float(brand_pair[0]) - float(brand_pair[1])
            )
            if (shallow is None or abs(offset_z+shallow-predicted_support)>1e-6):
                raise ValueError("EAR_Z_CENTER_BRAND_ANCHOR_SUPPORT_SKIN_MISMATCH")
        if (center_fold and len(depths) == 2 and not inverted and (shallow is None
                or world.shallow_nfb_face_world_z_mm is None
                or abs(offset_z + shallow - world.shallow_nfb_face_world_z_mm) > 1e-6)):
            raise ValueError("EAR_Z_SECOND_NFB_FACE_SOURCE_MISMATCH")
        if not all(isfinite(v) for v in (offset_z, back_z)):
            raise ValueError("EAR_Z_NONFINITE_SOURCE_SKIN")
        targets.append(ReceivingTierBaseZTarget(
            tier, part_id, offset_z, back_z, depths, True,
        ))
    return tuple(targets)


def resolve_receiving_tier_ear_contact_targets(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingTierEarContactTarget, ...]:
    """Use ONE brand-max-depth ear contact Z for all physical NFB layers."""
    rows = resolve_receiving_tier_ear_mating_xy(snapshot)
    if not rows:
        return ()
    base_z = {
        (row.layer_index, row.parent_base_id): row
        for row in resolve_receiving_tier_base_z_targets(snapshot)
    }
    if len({r.ear_id for r in rows}) != len(rows):
        raise ValueError("EAR_Z_DUPLICATE_PHYSICAL_EAR")
    max_depth = committed_receiving_ear_brand_max_depth_mm(snapshot)
    from .receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums
    upper = tuple(row for row in tuple(snapshot.get("inner_doors") or ())
                  if isinstance(row, Mapping)
                  and str(row.get("cell_key") or "").split(":")[-1] == "0"
                  and str(row.get("stable_id") or "").strip())
    if len(upper) != 1:
        raise ValueError("EAR_Z_UNIQUE_INNER_DOOR_REQUIRED")
    brand_anchor = resolve_receiving_nfb_world_skin_datums(
        snapshot, inner_door_id=str(upper[0]["stable_id"]),
        reference_nfb_depth_mm=max_depth,
        fixing_plate_thickness_mm=LARGE_EAR_MATERIAL_THICKNESS_MM,
    ).fixing_plate_contact_skin_world_z_mm
    if not isfinite(brand_anchor):
        raise ValueError("EAR_Z_BRAND_ANCHOR_NONFINITE")
    pitch_x = receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=float(snapshot["w"]),
        box_side_thickness_mm=float(snapshot["t"]),
    )
    inside_x = float(snapshot["w"])/2.0 - float(snapshot["t"])
    output = []
    for row in rows:
        side_sign = {"left": -1.0, "right": 1.0}.get(row.side)
        if (side_sign is None
                or abs(row.base_center_x_mm) > 1e-6
                or abs(row.selected_slot_column_x_mm-side_sign*pitch_x/2.0) > 1e-6
                or abs(row.side_inside_weld_x_mm-side_sign*inside_x) > 1e-6):
            raise ValueError("EAR_Z_SOURCE_MOUNT_X_DRIFT")
        target = base_z[(row.layer_index, row.parent_base_id)]
        # Keep the actual per-tier Base Plate skin as a separate witness.
        # It may not touch this invariant ear Z until a depth-compensation
        # profile/PAD is validated; never certify a floating joint.
        mating_verified = (
            target.physical_skin_z_resolved
            and target.base_back_skin_world_z_mm is not None
            and abs(target.base_back_skin_world_z_mm - brand_anchor) <= 1e-6
        )
        output.append(ReceivingTierEarContactTarget(
            ear_id=row.ear_id, parent_base_id=row.parent_base_id,
            layer_index=row.layer_index, side=row.side,
            fixing_hole_world_x_mm=row.selected_slot_column_x_mm,
            fixing_hole_world_y_mm=row.selected_slot_pair_world_y_mm,
            side_inside_weld_x_mm=row.side_inside_weld_x_mm,
            base_back_skin_world_z_mm=target.base_back_skin_world_z_mm,
            target_ear_contact_world_z_mm=brand_anchor,
            base_skin_z_source_verified=mating_verified,
        ))
    return tuple(output)
