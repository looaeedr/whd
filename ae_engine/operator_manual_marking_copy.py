"""#3414 explicit copy of one saved manual-marking group into another real sheet.

The receiving LEFT BasePlate is the *only* currently proven copy source
and destination.  A same-named Bay/version must never be inferred from the
part name; multi-scope projects fail closed until a physical scoped resolver
exists. The caller selects the destination editor and one saved source file.
No auto-sync and no import of another project's manufacturing permission.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from .sheetmetal_feature_core import ProfileFeature


def _file_identity(path, digest, role):
    if not isinstance(path, (str, Path)):
        raise ValueError("MANUAL_COPY_" + role + "_PROJECT_REQUIRED")
    target = Path(path).resolve(strict=True)
    if target.suffix.lower() != ".p6fold" or not target.is_file():
        raise ValueError("MANUAL_COPY_" + role + "_PROJECT_REQUIRED")
    raw = target.read_bytes()
    if not isinstance(digest, str) or digest != sha256(raw).hexdigest():
        raise ValueError("MANUAL_COPY_" + role + "_SAVED_SOURCE_CHANGED")
    return str(target), raw


def _bound_project_snapshot(raw, claimed, role):
    """Decode the same hash-verified bytes using the existing project API."""
    from . import manufacturing_api as api

    try:
        decoded = api.decode_project_value(json.loads(raw.decode("utf-8")))
        saved = api.project_operator_project_for_read(decoded)["snapshot"]
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise ValueError("MANUAL_COPY_" + role + "_SAVED_PROJECT_INVALID") from error
    # Mapping equality ignores serialization/key ordering, but not changed
    # authored geometry, features, physical owners or runtime scope.
    if saved != claimed:
        raise ValueError("MANUAL_COPY_" + role + "_SAVED_SNAPSHOT_MISMATCH")
    return saved


def _unique_single_sheet(snapshot, role):
    if not isinstance(snapshot, Mapping):
        raise ValueError("MANUAL_COPY_" + role + "_SNAPSHOT_REQUIRED")
    # Project readback legitimately projects the persisted Set1/Bay1
    # as a *transient* runtime selection, even for one legacy BasePlate.
    # Prove that selection matches its only true saved physical owner.
    # Multiple bays/sets are unsupported, never mapped by shared part name.
    if snapshot.get("active_mode") == "quantity":
        raise ValueError("MANUAL_COPY_VERSION_OWNER_UNRESOLVED")
    layout = snapshot.get("receiving_layout") or {}
    if not isinstance(layout, Mapping):
        raise ValueError("MANUAL_COPY_SET_BAY_OWNER_UNRESOLVED")
    sets = tuple(layout.get("sets") or ())
    if len(sets) != 1 or not isinstance(sets[0], Mapping):
        raise ValueError("MANUAL_COPY_SET_BAY_OWNER_UNRESOLVED")
    bays = tuple(sets[0].get("bays") or ())
    if len(bays) != 1 or not isinstance(bays[0], Mapping):
        raise ValueError("MANUAL_COPY_SET_BAY_OWNER_UNRESOLVED")
    active = snapshot.get("_receiving_runtime_selection")
    if active is not None and (
        not isinstance(active, Mapping)
        or active.get("set_index") != 0 or active.get("bay_index") != 0
        or active.get("set_id") != sets[0].get("stable_id")
        or active.get("bay_id") != bays[0].get("stable_id")
        or set(active) != {"set_index", "bay_index", "set_id", "bay_id"}
    ):
        raise ValueError("MANUAL_COPY_SET_BAY_OWNER_UNRESOLVED")
    quantity = snapshot.get("quantity") or {}
    if isinstance(quantity, Mapping) and len(tuple(quantity.get("versions") or ())) > 1:
        raise ValueError("MANUAL_COPY_VERSION_OWNER_UNRESOLVED")
    for key in ("model", "w", "h", "t", "fw", "receiving_base_plate"):
        if key not in snapshot:
            raise ValueError("MANUAL_COPY_" + role + "_ORIGINAL_SOURCE_MISSING")
    if not isinstance(snapshot["receiving_base_plate"], Mapping):
        raise ValueError("MANUAL_COPY_" + role + "_ORIGINAL_SOURCE_MISSING")
    return snapshot


def _saved_source_features(snapshot):
    all_features = snapshot.get("part_features") or {}
    if not isinstance(all_features, Mapping) or "base_plate" not in all_features:
        raise ValueError("MANUAL_COPY_SOURCE_SAVED_MARKING_MISSING")
    features = tuple(all_features["base_plate"])
    workspace = snapshot.get("workspace") or {}
    if isinstance(workspace, Mapping):
        other = workspace.get("part_features")
        if isinstance(other, Mapping) and "base_plate" in other and (
            tuple(other["base_plate"]) != features
        ):
            raise ValueError("MANUAL_COPY_SOURCE_WORKSPACE_MARKING_DRIFT")
    return features


def _base_part_spec(snapshot, features):
    from . import manufacturing_api as api
    values, policy = api.resolve_fold_designer_base_plate_source(
        "base_plate", snapshot,
        width=snapshot["w"], height=snapshot["h"],
        thickness=snapshot["t"], frame_width=snapshot["fw"],
        model_name=snapshot["model"], corner_policy=None,
    )
    if policy is not None:
        raise ValueError("MANUAL_COPY_PHYSICAL_CORNER_POLICY_UNSUPPORTED")
    spec = api.build_base_plate_operator_part_spec(
        values, features=tuple(features), corner_policy=policy,
    )
    from .operator_manual_marking import require_first_sheet_manual_marking_spec
    require_first_sheet_manual_marking_spec(spec)
    return spec


def _live_owner_scope(snapshot):
    """Read actual canonical single-Bay ownership, never a GUI label."""
    from .cabinet_types.policy import canonical_family_name
    from .receiving_layout import normalize_receiving_layout
    if (not isinstance(snapshot, Mapping)
            or canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode") == "quantity"):
        raise ValueError("MANUAL_COPY_TARGET_LIVE_OWNER_CHANGED")
    layout = normalize_receiving_layout(snapshot.get("receiving_layout"))
    sets = layout["sets"]
    if len(sets) != 1 or len(sets[0]["bays"]) != 1:
        raise ValueError("MANUAL_COPY_TARGET_LIVE_OWNER_CHANGED")
    bay = sets[0]["bays"][0]
    return (sets[0]["stable_id"], bay["stable_id"],
            layout.get("base_plate_owner_namespace"), bay.get("base_plate_owner_id"),
            layout.get("next_panel_number"), layout.get("next_base_plate_owner_generation"))


def verify_saved_manual_marking_copy_sources(
    *, source_snapshot, source_project_path, source_project_sha256,
    target_snapshot, target_project_path, target_project_sha256,
    target_context, source_group_id, target_live_snapshot=None,
):
    """Revalidate the two saved byte-bound sources and the selected live sheet.

    No feature is inserted, and the source's old position is not tested
    against the destination. Reuse at selection, placement and confirmation.
    """
    from . import manufacturing_api as api
    from .contracts import ManufacturingContext
    from .operator_manual_marking import require_first_sheet_manual_marking_render

    source_file, source_bytes = _file_identity(
        source_project_path, source_project_sha256, "SOURCE",
    )
    target_file, target_bytes = _file_identity(
        target_project_path, target_project_sha256, "TARGET",
    )
    if source_file == target_file:
        raise ValueError("MANUAL_COPY_SAME_PHYSICAL_PROJECT")
    # Preserve the scoped error for existing callers supplying an invalid
    # claim; no geometry is resolved from that claim before byte binding.
    _unique_single_sheet(source_snapshot, "SOURCE")
    _unique_single_sheet(target_snapshot, "TARGET")
    _saved_source_features(source_snapshot)
    source = _bound_project_snapshot(source_bytes, source_snapshot, "SOURCE")
    target = _bound_project_snapshot(target_bytes, target_snapshot, "TARGET")
    if target_live_snapshot is not None and (
        _live_owner_scope(target_live_snapshot) != _live_owner_scope(target)
    ):
        raise ValueError("MANUAL_COPY_TARGET_LIVE_OWNER_CHANGED")
    original = _saved_source_features(source)
    if not isinstance(source_group_id, str) or not source_group_id:
        raise ValueError("MANUAL_COPY_EXPLICIT_GROUP_ID_REQUIRED")
    source_rows = [f for f in original if api.is_manual_group(f)
                   and api.group_parameters(f)["group_id"] == source_group_id]
    if len(source_rows) != 1:
        raise ValueError("MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS")
    if (target_context is None
            or target_context.part_key != "base_plate"):
        raise ValueError("MANUAL_COPY_TARGET_PHYSICAL_OWNER_UNRESOLVED")
    require_first_sheet_manual_marking_render(
        "base_plate", target_context.render_data,
    )

    resource = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    source_render = api.build_part_render_data(
        _base_part_spec(source, original), resource,
    )
    from .operator_manual_marking import verify_manual_marking_output
    verify_manual_marking_output(source_render)
    source_context = api.resolve_physical_sheet_editor_context(
        "base_plate", source_render,
    )
    api.propose_operator_physical_sheet_hole_features(
        "base_plate", source_context, original,
    )

    # Re-resolve the saved TARGET source, not a reused "base_plate" label
    # from another file or Bay. Uncommitted dimensions cannot be silently
    # mistaken for the saved physical sheet.
    target_render = api.build_part_render_data(
        _base_part_spec(target, ()), resource,
    )
    require_first_sheet_manual_marking_render("base_plate", target_render)
    if (target_render.unfolded_topology != target_context.render_data.unfolded_topology
            or not target_render.material.equals(target_context.render_data.material)
            or tuple(row for row in target_render.scene.primitives
                     if row.layer in ("CUTTING", "BEND", "BLIND_HOLE"))
            != tuple(row for row in target_context.render_data.scene.primitives
                     if row.layer in ("CUTTING", "BEND", "BLIND_HOLE"))):
        raise ValueError("MANUAL_COPY_TARGET_SAVED_PHYSICAL_SOURCE_CHANGED")

    return source_rows[0]


def copy_saved_manual_marking_group_to_selected_sheet(
    *, source_snapshot, source_project_path, source_project_sha256,
    target_snapshot, target_project_path, target_project_sha256,
    target_context, target_features, source_group_id, target_position,
    target_live_snapshot=None,
):
    """Place a new independent group at the operator's destination anchor."""
    from . import manufacturing_api as api
    from .operator_manual_marking_groups import _rebuild
    from .sheetmetal_geometry import Vec2

    group = verify_saved_manual_marking_copy_sources(
        source_snapshot=source_snapshot, source_project_path=source_project_path,
        source_project_sha256=source_project_sha256, target_snapshot=target_snapshot,
        target_project_path=target_project_path, target_project_sha256=target_project_sha256,
        target_context=target_context, source_group_id=source_group_id,
        target_live_snapshot=target_live_snapshot,
    )
    if not isinstance(target_position, Vec2) or target_features is None:
        raise ValueError("MANUAL_COPY_TARGET_POSITION_REQUIRED")
    params = dict(api.group_parameters(group))
    # Single L uses its real turn point, cross its real intersection.
    # Pair/four-corner L use the nominal group center. Preserve all local
    # member offsets, rotation, mirror and dash phase.
    anchor = group.offset
    if params["kind"] in ("l", "cross"):
        anchor = api.group_member_world_points(group)[0][1]
    offset = Vec2(target_position.x + group.offset.x - anchor.x,
                  target_position.y + group.offset.y - anchor.y)
    params["group_id"] = uuid4().hex
    clone = _rebuild(replace(group, offset=offset, source_params=()), params)
    if (api.group_parameters(clone)["group_id"] == source_group_id
            or clone is group or not isinstance(clone, ProfileFeature)):
        raise ValueError("MANUAL_COPY_NEW_GROUP_ID_REQUIRED")
    # The target's actual current holes, full stroke and every hidden dash
    # space are checked by the *original* first-sheet Engine gate.
    api.propose_operator_physical_sheet_hole_features(
        "base_plate", target_context, tuple(target_features) + (clone,),
    )
    return clone
