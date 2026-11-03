# -*- coding: utf-8 -*-
"""#2517 Receiving physical Bay preview provenance: engine-owned reuse decisions.

The projected key is ONLY for bounded operator previews; it is NEVER a saved
layout, manufacturing request, physical geometry substitute, or export proof.
Unrecognized cross-Bay dependencies force complete fingerprint invalidation.
Pure translation planning cannot modify any existing FinalScene/PartSpec.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .custom_part_catalog import is_custom_part

from .cabinet_types.policy import canonical_family_name

@dataclass(frozen=True)
class ReceivingBayPreviewReusePolicy:
    """Read-only physical preview provenance flags; never DXF certification."""

    receiving_set_bay: bool
    requires_live_custom_catalog: bool
    allow_upstream_translation: bool
    allow_suffix_topology_reuse: bool


def plan_receiving_bay_preview_reuse_policy(
    snapshot, *, bay_index, candidate=False, available_parts=(),
) -> ReceivingBayPreviewReusePolicy:
    """Single Engine decision for committed Bay preview cache dependencies.

    The caller owns only LRU retention and GUI rendering, never physical
    CustomPart identity, upstream translation or source dependency policy.
    The fingerprint projector independently checks Joint topology and values.
    """
    live_custom = any(is_custom_part(key) for key in tuple(available_parts or ()))
    receiving = (
        isinstance(snapshot, Mapping)
        and canonical_family_name(snapshot) == "受電箱"
        and snapshot.get("active_mode", "set_bay") == "set_bay"
    )
    state = snapshot if receiving else {}
    physical_dependencies = bool(
        live_custom or state.get("assembly_joints")
        or state.get("custom_parts") or state.get("joint_relief_state")
    )
    allow_translation = bool(
        receiving and not candidate and type(bay_index) is int
        and bay_index >= 2 and not physical_dependencies
    )
    return ReceivingBayPreviewReusePolicy(
        receiving_set_bay=bool(receiving),
        requires_live_custom_catalog=live_custom,
        allow_upstream_translation=allow_translation,
        allow_suffix_topology_reuse=bool(receiving and not candidate),
    )


def project_receiving_bay_preview_face_features_key(face_features):
    """Ignore only transient Joint locks which the real per-Bay solver replaces.

    receiving_bay_joint_face_features removes the source_type below from
    existing BoxBody faces and reconstructs the selected Bay's locks using
    receiving_layout and the actual W/H/D/T/FW. Both remain in the preview
    fingerprint. Authored faces and all non-BoxBody features still invalidate.
    Never mutate the Designer workspace or the manufacturing input.
    """
    if not isinstance(face_features, dict):
        return face_features
    box_faces = face_features.get("box_body")
    if not isinstance(box_faces, dict):
        return face_features
    if not all(isinstance(values, (list, tuple))
               for values in box_faces.values()):
        return face_features  # unknown schema: preserve full key
    retained = {
        face: remaining
        for face, values in box_faces.items()
        if (remaining := [feature for feature in values
                         if getattr(feature, "source_type", "") !=
                         "receiving_joint_side_lock"])
    }
    if retained == box_faces:
        return face_features
    return {**face_features, "box_body": retained}


def receiving_default_local_joints_only(rows):
    """Allow suffix cache reuse only for certified local default EndCap joints.

    The real GUI creates intent-derived Head/Tail to BoxBody joints even in a
    fresh receiving project. These do not connect distant Bays. Any user,
    solver, family, unknown or revised joint still fails closed to full solve.
    """
    from collections.abc import Mapping

    if rows is None:
        return True
    if not isinstance(rows, (list, tuple)):
        return False
    for raw in rows:
        if not isinstance(raw, Mapping):
            return False
        part, target = raw.get("subject_part"), raw.get("target_part")
        edge, source = raw.get("edge"), raw.get("source")
        if (part not in ("head", "tail") or target != "box_body"
                or edge not in ("TOP", "BOTTOM", "LEFT", "RIGHT")
                or raw.get("revision") != 1):
            return False
        origin = raw.get("migration_origin")
        if source == "INTENT_DERIVED":
            if origin != "ASSEMBLY_INTENT":
                return False
        elif source == "LEGACY_MIGRATED":
            if origin not in ("ASSEMBLY_TYPE", "ENDCAP_BOTTOM_WRAP"):
                return False
        else:
            return False
        joint_id = raw.get("joint_id", "")
        if (not isinstance(joint_id, str)
                or not joint_id.startswith(f"{part}:box_body:{edge.lower()}:")
                or not joint_id.endswith(":intent_derived")):
            return False
    return True


def project_receiving_bay_preview_fingerprint_snapshot(snapshot, *, set_index, bay_index,
                                                 allow_upstream_translation=False,
                                                 allow_suffix_topology_reuse=False):
    """Read-only key projection for provably unrelated *trailing* Bay dimensions.

    The requesting Bay's own W/H/D, its left/right Joint participants and
    every preceding Bay remain part of the key: the left chain controls
    assembly X/Y/Z, and the immediate right neighbor controls side locks.
    Only distant prefixes (with world-offset rebasing) and Bays strictly
    AFTER the right neighbor are independent of this Bay's local sheet.
    For tail-only topology resize, drop distant suffix rows AND the matching
    unused per-Bay setting refs/values from the key; a SHARED setting value
    referenced by this Bay or its neighbor is always retained.
    All relevant IDs, nearby Joints, NFB, features, other Sets, model and
    global geometry authority remain included and fail closed.
    NEVER use this deliberately incomplete copy as a saved/solved layout.
    """
    # Copy-on-write only the key's suffix path. Deep-copying the entire
    # projected project on every display refresh would itself be a slowdown.
    fingerprint_snapshot = dict(snapshot)
    if canonical_family_name(fingerprint_snapshot) != "受電箱":
        return fingerprint_snapshot
    if fingerprint_snapshot.get("active_mode", "set_bay") != "set_bay":
        return fingerprint_snapshot
    layout = fingerprint_snapshot.get("receiving_layout")
    if not isinstance(layout, dict) or layout.get("schema") != "receiving-layout-v1":
        return fingerprint_snapshot
    sets = layout.get("sets")
    if not isinstance(sets, list) or type(set_index) is not int:
        return fingerprint_snapshot
    if not 0 <= set_index < len(sets) or type(bay_index) is not int:
        return fingerprint_snapshot
    selected = sets[set_index]
    if not isinstance(selected, dict):
        return fingerprint_snapshot
    bays = selected.get("bays")
    joints = selected.get("joints")
    if not isinstance(bays, list) or not isinstance(joints, list):
        return fingerprint_snapshot
    if not 0 <= bay_index < len(bays) or len(joints) != len(bays) - 1:
        return fingerprint_snapshot
    if not all(isinstance(row, dict) and row.get("stable_id")
               for row in bays):
        return fingerprint_snapshot
    # Only the operator label and its monotonic allocator are non-geometric.
    # Keep every physical ID, Fold/Joint/NFB setting and unknown extension in
    # the source key. Never mutate the canonical project or manufacturing input.
    # Do this before early returns so a label edit cannot rebuild a physical
    # FinalScene even when a custom Joint requires conservative cache policy.
    if not all(isinstance(group, dict)
               and isinstance(group.get("bays"), list)
               and all(isinstance(row, dict) for row in group["bays"])
               for group in sets):
        return fingerprint_snapshot
    shallow_layout = {key: value for key, value in layout.items()
                      if key != "next_panel_number"}
    shallow_sets = []
    for group in sets:
        copy_group = dict(group)
        copy_group["bays"] = [
            {key: value for key, value in row.items() if key != "panel_name"}
            for row in group["bays"]
        ]
        shallow_sets.append(copy_group)
    shallow_layout["sets"] = shallow_sets
    fingerprint_snapshot["receiving_layout"] = shallow_layout
    layout, sets = shallow_layout, shallow_sets
    selected = sets[set_index]
    bays, joints = selected["bays"], selected["joints"]
    # Custom joints, custom parts and committed Joint relief may connect
    # non-neighboring Bays. Even with both optimization flags disabled, the
    # ordinary path below would still hide trailing dimensions. Never reuse
    # a possibly stale FinalScene: retain the entire authoritative key.
    if (fingerprint_snapshot.get("custom_parts")
            or fingerprint_snapshot.get("joint_relief_state")
            or not receiving_default_local_joints_only(
                fingerprint_snapshot.get("assembly_joints"))):
        return fingerprint_snapshot
    keep_count = min(len(bays), bay_index + 2)
    trim_suffix = allow_suffix_topology_reuse and keep_count < len(bays)
    new_settings = None
    if trim_suffix and "settings" in selected:
        from collections.abc import Mapping
        raw = selected["settings"]
        if not isinstance(raw, Mapping):
            return fingerprint_snapshot
        included = tuple(str(row["stable_id"]) for row in bays[:keep_count])
        new_settings = {}
        for kind, row in raw.items():
            if (not isinstance(row, Mapping) or set(row) != {"refs", "values"}
                    or not isinstance(row["refs"], Mapping)
                    or not isinstance(row["values"], Mapping)):
                return fingerprint_snapshot
            if any(bay_id not in row["refs"] for bay_id in included):
                return fingerprint_snapshot
            refs = {bay_id:row["refs"][bay_id] for bay_id in included}
            if any(ref not in row["values"] for ref in refs.values()):
                return fingerprint_snapshot
            values = {ref:row["values"][ref] for ref in refs.values()}
            new_settings[kind] = {"refs":refs, "values":values}
    hidden = (() if trim_suffix else tuple(range(bay_index + 2, len(bays))))
    if allow_upstream_translation and bay_index >= 2:
        hidden += tuple(range(0, bay_index - 1))
    if not hidden and not trim_suffix:
        return fingerprint_snapshot
    # Copy-on-write: only a derived *cache key*, never an output or saved DTO.
    shallow_layout = dict(layout)
    shallow_sets = list(sets)
    shallow_set = dict(selected)
    shallow_bays = list(bays[:keep_count] if trim_suffix else bays)
    for position in hidden:
        later = dict(bays[position])
        for axis in ("width", "height", "depth"):
            later.pop(axis, None)
        shallow_bays[position] = later
    shallow_set["bays"] = shallow_bays
    if trim_suffix:
        shallow_set["joints"] = list(joints[:keep_count - 1])
        if new_settings is not None:
            shallow_set["settings"] = new_settings
    shallow_sets[set_index] = shallow_set
    shallow_layout["sets"] = shallow_sets
    fingerprint_snapshot["receiving_layout"] = shallow_layout
    return fingerprint_snapshot

@dataclass(frozen=True)
class ReceivingBayWorldAssemblyProjection:
    """One Engine-selected Bay world datum and ordered visible physical parts."""

    bay_offset: tuple[float, float, float]
    part_placements: tuple[tuple[object, tuple[float, float, float]], ...]


def project_receiving_bay_preview_assembly_members(
    layout, resolved_parts, *, set_index, bay_index,
) -> ReceivingBayWorldAssemblyProjection:
    """Place actual resolved Bay sheets in Engine-derived joint world space.

    The caller has already resolved the canonical PartSpecs/FinalScene.
    This is read-only display placement: standalone sheets do not belong
    to a Bay Assembly. Invalid world offsets fail closed rather than being
    truncated by zip() or projected as a partially assembled cabinet.
    """
    from math import isfinite
    from .receiving_layout import receiving_bay_assembly_offsets

    offsets = receiving_bay_assembly_offsets(layout, set_index=set_index)
    if type(bay_index) is not int or not 0 <= bay_index < len(offsets):
        raise IndexError("Receiving preview bay_index out of range")
    bay_offset = tuple(float(x) for x in offsets[bay_index])
    if len(bay_offset) != 3 or not all(isfinite(x) for x in bay_offset):
        raise ValueError("RECEIVING_BAY_WORLD_OFFSET_INVALID")

    projected = []
    for part in tuple(resolved_parts or ()):
        role = getattr(part, "placement", None)
        if role == "standalone":
            continue
        if not isinstance(role, str) or not role:
            raise ValueError("RECEIVING_BAY_ASSEMBLY_PLACEMENT_MISSING")
        raw = getattr(part, "offset", None)
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            raise ValueError("RECEIVING_BAY_PART_WORLD_OFFSET_INVALID")
        try:
            if any(isinstance(x, bool) for x in raw):
                raise ValueError("bool offset")
            local = tuple(float(x) for x in raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("RECEIVING_BAY_PART_WORLD_OFFSET_INVALID") from exc
        world = tuple(a + b for a, b in zip(local, bay_offset))
        if not all(isfinite(x) for x in local + world):
            raise ValueError("RECEIVING_BAY_PART_WORLD_OFFSET_INVALID")
        projected.append((part, world))
    return ReceivingBayWorldAssemblyProjection(bay_offset, tuple(projected))


def plan_receiving_bay_preview_offset_rebase(parts, old_anchor, new_anchor):
    """Plan immutable world placement deltas; never alter sheets or source parts.

    Caller must first reject unsupported FinalScene envelopes (diagnostics,
    collisions, nonstandard origins); no rebase can approve manufacturing.
    Return None for invalid, ambiguous, standalone or nonfinite placements.
    """
    from math import isfinite
    if (not isinstance(old_anchor, (tuple, list))
            or not isinstance(new_anchor, (tuple, list))
            or len(old_anchor) != 3 or len(new_anchor) != 3):
        return None
    try:
        delta = tuple(float(b) - float(a) for a, b in zip(old_anchor, new_anchor))
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(isfinite(v) for v in delta):
        return None
    translated = []
    for part in tuple(parts):
        if (getattr(part, "placement", None) == "standalone"
                or not isinstance(getattr(part, "offset", None), (tuple, list))
                or len(part.offset) != 3):
            return None
        try:
            offset = tuple(float(v) + shift for v, shift in zip(part.offset, delta))
        except (TypeError, ValueError, OverflowError):
            return None
        if not all(isfinite(v) for v in offset):
            return None
        translated.append(offset)
    return tuple(translated)
