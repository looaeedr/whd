"""Stateless part-panel presentation helpers.

This module projects authoritative application/manufacturing state into operator
navigation presentation. It does not own physical identity, geometry, visibility
masks, persistence, or application state.
"""


def _phase6_logical_part_present(existing_parts, logical_key):
    """Project dynamic physical stable IDs into the legacy top-level UI groups.

        The physical IDs remain authoritative; this helper only answers whether a
        logical main-GUI group should be visible.
        """
    existing = set(str(key) for key in (existing_parts or ()))
    key = str(logical_key or "")
    if key == "door":
        return "door" in existing or any(item.startswith("door_c") for item in existing)
    if key == "base_plate":
        return "base_plate" in existing or any(item.startswith("base_plate_c") for item in existing)
    if key == "box_body":
        return "box_body" in existing or any(item.startswith("box_body:") for item in existing)
    return key in existing
