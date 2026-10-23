# -*- coding: utf-8 -*-
"""#1504 AC-09/24: live per-unit CURRENT numeric CSV NFB diagnostics.

This is a READ-ONLY projection of the persisted NFBConfig and the *current*
brand CSV. It does not replace the normal canonical FinalScene/CHECK/Q gates,
does not serialize DRAFT/CONFIGURED, and never grants manufacturing READY.
The old DXF inventory/certification path continues to serve legacy projects.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_nfb_numeric_catalog import model_spec
from .receiving_nfb_persistence import normalize_nfb_saved_fields


def current_v5_nfb_diagnostics(
    saved_bay: Mapping[str, object], *,
    set_id: str, bay_id: str, version_id: str | None,
    dependent_part_ids: Sequence[str] = (),
    unaffected_part_ids: Sequence[str] = (),
) -> dict[str, object] | None:
    """Inspect each saved hole; return None only for a wholly legacy NFB config.

    Any mixed current/legacy source is reported as invalid and never silently
    drops the legacy row. Actual physical part IDs must be supplied by a
    trusted scene/PartSpec caller; this function will not fabricate them.
    """
    if not isinstance(saved_bay, Mapping) or saved_bay.get("nfb_config_submitted") is not True:
        return None
    if not all(isinstance(x, str) and x.strip() for x in (set_id, bay_id)):
        raise ValueError("NFB scoped status requires actual Set/Bay IDs")
    if version_id is not None and not isinstance(version_id, str):
        raise ValueError("NFB scoped status version ID invalid")
    saved = normalize_nfb_saved_fields(saved_bay)
    config = saved["nfb_config"]
    holes = config["holes"]
    parsed = [parse_numeric_model_ref(h["model_filename"]) for h in holes]
    if not any(parsed):
        return None
    from .receiving_nfb_model_identity import PREFIX
    if any(parsed[i] is None and str(holes[i]["model_filename"]).startswith(PREFIX)
           for i in range(len(holes))):
        raise ValueError("NFB saved numeric source identity invalid")

    dependencies = tuple(dependent_part_ids)
    unaffected = tuple(unaffected_part_ids)
    if (any(not isinstance(x, str) or not x.strip() for x in (*dependencies, *unaffected))
            or len(set((*dependencies, *unaffected))) != len(dependencies) + len(unaffected)):
        raise ValueError("NFB actual part IDs missing, duplicate or overlapping")

    layer_count = config.get("layer_count")
    rows: list[dict[str, object]] = []
    csv_cache: dict[tuple[str, str], tuple[str, ...]] = {}
    for index, hole in enumerate(holes):
        identity = parsed[index]
        layer = hole.get("layer_index", 0 if layer_count == 1 else None)
        slot = hole.get("slot_index")
        errors = []
        if (type(layer_count) is not int or layer_count not in (1, 2)
                or type(layer) is not int or not 0 <= layer < layer_count):
            errors.append("NFB_LAYER_OWNER_INVALID")
        if type(slot) is not int or slot < 0:
            errors.append("NFB_UNIT_SLOT_INVALID")
        if identity is None:
            errors.append("NFB_CURRENT_CSV_LEGACY_MIXED_SOURCE")
        else:
            brand, model = identity
            if hole.get("source_brand", brand) != brand:
                errors.append("NFB_CSV_BRAND_SOURCE_MISMATCH")
            key = (brand, model)
            if key not in csv_cache:
                try:
                    spec = model_spec(brand, model)
                    if spec is None:
                        csv_cache[key] = ("NFB_CSV_MODEL_MISSING",)
                    elif not spec.dimensionally_complete:
                        csv_cache[key] = ("NFB_CSV_REQUIRED_DIMENSIONS_MISSING:" +
                                          ",".join(spec.missing_fields),)
                    else:
                        csv_cache[key] = ()
                except (OSError, ValueError, UnicodeError):
                    csv_cache[key] = ("NFB_CSV_SOURCE_UNAVAILABLE_OR_INVALID",)
            errors.extend(csv_cache[key])
        if hole.get("manual_x_state") != "CONFIRMED":
            errors.append("NFB_WORLD_X_RECONFIRM_REQUIRED")
        # A saved CONFIRMED coordinate still needs live CSV/scene/bounds
        # verification before *any* manufactured cutting is approved.
        rows.append({
            "physical_hole_id": hole["physical_hole_id"],
            "layer_index": layer,
            "slot_index": slot,
            "model_filename": hole["model_filename"],
            "source_status": "SOURCE_PRESENT_RECHECK_ONLY" if not errors else "UNVERIFIED",
            "reasons": tuple(dict.fromkeys(errors)),
            "manufacturing_verified": False,
        })

    good = all(not row["reasons"] for row in rows)
    state = "CONFIGURED" if good else "DRAFT"
    common = ("NFB_CURRENT_CSV_PHYSICAL_CUTTING_RECHECK_REQUIRED",)
    return {
        "status": "CSV_V5_SCOPED_DIAGNOSTIC",
        "set_id": set_id, "bay_id": bay_id, "version_id": version_id,
        "nfb_config_submitted": True, "derived_state": state,
        "unit_rows": tuple(rows),
        "part_rows": tuple(
            {"part_id": x, "nfb_affected": True, "status": "RECHECK_ONLY" if good else "BLOCKED",
             "reasons": common if good else tuple(dict.fromkeys(
                 reason for row in rows for reason in row["reasons"]))}
            for x in dependencies
        ) + tuple(
            {"part_id": x, "nfb_affected": False, "status": "NFB_UNAFFECTED",
             "reasons": ()} for x in unaffected
        ),
        "actual_export_count": None, "rows": (),
        "unresolved_dependencies": common,
        "whole_ready": False, "manufacturing_ready": False,
        "reason": "目前只核對數值 CSV 與已提交逐顆資料，實體板件須在出圖時重驗",
    }
