"""Truly shared, stateless physical-part panel presentation helpers."""


def logical_part_present(existing_parts, logical_key):
    """Project authoritative physical stable IDs into logical panel groups."""
    existing = set(str(key) for key in (existing_parts or ()))
    key = str(logical_key or "")
    if key == "door":
        return "door" in existing or any(item.startswith("door_c") for item in existing)
    if key == "base_plate":
        return "base_plate" in existing or any(item.startswith("base_plate_c") for item in existing)
    if key == "box_body":
        return "box_body" in existing or any(item.startswith("box_body:") for item in existing)
    return key in existing
