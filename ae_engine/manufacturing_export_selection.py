"""Headless physical export selection and Receiving Bay coordinate authority.

GUI/CADSplit submit intents and source-resolved assembly pieces. Physical owner
mapping and world-to-local de-translation belong to WHD Engine alone.
"""
from dataclasses import replace
from collections.abc import Mapping

from .live_cabinet_family import resolve_live_cabinet_family
from .operator_settings_transactions import normalize_operator_settings_boolean


def normalize_operator_selected_export_flags(flags):
    """Decode exact operator DXF checkbox source before physical selection."""
    if not isinstance(flags, Mapping):
        raise TypeError("SELECTED_EXPORT_OPERATOR_FLAGS_REQUIRED")
    return {
        str(key): normalize_operator_settings_boolean(value)
        for key, value in flags.items()
    }




def logical_part_present(existing_parts, logical_key):
    """Engine-owned physical stable-ID projection for old logical GUI panels.

    A fixing plate does not imply an actual BasePlate; physical NFB tier 0/1
    and inner-door panel identities retain the original compatibility rules.
    This is presence evidence, never manufacturing/export certification.
    """
    existing = set(str(key) for key in (existing_parts or ()))
    key = str(logical_key or "")
    if key == "door":
        return ("door" in existing
                or any(item.startswith("door_c") for item in existing)
                or any(item.startswith("inner_door:") for item in existing))
    if key == "base_plate":
        return ("base_plate" in existing
                or any(item.startswith("base_plate_c") for item in existing)
                or any(item in {
                    "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
                } for item in existing))
    if key == "box_body":
        return "box_body" in existing or any(
            item.startswith("box_body:") for item in existing
        )
    return key in existing


def selected_project_export_flags(
    input_snapshot, existing_parts, workspace_parts, requested_flags,
    *, has_indicator_box=False,
):
    """Reconcile operator checkboxes with real available physical part IDs.

    Only a committed Receiving NFB source may augment the *old GUI presence
    mirror* with actual live tier bases or inner-door physical owners.
    This is a selection projection: each exporter must verify its current
    Family, source, actual FinalScene and certified DXF output independently.
    """
    if not isinstance(requested_flags, Mapping):
        raise TypeError("PROJECT_EXPORT_OPERATOR_FLAGS_REQUIRED")
    flags = normalize_operator_selected_export_flags(requested_flags)
    indicator_present = normalize_operator_settings_boolean(has_indicator_box)
    existing = set(existing_parts or ())
    real_parts = set(existing)
    if (isinstance(input_snapshot, Mapping)
            and resolve_live_cabinet_family(input_snapshot) == "受電箱"
            and input_snapshot.get("nfb_config_submitted") is True):
        real_parts.update(
            part for part in tuple(workspace_parts or ())
            if str(part).startswith(("base_plate:nfb_layer:", "inner_door:"))
        )
    result = {}
    for key in ("box_body", "head", "tail"):
        # Preserve the original main-screen physical-root checkbox contract.
        result[key] = bool(flags.get(key) and key in existing)
    for key in ("door", "base_plate"):
        result[key] = bool(
            flags.get(key) and logical_part_present(real_parts, key)
        )
    for key in ("indicator_box", "indicator_door"):
        result[key] = bool(
            flags.get(key) and key in existing and indicator_present
        )
    return result



from .contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from .receiving_layout import receiving_bay_assembly_offsets


def resolved_export_intention_key(part_key):
    """Map canonical physical source identity onto operator export intent."""
    key = str(part_key or "").strip()
    if key == "box_body" or key.startswith("box_body:"):
        return "box_body"
    if key in ("head", "tail"):
        return key
    if key == "door" or key.startswith("door_") or key.startswith("inner_door:"):
        return "door"
    if (key == "base_plate" or key.startswith("base_plate_")
            or key.startswith("base_plate:nfb_layer:")):
        return "base_plate"
    if key == "indicator_box" or key.startswith("indicator_box_"):
        return "indicator_box"
    if key == "indicator_door" or key.startswith("indicator_door_"):
        return "indicator_door"
    return None


def receiving_export_part_selected(part_key, flags):
    """A shared physical C divider belongs to the BoxBody AND inner-door frame.

    The canonical WHD Part/FinalScene remains unchanged. Selecting either the
    BoxBody or Door assembly must not silently drop this same verified blank.
    This selects existing physical inventory only, never fabricates a divider.
    """
    key = str(part_key or "").strip()
    validated_flags = normalize_operator_selected_export_flags(flags)
    if key.startswith("box_body:divider:"):
        return validated_flags.get("box_body", False) or validated_flags.get("door", False)
    return validated_flags.get(resolved_export_intention_key(key), False)


def select_resolved_export_geometry(resolved_geometry, flags):
    """Filter actual physical inventory without manufacturing a missing part."""
    validated_flags = normalize_operator_selected_export_flags(flags)
    selected = tuple(
        part for part in tuple(getattr(resolved_geometry, "parts", ()) or ())
        if receiving_export_part_selected(part.part_key, validated_flags)
    )
    return replace(resolved_geometry, parts=selected)


def resolve_receiving_bay_local_export_geometry(
    assembly_parts, saved_layout, *, set_index: int, bay_index: int,
) -> ResolvedManufacturingGeometry:
    """Remove exactly one certified Set/Bay XYZ translation before DXF.

    An incomplete or nonfinite world offset must never be truncated by zip()
    or carried as a fake local manufacturing placement. The source scene's
    original physical parts and render data remain unchanged.
    """
    from math import isfinite

    anchors = receiving_bay_assembly_offsets(saved_layout, set_index=set_index)
    if type(bay_index) is not int or not 0 <= bay_index < len(anchors):
        raise IndexError("RECEIVING_BAY_EXPORT_INDEX_INVALID")
    anchor = tuple(float(value) for value in anchors[bay_index])
    if len(anchor) != 3 or not all(isfinite(value) for value in anchor):
        raise ValueError("RECEIVING_BAY_EXPORT_WORLD_ANCHOR_INVALID")

    physical = []
    for part in tuple(assembly_parts or ()):
        placement = getattr(part, "placement", None)
        if placement == "standalone":
            raise ValueError("多連出圖禁止以單件預覽取代組合體實體")
        if not isinstance(placement, str) or not placement:
            raise ValueError("RECEIVING_BAY_EXPORT_PLACEMENT_INVALID")
        raw = getattr(part, "offset", None)
        if not isinstance(raw, (tuple, list)) or len(raw) != 3:
            raise ValueError("RECEIVING_BAY_EXPORT_WORLD_OFFSET_INVALID")
        try:
            if any(isinstance(value, bool) for value in raw):
                raise ValueError("boolean physical world offset")
            world = tuple(float(value) for value in raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("RECEIVING_BAY_EXPORT_WORLD_OFFSET_INVALID") from exc
        local = tuple(world[i] - anchor[i] for i in range(3))
        if not all(isfinite(value) for value in world + local):
            raise ValueError("RECEIVING_BAY_EXPORT_WORLD_OFFSET_INVALID")
        physical.append(ResolvedManufacturingPart(
            part_key=part.part_key,
            render_data=part.render_data,
            x_profile=part.x_profile,
            y_profile=part.y_profile,
            placement=placement,
            offset=local,
        ))
    return ResolvedManufacturingGeometry(parts=tuple(physical))
