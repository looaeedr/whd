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
