# -*- coding: utf-8 -*-
"""#1502: independent *actual FinalScene blanks* for NFB tiers in upper Door.

Each tier's NFB opening group determines Base Plate Y; physical X stays 0.
A tier's source physical plate uses a NEW BasePlatePartSpec/PartRenderData and
its own unfolded topology identity. It is never a translated reference to
another layer's PartRenderData or an invented different base-plate editor.

The source BEND/CUTTING blank is real; screw holes, side-sheet welded fixing
plate skins/MARKING and per-tier depth proof are NOT yet source-certified.
Therefore generated part metadata is explicitly manufacturing-blocked.
"""
from __future__ import annotations

from dataclasses import replace
from collections.abc import Mapping


PREVIEW_STATUS = "NFB_TIER_BASE_EAR_AND_HOLES_UNVERIFIED"


def expand_receiving_nfb_layer_parts(snapshot, assembly_parts):
    """Replace a single root Base Plate with 2 independent manufactured blanks.

    A completed committed two-tier configuration is mandatory. One NFB tier
    retains the existing (already physically Z-mated) single Base Plate path.
    Root Base Plate's legacy Z is preview-only here until a layer-specific
    NFB depth/skin result is approved: never advertise that Z as certified.
    """
    parts = tuple(assembly_parts or ())
    if not isinstance(snapshot, Mapping) or str(snapshot.get("model") or "") not in (
        "受電箱", "RECEIVING"
    ):
        return parts
    # Assembly may rebuild during a Receiving mode/Set/Bay transition.
    # Only a FULLY SUBMITTED two-tier configuration authorizes the new
    # manufacturing source path. Do not interrogate stale Set/Bay selection
    # for legacy, draft or single-tier snapshots; those legitimately exist
    # during first entering/cancelling quantity and multi-Bay UI.
    if snapshot.get("nfb_config_submitted") is not True:
        return parts
    active_config = snapshot.get("nfb_config")
    if not isinstance(active_config, Mapping) or active_config.get("layer_count") != 2:
        return parts
    from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers

    upper = [
        row for row in tuple(snapshot.get("inner_doors") or ())
        if isinstance(row, Mapping)
        and str(row.get("cell_key") or "").split(":")[-1] == "0"
        and str(row.get("stable_id") or "").strip()
    ]
    if len(upper) != 1:
        # No unique source owner; do not manufacture invented second plates.
        return parts
    try:
        centers = receiving_nfb_layer_centers(snapshot, str(upper[0]["stable_id"]))
    except ValueError as exc:
        # Identity drift is an ordinary transient state *during UI switching*:
        # do not crash an unrelated cabinet mode or make false plates. Once
        # the active source is committed and identities match, this source
        # creates the two plates; export still has its independent hard gate.
        if str(exc) in {
            "RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT",
            "RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT",
            "RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT",
        }:
            return parts
        raise
    if len(centers) <= 1:
        return parts
    if len(centers) != 2 or [x.layer_index for x in centers] != [0, 1]:
        raise ValueError("RECEIVING_TWO_TIER_PHYSICAL_OWNERS_MISSING")
    root = next((part for part in parts if part.part_key == "base_plate"), None)
    if root is None:
        raise ValueError("RECEIVING_TWO_TIER_SOURCE_BASE_PLATE_MISSING")
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
    from .contracts import BasePlatePartSpec
    from .manufacturing_scene_orchestration import build_part_render_data
    from phase6_final_scene_contracts import AssemblyScenePart

    values = receiving_base_plate_values(snapshot)
    if values is None:
        raise ValueError("RECEIVING_TWO_TIER_BASE_VARIANT_UNCONFIGURED")
    # We cannot claim that a two-tier pair's source depth is the same as
    # a historical one-tier source: holes and PAD must be resolved per layer.
    # No model-depth fallback grants manufacturing permission.
    profiles = receiving_base_plate_3d_profiles(snapshot, values)
    if profiles is None:
        raise ValueError("RECEIVING_TWO_TIER_BASE_PROFILE_UNAVAILABLE")
    # #1503: each tier uses the SAME NFB source depth / actual inner-door
    # and original Base Plate physical-face Z rule. Different tier count
    # only means independent applications of that one solver.
    from .receiving_tier_ear_z_targets import resolve_receiving_tier_base_z_targets
    z_targets = {
        x.layer_index: x for x in resolve_receiving_tier_base_z_targets(snapshot)
    }
    if set(z_targets) != {0, 1}:
        raise ValueError("RECEIVING_NFB_TIER_DEPTH_TARGET_IDENTITY_MISSING")
    generated = []
    for center in centers:
        identity = center.layer_part_id
        depth_target = z_targets[center.layer_index]
        if depth_target.parent_base_id != identity:
            raise ValueError("RECEIVING_NFB_TIER_Z_TARGET_OWNER_DRIFT")
        # Exact same source-physical Base Plate variant is used for the skin
        # solve, FinalScene material and fold profiles in EVERY NFB tier.
        tier_pair = (
            tuple(depth_target.source_depths_mm)
            if len(depth_target.source_depths_mm) == 2 else None
        )
        tier_values = {**values, "receiving_nfb_depth_pair_mm": tier_pair}
        tier_profiles = receiving_base_plate_3d_profiles(snapshot, tier_values)
        if tier_profiles is None:
            raise ValueError("RECEIVING_NFB_TIER_SOURCE_PROFILE_MISSING")
        spec = BasePlatePartSpec(
            width=float(snapshot["w"]),
            height=float(values["h"]),
            thickness=float(snapshot["t"]),
            shrink_top=float(values["base_plate_shrink_top"]),
            shrink_bottom=float(values["base_plate_shrink_bottom"]),
            shrink_left=float(values["base_plate_shrink_left"]),
            shrink_right=float(values["base_plate_shrink_right"]),
            bend=float(values["base_plate_bend"]),
            model_name="受電箱",
            receiving_bend_pattern=str(values["receiving_bend_pattern"]),
            receiving_nfb_depth_pair_mm=tier_pair,
            physical_id=identity,
        )
        actual = build_part_render_data(spec)
        topology = actual.unfolded_topology
        if topology is None or topology.piece_id != identity:
            raise ValueError("RECEIVING_NFB_TIER_FINAL_SCENE_IDENTITY_DRIFT")
        actual = replace(
            actual,
            metadata={
                **dict(actual.metadata),
                "stable_id": identity,
                "nfb_layer_index": center.layer_index,
                "nfb_layer_manufacturing_status": PREVIEW_STATUS,
                "manufacturing_ready": False,
            },
        )
        # NFB horizontal X is a SCREW-HOLE position, never the Base Plate
        # assembly X. The plate and its +/-335-mm ear fixing columns remain
        # fixed at the cabinet X centre for every NFB layer.
        # Missing model depth never becomes an invented installation Z; old
        # preview is retained only as a non-manufacturing visualization.
        z = (float(depth_target.world_offset_z_mm)
             if depth_target.physical_skin_z_resolved
             else float(root.offset[2]))
        actual = replace(actual, metadata={
            **dict(actual.metadata),
            "nfb_tier_depth_source_mm": depth_target.source_depths_mm,
            "nfb_tier_real_skin_z_resolved": depth_target.physical_skin_z_resolved,
            "nfb_tier_base_back_skin_world_z_mm":
                depth_target.base_back_skin_world_z_mm,
        })
        generated.append(AssemblyScenePart(
            part_key=identity,
            render_data=actual,
            x_profile=tuple(dict(s) for s in tier_profiles["X"]),
            y_profile=tuple(dict(s) for s in tier_profiles["Y"]),
            placement="offset",
            offset=(0.0, float(center.world_y_mm), z),
        ))
    if len({p.part_key for p in generated}) != 2:
        raise ValueError("RECEIVING_NFB_TIER_PART_DUPLICATE")
    return tuple(p for p in parts if p.part_key != "base_plate") + tuple(generated)
