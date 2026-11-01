# -*- coding: utf-8 -*-
"""Engine-owned physical BasePlate 2D source identity and presentation geometry.

The operator GUI supplies current committed source, active part and the actual
canonical resolved geometry. No Tk, GUI state, guessed DXF, or release flag is
consulted. Stale CSV physical sheets fail closed instead of drawing an old plate.
"""
from __future__ import annotations
from collections.abc import Mapping


def project_receiving_base_plate_2d_snapshot(snapshot, resolved, *, active_part=""):
    """Select the exact canonical current Receiving NFB BasePlate for 2D."""
    if not isinstance(snapshot, Mapping):
        raise TypeError("receiving BasePlate snapshot must be a mapping")
    current = snapshot
    nfb = current.get("nfb_config")
    nfb_rows = nfb.get("holes") if isinstance(nfb, dict) else None
    numeric_source = (
        current.get("nfb_config_submitted") is True
        and isinstance(nfb_rows, (list, tuple))
        and any(isinstance(row, dict)
                and str(row.get("model_filename") or "").startswith("nfbv5:")
                for row in nfb_rows)
    )
    expected_source = None
    if numeric_source or not current.get("receiving_base_plate"):
        from .receiving_base_plate_config import receiving_base_plate_values
        expected_source = receiving_base_plate_values(current)
        if expected_source is None:
            raise ValueError(
                "受電箱底板尚未設定實體來源型式，不能顯示舊式通用底板"
            )
    part_keys = tuple(
        p.part_key for p in tuple(resolved.parts or ())
        if p.part_key == "base_plate"
        or p.part_key.startswith("base_plate:nfb_layer:")
    )
    tiers = tuple(
        key for key in part_keys
        if key.startswith("base_plate:nfb_layer:")
    )
    if current.get("nfb_config_submitted") is True:
        config = current.get("nfb_config")
        count = config.get("layer_count") if isinstance(config, dict) else None
        if count == 1 and "base_plate" in part_keys:
            # One submitted NFB tier owns the existing real Base Plate.
            # It must remain selectable in 2D even while DXF is blocked.
            chosen = "base_plate"
        elif count == 2 and tiers:
            active = str(active_part or "")
            chosen = active if active in tiers else tiers[0]
        else:
            raise ValueError(
                "已提交 NFB，但沒有對應的受電箱分層底板；不能回退舊式底板"
            )
    else:
        if "base_plate" not in part_keys:
            raise ValueError(
                "受電箱底板已選來源，但未產生實體底板；不能回退舊式底板"
            )
        chosen = "base_plate"
    physical = resolved.part(chosen).render_data
    # A delayed 2D refresh/cache must never resurrect a previous model's
    # flat/folded source sheet after this Bay's current numeric CSV changed.
    # This is a source-shape check, NOT a manufacturing release gate.
    if numeric_source and expected_source is not None:
        from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
        topology = getattr(physical, "unfolded_topology", None)
        actual_pattern = (getattr(physical, "metadata", None) or {}).get(
            "receiving_bend_pattern"
        )
        expected_pattern = expected_source["receiving_bend_pattern"]
        height = (float(expected_source["h"])
                  - float(expected_source["base_plate_shrink_top"])
                  - float(expected_source["base_plate_shrink_bottom"]))
        flat_width = (float(current["w"])
                      - float(expected_source["base_plate_shrink_left"])
                      - float(expected_source["base_plate_shrink_right"]))
        if (topology is None or actual_pattern != expected_pattern
                or abs(float(topology.height) - height) > 1e-6
                or (expected_pattern != RECEIVING_BASE_PATTERN_CENTER
                    and abs(float(topology.width) - flat_width) > 1e-6)):
            raise ValueError(
                "受電箱底板目前 CSV 來源與已載入 2D 實體板型不一致"
            )
    if (getattr(physical, "unfolded_topology", None) is None
            or getattr(physical, "material", None) is None):
        raise ValueError("受電箱專屬底板缺少實際展開幾何")
    bounds = tuple(float(v) for v in physical.material.bounds)
    minx, miny, maxx, maxy = bounds
    return {
        "render_data": physical,
        "bounds": bounds,
        "world_bounds": bounds,
        "box_rect": (minx, miny, maxx - minx, maxy - miny),
        "bend": 0.0,
        "receiving_physical_part_key": chosen,
        "receiving_tier_keys": tiers,
    }

def project_legacy_base_plate_2d_bounds(
    bounds, *, width, height, shrink_left, shrink_bottom, bend,
):
    """Legacy physical blank's matching operator box outline in flat XY."""
    minx, miny, maxx, maxy = (float(v) for v in bounds)
    box_l = -(float(shrink_left) - float(bend))
    box_b = -(float(shrink_bottom) - float(bend))
    w = float(width)
    h = float(height)
    world_bounds = (
        min(minx, box_l),
        min(miny, box_b),
        max(maxx, box_l + w),
        max(maxy, box_b + h),
    )
    return world_bounds, (float(box_l), float(box_b), w, h)
