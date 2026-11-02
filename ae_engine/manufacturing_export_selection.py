"""Headless physical export selection and Receiving Bay coordinate authority.

GUI/CADSplit submit intents and source-resolved assembly pieces. Physical owner
mapping and world-to-local de-translation belong to WHD Engine alone.
"""
from dataclasses import replace
from collections.abc import Mapping

from .live_cabinet_family import resolve_live_cabinet_family


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
        result[key] = bool(requested_flags.get(key) and key in existing)
    for key in ("door", "base_plate"):
        result[key] = bool(
            requested_flags.get(key) and logical_part_present(real_parts, key)
        )
    for key in ("indicator_box", "indicator_door"):
        result[key] = bool(
            requested_flags.get(key) and key in existing and has_indicator_box
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


def select_resolved_export_geometry(resolved_geometry, flags):
    """Filter actual physical inventory without manufacturing a missing part."""
    selected = tuple(
        part for part in tuple(getattr(resolved_geometry, "parts", ()) or ())
        if bool(flags.get(resolved_export_intention_key(part.part_key), False))
    )
    return replace(resolved_geometry, parts=selected)


def resolve_receiving_bay_local_export_geometry(
    assembly_parts, saved_layout, *, set_index: int, bay_index: int,
) -> ResolvedManufacturingGeometry:
    """Remove only the canonical Set/Bay assembly translation before DXF."""
    anchor = receiving_bay_assembly_offsets(
        saved_layout, set_index=set_index,
    )[bay_index]
    physical = tuple(
        ResolvedManufacturingPart(
            part_key=p.part_key,
            render_data=p.render_data,
            x_profile=p.x_profile,
            y_profile=p.y_profile,
            placement=p.placement,
            offset=tuple(float(x) - float(y) for x, y in zip(p.offset, anchor)),
        )
        for p in tuple(assembly_parts or ())
    )
    if any(part.placement == "standalone" for part in physical):
        raise ValueError("多連出圖禁止以單件預覽取代組合體實體")
    return ResolvedManufacturingGeometry(parts=physical)
