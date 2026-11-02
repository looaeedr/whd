"""Engine-owned Receiving physical BasePlate Part Session fold source routing.

Activation and save must not read a stale generic editor buffer as physical
NFB BasePlate authority. These are read-only source projections, not a
manufacturing DXF approval or a replacement for canonical FinalScene.
"""
from __future__ import annotations

from .cabinet_types import policy as family_policy
from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles


def project_operator_part_activation_profiles(part_key, snapshot, stored, defaults):
    """Choose source-derived activated profiles or unchanged saved user input."""
    if (str(part_key) == "base_plate"
            and family_policy.canonical_family_name(snapshot) == "受電箱"):
        x = tuple((defaults or {}).get("X", ()) or ())
        y = tuple((defaults or {}).get("Y", ()) or ())
        if (x and y
                and all(str(row.get("phase6_key") or "").startswith("receiving_")
                        for row in (*x, *y))):
            return defaults, True
    if stored is None:
        return defaults, True
    return stored, False


def project_operator_receiving_base_plate_save_profiles(snapshot, part_key):
    """Only configured Receiving BasePlate uses canonical true physical folds.

    An unconfigured or non-Receiving part returns None so the original editor
    save path remains unchanged. Invalid physical source errors propagate.
    """
    if (str(part_key) != "base_plate"
            or family_policy.canonical_family_name(snapshot) != "受電箱"):
        return None
    return receiving_base_plate_3d_profiles(snapshot)

def can_skip_operator_receiving_part_save(
    snapshot, *, previous_active, save_outgoing, was_non_single,
    stored_profiles=None, live_profiles=None, live_dimensions=None,
    committed_dimensions=None,
):
    """Only unchanged, source-equivalent Receiving navigation is display-only.

    The editor may show stale projected BoxBody/EndCap values after a Set/Bay
    transaction. Refuse to suppress save for missing or malformed live values.
    Caller identity never controls physical-source ownership.
    """
    from collections.abc import Mapping

    if (not save_outgoing
            or not isinstance(snapshot, Mapping)
            or family_policy.canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode") != "set_bay"):
        return False
    part = str(previous_active or "")
    if was_non_single and part == "box_body":
        return True
    if part not in {"head", "tail"}:
        return False
    if not all(isinstance(value, Mapping) for value in (
        stored_profiles, live_profiles, live_dimensions, committed_dimensions,
    )):
        return False
    try:
        unchanged_fold = all(
            list(live_profiles.get(axis, ()) or ())
            == list(stored_profiles.get(axis, ()) or ())
            for axis in ("X", "Y")
        )
        unchanged_whd = all(
            abs(float(live_dimensions[axis]) - float(committed_dimensions[axis]))
            <= 1e-9 for axis in ("w", "h", "d")
        )
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        return False
    return unchanged_fold and unchanged_whd

