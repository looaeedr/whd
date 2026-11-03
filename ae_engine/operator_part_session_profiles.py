"""Engine-owned Receiving physical BasePlate Part Session fold source routing.

Activation and save must not read a stale generic editor buffer as physical
NFB BasePlate authority. These are read-only source projections, not a
manufacturing DXF approval or a replacement for canonical FinalScene.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

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


def project_operator_receiving_settings_live_dimensions(
    snapshot, live_dimensions, *, applying_settings=False,
):
    """Project the already-committed box source over stale Settings UI fields.

    This is a read-only source selection, never a manufacturing resize.
    Invalid present physical values must not fall back to cached UI dimensions.
    """
    from collections.abc import Mapping
    from .operator_settings_transactions import normalize_operator_source_dimension

    if (not applying_settings
            or family_policy.canonical_family_name(snapshot) != "受電箱"
            or not isinstance(live_dimensions, Mapping)
            or not all(axis in live_dimensions for axis in ("w", "h", "d"))):
        return None
    # Validate by the same Engine authority used on Settings commit, preserving
    # the original source values/types for the legacy operator controls.
    for axis in ("w", "h", "d"):
        normalize_operator_source_dimension(live_dimensions[axis], field=axis)
    return {axis: live_dimensions[axis] for axis in ("w", "h", "d")}


def project_operator_quantity_box_dimensions(snapshot):
    """Only a configured Receiving Quantity box overrides stale editor inputs.

    The existing Engine Quantity owner validates this confirmed physical source.
    A missing legacy common box leaves the original operator-input path intact;
    an explicitly malformed box never falls back to the stale GUI header.
    """
    from collections.abc import Mapping
    from .receiving_quantity_box import normalize_common_box

    if (not isinstance(snapshot, Mapping)
            or family_policy.canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode") != "quantity"
            or snapshot.get("receiving_quantity_box") is None):
        return None
    box = normalize_common_box(snapshot["receiving_quantity_box"])
    return {axis: box[axis] for axis in ("w", "h", "d")}


def project_operator_part_session_source_dimensions(snapshot, operator_dimensions):
    """Read the same positive, fractional outside W/H/D as the Engine request.

    A confirmed Receiving Quantity box is the sole size authority even when
    legacy Fold Designer header fields still show a previous Set/Bay size.
    """
    from collections.abc import Mapping
    from .operator_settings_transactions import normalize_operator_source_dimension

    quantity = project_operator_quantity_box_dimensions(snapshot)
    if quantity is not None:
        return quantity
    if not isinstance(operator_dimensions, Mapping):
        raise ValueError("Part Session 包外 W/H/D 來源資料缺失")
    return {
        axis: normalize_operator_source_dimension(
            operator_dimensions.get(axis), field=axis,
        )
        for axis in ("w", "h", "d")
    }


def operator_receiving_navigation_only_sync_change(previous, current) -> bool:
    """Prove only the selected existing part changed; unknown fields fail closed.

    Compare complete payloads, including removed keys, rather than trusting the
    sender's delta or geometry cache. Transport metadata is not product state.
    """
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return False
    old, new = deepcopy(dict(previous)), deepcopy(dict(current))
    changed = False
    for payload in (old, new):
        # This optimization is certified only for Receiving multi-Bay
        # navigation. Other families (e.g. vault) must publish their derived
        # EndCap relief during the normal part activation transition; merely
        # changing active_part is not display-only for those factories.
        if (payload.get("model") not in ("受電箱", "RECEIVING")
                or payload.get("active_mode") != "set_bay"):
            return False
        workspace = payload.get("workspace")
        if not isinstance(workspace, dict):
            return False
        active = payload.get("active_part")
        if (not active or workspace.get("active_part") != active
                or active not in tuple(workspace.get("existing_parts") or ())):
            return False
    changed = old["active_part"] != new["active_part"]
    for payload in (old, new):
        for name in ("origin", "revision", "fingerprint", "transaction_id", "delta", "active_part"):
            payload.pop(name, None)
        payload["workspace"].pop("active_part", None)
    return changed and old == new


