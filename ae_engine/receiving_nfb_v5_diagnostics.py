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
from .receiving_nfb_numeric_catalog import read_numeric_specs
from .receiving_nfb_persistence import normalize_nfb_saved_fields


def current_v5_nfb_diagnostics(
    saved_bay: Mapping[str, object], *,
    set_id: str, bay_id: str, version_id: str | None,
    dependent_part_ids: Sequence[str] = (),
    unaffected_part_ids: Sequence[str] = (),
    missing_required_physical_roles: Sequence[str] = (),
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

    missing_roles = tuple(missing_required_physical_roles)
    if (len(set(missing_roles)) != len(missing_roles)
            or any(role not in ("INNER_DOOR", "BASE_PLATE")
                   for role in missing_roles)):
        raise ValueError("NFB missing physical roles must be source-derived")
    physical_reasons = tuple(
        f"NFB_REAL_{role}_SOURCE_MISSING" for role in missing_roles
    )
    layer_count = config.get("layer_count")
    rows: list[dict[str, object]] = []
    csv_by_brand: dict[str, dict[str, object] | None] = {}
    slot_owners: set[tuple[int, int]] = set()
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
        if type(hole.get("layer_count", layer_count)) is not int or (
            hole.get("layer_count", layer_count) != layer_count
        ):
            errors.append("NFB_UNIT_LAYER_COUNT_MISMATCH")
        if (type(layer) is int and 0 <= layer < 2
                and type(slot) is int and slot >= 0):
            owner = (layer, slot)
            if owner in slot_owners:
                errors.append("NFB_DUPLICATE_LAYER_UNIT_OWNER")
            slot_owners.add(owner)
        if identity is None:
            errors.append("NFB_CURRENT_CSV_LEGACY_MIXED_SOURCE")
        else:
            brand, model = identity
            if hole.get("source_brand") not in (None, brand):
                errors.append("NFB_CSV_BRAND_SOURCE_MISMATCH")
            if brand not in csv_by_brand:
                try:
                    csv_by_brand[brand] = {
                        item.model: item for item in read_numeric_specs(brand)
                    }
                except (OSError, ValueError, UnicodeError):
                    csv_by_brand[brand] = None
            candidates = csv_by_brand[brand]
            if candidates is None:
                errors.append("NFB_CSV_SOURCE_UNAVAILABLE_OR_INVALID")
            else:
                spec = candidates.get(model)
                if spec is None:
                    errors.append("NFB_CSV_MODEL_MISSING")
                elif not spec.dimensionally_complete:
                    errors.append("NFB_CSV_REQUIRED_DIMENSIONS_MISSING:" +
                                  ",".join(spec.missing_fields))
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

    good = not physical_reasons and all(not row["reasons"] for row in rows)
    state = "CONFIGURED" if good else "DRAFT"
    common = ("NFB_CURRENT_CSV_PHYSICAL_CUTTING_RECHECK_REQUIRED",)
    return {
        "status": "CSV_V5_SCOPED_DIAGNOSTIC",
        "set_id": set_id, "bay_id": bay_id, "version_id": version_id,
        "nfb_config_submitted": True, "derived_state": state,
        "unit_rows": tuple(rows),
        "part_rows": tuple(
            {"part_id": x, "nfb_affected": True, "status": "RECHECK_ONLY" if good else "BLOCKED",
             "reasons": common if good else tuple(dict.fromkeys((
                 *physical_reasons,
                 *(reason for row in rows for reason in row["reasons"]),
             )))}
            for x in dependencies
        ) + tuple(
            {"part_id": x, "nfb_affected": False, "status": "NFB_UNAFFECTED",
             "reasons": ()} for x in unaffected
        ),
        "actual_export_count": None, "rows": (),
        "unresolved_dependencies": tuple((*physical_reasons, *common)),
        "whole_ready": False, "manufacturing_ready": False,
        "reason": "目前只核對數值 CSV 與已提交逐顆資料，實體板件須在出圖時重驗",
    }


def actual_unrelated_nfb_scene_parts(
    physical_parts: Sequence[object], *, dependent_part_ids: Sequence[str],
) -> tuple[str, ...]:
    """Identify genuinely existing, source-rendered, NFB-independent sheets.

    Never infer part IDs from nominal W/H/D, raw UI flags, or an old cached
    NFB receipt. The exact Bay FinalScene is the physical existence witness.
    Box sides are intentionally excluded: their EAR marking may depend on
    the installed NFB base. This is a *NFB dependency* classification only;
    it does NOT grant fabrication/export readiness to the unrelated sheets.
    """
    eligible = frozenset({
        "head", "tail", "door", "box_body:back_panel",
    })
    dependent = frozenset(dependent_part_ids)
    if any(not isinstance(x, str) or not x.strip() for x in dependent):
        raise ValueError("NFB actual dependencies require real part IDs")
    found = set()
    unaffected = []
    for physical in tuple(physical_parts):
        key = getattr(physical, "part_key", None)
        render = getattr(physical, "render_data", None)
        if not isinstance(key, str) or not key.strip():
            raise ValueError("NFB actual FinalScene part identity missing")
        if key in found:
            raise ValueError("NFB actual FinalScene duplicate physical owner")
        found.add(key)
        if (key in eligible and key not in dependent
                and getattr(render, "scene", None) is not None):
            unaffected.append(key)
    return tuple(unaffected)
