"""Headless physical export selection and Receiving Bay coordinate authority.

GUI/CADSplit submit intents and source-resolved assembly pieces. Physical owner
mapping and world-to-local de-translation belong to WHD Engine alone.
"""
from dataclasses import replace

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
