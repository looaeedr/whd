# -*- coding: utf-8 -*-
"""#1502: current committed CSV/NFBConfig feeds ONE normal WHD FinalScene.

Do not create a parallel CSV button, preview cache or DXF-only geometry.
The ordinary Phase6 resolver consumes this projection for both 2D and 3D.
Only an actually confirmed world-X datum may move NFB screw holes; no
guessing an X or hiding existing physical blanks while it is unconfirmed.
"""
from __future__ import annotations

from collections.abc import Mapping

from .contracts import BasePlatePartSpec
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole,
    trial_configured_nfb_v5_inner_door_render_data,
)
from .receiving_nfb_v5_live_base_preview import (
    project_csv_v5_onto_existing_assembly_parts,
)
from .receiving_nfb_model_identity import parse_numeric_model_ref


def _submitted_csv_holes(snapshot):
    """Get canonical selected Bay's full config; no separate editor authority."""
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        return ()
    config = snapshot.get("nfb_config")
    if not isinstance(config, Mapping):
        return ()
    rows = config.get("holes")
    if not isinstance(rows, (tuple, list)) or not rows:
        return ()
    # Old projects with DXF references still use their own existing path;
    # a *mixed* CSV/DXF configuration cannot silently drop physical holes.
    parsed = tuple(
        parse_numeric_model_ref(row.get("model_filename"))
        if isinstance(row, Mapping) else None for row in rows
    )
    if not any(parsed):
        return ()
    if any(p is None for p in parsed):
        raise ValueError("NFB_COMMITTED_CSV_MIXED_UNRESOLVED_SOURCE")
    count = config.get("layer_count")
    if type(count) is not int or count not in (1, 2):
        raise ValueError("NFB_COMMITTED_CSV_INVALID_LAYER_COUNT")
    # Edited/committed UI CSV initially stores UNVERIFIED_BASIS X. Do not
    # fabricate or cut holes at zero before operator's physical X exists.
    if any(row.get("manual_x_state") != "CONFIRMED"
           or row.get("manual_x_mm") is None for row in rows):
        return ()
    from .receiving_nfb_persistence import normalize_nfb_config
    from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
    from .cabinet_types.policy import derive_inner_door_panels

    validated = normalize_nfb_config(config)
    layout = snapshot.get("receiving_layout")
    selector = snapshot.get("_receiving_runtime_selection")
    if not isinstance(layout, Mapping) or not isinstance(selector, Mapping):
        raise ValueError("NFB_COMMITTED_CSV_ACTIVE_SET_BAY_REQUIRED")
    sets = layout.get("sets")
    si, bi = selector.get("set_index"), selector.get("bay_index")
    if (not isinstance(sets, (list, tuple))
            or type(si) is not int or not 0 <= si < len(sets)
            or sets[si].get("stable_id") != selector.get("set_id")):
        raise ValueError("NFB_COMMITTED_CSV_SET_IDENTITY_DRIFT")
    bays = sets[si].get("bays")
    if (not isinstance(bays, (list, tuple))
            or type(bi) is not int or not 0 <= bi < len(bays)
            or bays[bi].get("stable_id") != selector.get("bay_id")
            or bays[bi].get("nfb_config_submitted") is not True
            or bays[bi].get("nfb_config") != config):
        raise ValueError("NFB_COMMITTED_CSV_BAY_IDENTITY_DRIFT")
    upper = tuple(p for p in derive_inner_door_panels(snapshot)
                  if str(p.cell_key).split(":")[-1] == "0")
    if len(upper) != 1:
        raise ValueError("NFB_COMMITTED_CSV_UNIQUE_UPPER_DOOR_REQUIRED")
    door_id = upper[0].inner_door_id
    centers = receiving_nfb_layer_centers(snapshot, door_id)
    # Only the physical tiers actually holding NFBs get a base/screw set.
    owners = {p.layer_index for p in centers}
    if count == 2 and owners != {0, 1}:
        return ()
    if count == 1 and owners != {0}:
        return ()
    holes = []
    seen = set()
    for row, model in zip(validated["holes"], parsed):
        tier = row.get("layer_index", 0 if count == 1 else None)
        brand = row.get("source_brand")
        hole_id = row.get("physical_hole_id")
        if (tier not in owners or brand != model[0]
                or hole_id in seen):
            raise ValueError("NFB_COMMITTED_CSV_OWNER_OR_MODEL_MISMATCH")
        seen.add(hole_id)
        holes.append(NfbV5ConfiguredInnerDoorHole(
            physical_hole_id=hole_id,
            brand=brand,
            model_ref=row["model_filename"],
            world_x_mm=float(row["manual_x_mm"]),
            layer_count=count,
            slot_index=tier,
            rotation_deg=row.get("rotation_deg", 0),
        ))
    return door_id, tuple(holes)


def _existing_source_specs(snapshot, holes):
    count = holes[0].layer_count
    if count == 2:
        from .receiving_nfb_layer_physical_parts import (
            source_receiving_nfb_tier_base_specs,
        )
        return source_receiving_nfb_tier_base_specs(snapshot)
    physical = receiving_base_plate_values(snapshot)
    if physical is None:
        raise ValueError("NFB_COMMITTED_CSV_REAL_BASE_SOURCE_MISSING")
    spec = BasePlatePartSpec(
        width=float(snapshot["w"]), height=float(physical["h"]),
        thickness=float(snapshot["t"]),
        shrink_top=float(physical["base_plate_shrink_top"]),
        shrink_bottom=float(physical["base_plate_shrink_bottom"]),
        shrink_left=float(physical["base_plate_shrink_left"]),
        shrink_right=float(physical["base_plate_shrink_right"]),
        bend=float(physical["base_plate_bend"]),
        model_name="受電箱",
        receiving_bend_pattern=physical["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=physical["receiving_nfb_depth_pair_mm"],
        physical_id="base_plate",
    )
    return {0: spec}


def apply_committed_csv_v5_to_canonical_parts(snapshot, assembly_parts):
    """Read current committed CSV once per physical resolve, update same parts.

    Not an extra renderer or manufacturing approval. Incomplete WORLD-X keeps
    the existing editable physical scene (instead of inventing a screw datum).
    All complete and provenance-valid CSV records cut into actual FinalScene.
    """
    parts = tuple(assembly_parts)
    sourced = _submitted_csv_holes(snapshot)
    if not sourced:
        return parts
    inner_door_id, holes = sourced
    if not any(part.part_key.startswith("base_plate") for part in parts):
        # No original material sheet exists. A missing Base Plate may not be
        # manufactured by silently reusing an unrelated door or box-body.
        raise ValueError("NFB_COMMITTED_CSV_REAL_BASE_PART_MISSING")
    proof = trial_configured_nfb_v5_inner_door_render_data(
        snapshot, inner_door_id, holes=holes,
    )
    return project_csv_v5_onto_existing_assembly_parts(
        snapshot, inner_door_id, door=proof,
        configured_holes=holes,
        base_specs=_existing_source_specs(snapshot, holes),
        assembly_parts=parts,
    )
