"""#3414 explicit copy of one saved manual-marking group into another real sheet.

The legacy Receiving LEFT BasePlate path remains cross-project only.
The ordinary EndCap path uses explicit, independently verified physical
owners. A same-named Bay/version must never be inferred from the part name.
The caller selects the destination editor and one saved source file.
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


def _resolve_bound_saved_marking_geometry(saved, key, resolve_saved_geometry):
    """Ask the trusted adapter only after the same bytes have been decoded.

    A saved FinalScene is not a project authority. This private port takes
    actual decoded project inputs and an explicit part; the GUI must not
    implement this port by substituting its current live target or cached DXF.
    """
    from copy import deepcopy

    if not callable(resolve_saved_geometry):
        raise TypeError("MANUAL_COPY_CANONICAL_SAVED_RENDER_REQUIRED")
    return resolve_saved_geometry(deepcopy(saved), key)


def list_ordinary_marking_copy_versions(snapshot, part_key):
    """Return the existing project version choices; never guess a donor."""
    from .operator_quantity_marking_owner import uses_quantity_physical_marking_editor
    from .receiving_quantity_versions import QuantityModel

    if part_key not in {"door", "base_plate"} or not uses_quantity_physical_marking_editor(snapshot, part_key):
        return ()
    model = QuantityModel.from_payload(snapshot["quantity"])
    return tuple((row["version_id"], row["piece_count"])
                 for row in model.snapshot()["versions"])


def _read_ordinary_copy_owner(snapshot, geometry, key, version_id, *, require_selected=False, allow_unowned=False):
    from .operator_quantity_marking_owner import open_quantity_physical_marking
    from .operator_root_marking_store import open_workspace_owner_marking_draft
    from .operator_selected_marking_receipt import open_selected_ordinary_marking_modal_source
    from .receiving_quantity_versions import QuantityModel

    versions = list_ordinary_marking_copy_versions(snapshot, key)
    if versions:
        if version_id not in {identity for identity, _ in versions}:
            raise ValueError("MANUAL_COPY_EXPLICIT_QUANTITY_VERSION_REQUIRED")
        model = QuantityModel.from_payload(snapshot["quantity"])
        if require_selected and model.selected_version_id != version_id:
            raise ValueError("MANUAL_COPY_TARGET_EDITOR_SESSION_STALE")
        model.select(version_id)
        scoped = {**snapshot, "quantity": model.snapshot()}
        opening = open_quantity_physical_marking(scoped, geometry, key)
        marks = () if opening.saved_record is None else opening.saved_record["features"]
        receipt = opening.stock
    else:
        if version_id is not None:
            raise ValueError("MANUAL_COPY_QUANTITY_VERSION_UNAVAILABLE")
        receipt = open_selected_ordinary_marking_modal_source(snapshot, geometry, key)
        marks = (() if receipt.owner_id is None else
                 open_workspace_owner_marking_draft(snapshot, receipt).saved_marks)
    if receipt.output_capability != "verified_normal" or (receipt.owner_id is None and not allow_unowned):
        raise ValueError("MANUAL_COPY_PHYSICAL_OWNER_UNRESOLVED")
    return receipt, tuple(marks)


def _open_ordinary_saved_copy_source(
    *, source_snapshot, source_project_path, source_project_sha256,
    source_part_key, resolve_saved_geometry, source_version_id=None,
):
    """Read one explicitly selected ordinary sheet, bound to saved bytes and ink.

    Geometry must come from the existing canonical selected-part resolver.
    Its source seal then has to equal the persisted physical owner's mark
    record. This helper grants no publication or placement capability.
    """
    if source_part_key not in ("head", "tail", "door", "base_plate"):
        raise ValueError("MANUAL_COPY_EXPLICIT_ORDINARY_SOURCE_REQUIRED")
    path, raw = _file_identity(source_project_path, source_project_sha256, "SOURCE")
    saved = _bound_project_snapshot(raw, source_snapshot, "SOURCE")
    source_geometry = _resolve_bound_saved_marking_geometry(
        saved, source_part_key, resolve_saved_geometry,
    )
    receipt, marks = _read_ordinary_copy_owner(saved, source_geometry, source_part_key, source_version_id)
    if not marks:
        raise ValueError("MANUAL_COPY_SOURCE_GROUP_MISSING")
    return path, receipt, marks


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
    if not isinstance(all_features, Mapping):
        raise ValueError("MANUAL_COPY_SOURCE_SAVED_MARKING_MISSING")
    features = tuple(all_features.get("base_plate", ()))
    workspace = snapshot.get("workspace") or {}
    if isinstance(workspace, Mapping):
        other = workspace.get("part_features")
        if isinstance(other, Mapping) and "base_plate" in other and (
            tuple(other["base_plate"]) != features
        ):
            raise ValueError("MANUAL_COPY_SOURCE_WORKSPACE_MARKING_DRIFT")
    from . import manufacturing_api as api
    owner = api.resolve_workspace_physical_root_owner(snapshot, "base_plate")
    record = api.read_workspace_marking_owner_record(snapshot, owner) if owner is not None else None
    if record is None:
        if "base_plate" not in all_features:
            raise ValueError("MANUAL_COPY_SOURCE_SAVED_MARKING_MISSING")
        return features  # untouched legacy role transport
    if any(api.is_manual_mark(f) for f in features):
        raise ValueError("PHYSICAL_MARKING_LEGACY_ROLE_MARKS_UNBOUND")
    from .contracts import ManufacturingContext
    source = api.build_part_render_data(
        _base_part_spec(snapshot, features),
        ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
    )
    geometry = api.selected_normal_marking_inventory("base_plate", source)
    receipt = api.open_physical_sheet_marking("base_plate", snapshot=snapshot, geometry=geometry)
    if receipt.output_capability != "existing_normal":
        raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
    saved = api.open_workspace_owner_marking_draft(snapshot, receipt)
    return (*features, *saved.saved_marks)


def list_saved_manual_marking_copy_groups(*, source_snapshot, source_project_path,
                                          source_project_sha256):
    """List IDs from the same byte-bound physical source that Copy will recheck."""
    from .operator_manual_marking_groups import group_parameters, is_manual_group

    _unique_single_sheet(source_snapshot, "SOURCE")
    _file, raw = _file_identity(source_project_path, source_project_sha256, "SOURCE")
    saved = _bound_project_snapshot(raw, source_snapshot, "SOURCE")
    rows = _saved_source_features(saved)
    return tuple(group_parameters(row)["group_id"] for row in rows if is_manual_group(row))


def project_live_manual_marking_copy_target_state(snapshot, part_key, *, editor_features=None):
    """Compare role holes and saved owner marks independently for the open target."""
    from .operator_manual_marking import is_manual_mark
    from .operator_root_marking_store import read_workspace_marking_owner_record
    from .workspace_state import resolve_workspace_physical_root_owner

    error = "MANUAL_COPY_TARGET_EDITOR_SESSION_STALE"
    if not isinstance(snapshot, Mapping) or part_key != "base_plate":
        raise ValueError(error)
    role = snapshot.get("part_features") or {}
    if not isinstance(role, Mapping):
        raise ValueError(error)
    role_features = tuple(role.get(part_key, ()))
    owner = resolve_workspace_physical_root_owner(snapshot, part_key)
    saved = read_workspace_marking_owner_record(snapshot, owner) if owner else None
    if saved is not None and any(is_manual_mark(row) for row in role_features):
        raise ValueError(error)
    marks = () if saved is None else saved["features"]
    if editor_features is not None and tuple(editor_features) != (*role_features, *marks):
        raise ValueError(error)
    return owner, role_features, saved


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
    from .workspace_state import resolve_workspace_physical_root_owner
    source_owner = resolve_workspace_physical_root_owner(source, "base_plate")
    if source_owner is not None and (
        source_owner == resolve_workspace_physical_root_owner(target, "base_plate")
        or source_owner == resolve_workspace_physical_root_owner(target_live_snapshot, "base_plate")
    ):
        # Save As does not create a different physical occupant. Older
        # ownerless files continue through their existing scoped witnesses.
        raise ValueError("MANUAL_COPY_SAME_PHYSICAL_OWNER")
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


class ManualCopyPlacementRejected(ValueError):
    """Only a rejected candidate on an already verified physical target.

    Source/owner/session failures and invalid pre-existing target features
    are intentionally not classified as retryable placement errors.
    """


def _clone_copy_group(group, source_group_id, target_position):
    from . import manufacturing_api as api
    from .operator_manual_marking_groups import _rebuild
    from .sheetmetal_geometry import Vec2

    if not isinstance(target_position, Vec2):
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
    return clone


def _open_ordinary_saved_copy_target(
    *, target_snapshot, target_project_path, target_project_sha256,
    target_part_key, resolve_saved_geometry, target_live_snapshot, target_live_geometry,
    target_version_id=None,
):
    """Match an explicitly selected live ordinary sheet to its saved stock."""
    if target_part_key not in ("head", "tail", "door", "base_plate"):
        raise ValueError("MANUAL_COPY_EXPLICIT_ORDINARY_TARGET_REQUIRED")
    path, raw = _file_identity(target_project_path, target_project_sha256, "TARGET")
    saved = _bound_project_snapshot(raw, target_snapshot, "TARGET")
    target_saved_geometry = _resolve_bound_saved_marking_geometry(
        saved, target_part_key, resolve_saved_geometry,
    )
    saved_receipt, saved_marks = _read_ordinary_copy_owner(
        saved, target_saved_geometry, target_part_key, target_version_id, allow_unowned=True,
    )
    live_receipt, live_marks = _read_ordinary_copy_owner(
        target_live_snapshot, target_live_geometry, target_part_key, target_version_id,
        require_selected=True, allow_unowned=True,
    )
    if saved_receipt.owner_id != live_receipt.owner_id:
        raise ValueError("MANUAL_COPY_TARGET_LIVE_OWNER_CHANGED")
    if saved_receipt.source_sha256 != live_receipt.source_sha256:
        raise ValueError("MANUAL_COPY_TARGET_SAVED_PHYSICAL_SOURCE_CHANGED")
    if saved_marks != live_marks:
        raise ValueError("MANUAL_COPY_TARGET_EDITOR_SESSION_STALE")
    return path, live_receipt


def _ordinary_saved_copy_key(mark):
    """Selection key in the sealed saved owner; not a persisted mark identity."""
    from .operator_manual_marking import is_manual_round_mark
    from .operator_manual_marking_groups import group_parameters, is_manual_group
    from .operator_physical_sheet_marking import is_manual_straight_mark

    if is_manual_group(mark):
        return group_parameters(mark)["group_id"]
    kind = "line" if is_manual_straight_mark(mark) else "circle" if is_manual_round_mark(mark) else None
    return f"{kind}:{sha256(repr(mark).encode('utf-8')).hexdigest()}" if kind else None


def _verify_ordinary_saved_copy_sources(*, source_group_id, source, target):

    source_file, source_receipt, source_marks = _open_ordinary_saved_copy_source(**source)
    target_file, target_receipt = _open_ordinary_saved_copy_target(**target)
    if source_receipt.owner_id == target_receipt.owner_id:
        raise ValueError("MANUAL_COPY_SAME_PHYSICAL_OWNER")
    if Path(source_file).samefile(target_file):
        if source["source_part_key"] == target["target_part_key"]:
            raise ValueError("MANUAL_COPY_SAME_PHYSICAL_OWNER")
        # Two explicit physical owners may share one project file. Bind both
        # to one saved revision and independently recheck the live donor.
        if source["source_project_sha256"] != target["target_project_sha256"]:
            raise ValueError("MANUAL_COPY_SAME_PROJECT_REVISION_CHANGED")
        live = target["target_live_snapshot"]
        key = source["source_part_key"]
        geometry = _resolve_bound_saved_marking_geometry(live, key, source["resolve_saved_geometry"])
        current, current_marks = _read_ordinary_copy_owner(
            live, geometry, key, source.get("source_version_id"),
        )
        if (current.owner_id != source_receipt.owner_id
                or current.source_sha256 != source_receipt.source_sha256):
            raise ValueError("MANUAL_COPY_LIVE_DONOR_SOURCE_CHANGED")
        if current_marks != source_marks:
            raise ValueError("MANUAL_COPY_LIVE_DONOR_MARKS_CHANGED")
    if not isinstance(source_group_id, str) or not source_group_id:
        raise ValueError("MANUAL_COPY_EXPLICIT_GROUP_ID_REQUIRED")
    matches = [mark for mark in source_marks if _ordinary_saved_copy_key(mark) == source_group_id]
    if len(matches) != 1:
        raise ValueError("MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS")
    return matches[0], target_receipt


def _copy_ordinary_saved_group(
    *, source_group_id, source, target, target_features, target_position,
):
    """Place with the ordinary editor's full-stroke and material validation."""
    from .operator_manual_marking import _build_manual_round_feature, is_manual_round_mark
    from .operator_physical_sheet_marking import (
        is_manual_straight_mark, move_physical_sheet_straight_mark, validate_physical_sheet_marking_draft,
    )
    from .sheetmetal_geometry import Vec2

    group, receipt = _verify_ordinary_saved_copy_sources(
        source_group_id=source_group_id, source=source, target=target,
    )
    if target_features is None:
        raise ValueError("MANUAL_COPY_TARGET_POSITION_REQUIRED")
    existing = tuple(target_features)
    validate_physical_sheet_marking_draft(receipt, existing)
    if not isinstance(target_position, Vec2):
        raise ValueError("MANUAL_COPY_TARGET_POSITION_REQUIRED")
    try:
        if is_manual_straight_mark(group):
            start, end = group.points
            return move_physical_sheet_straight_mark(
                receipt, (*existing, group), selected_index=len(existing),
                displacement=Vec2(target_position.x - (start.x + end.x) / 2,
                                  target_position.y - (start.y + end.y) / 2),
            )
        if is_manual_round_mark(group):
            if "circle" not in receipt.allowed_tools:
                raise ValueError("PHYSICAL_SHEET_MARKING_TOOL_UNSUPPORTED")
            clone = _build_manual_round_feature(target_position, group.diameter)
        else:
            clone = _clone_copy_group(group, source_group_id, target_position)
        validate_physical_sheet_marking_draft(receipt, (*existing, clone))
    except ValueError as exc:
        raise ManualCopyPlacementRejected(str(exc)) from exc
    return clone


def copy_saved_manual_marking_group_to_selected_sheet(
    *, source_snapshot, source_project_path, source_project_sha256,
    target_snapshot, target_project_path, target_project_sha256,
    target_context, target_features, source_group_id, target_position,
    target_live_snapshot=None,
):
    """Place a new independent group at the operator's destination anchor."""
    from . import manufacturing_api as api
    group = verify_saved_manual_marking_copy_sources(
        source_snapshot=source_snapshot, source_project_path=source_project_path,
        source_project_sha256=source_project_sha256, target_snapshot=target_snapshot,
        target_project_path=target_project_path, target_project_sha256=target_project_sha256,
        target_context=target_context, source_group_id=source_group_id,
        target_live_snapshot=target_live_snapshot,
    )
    clone = _clone_copy_group(group, source_group_id, target_position)
    if target_features is None:
        raise ValueError("MANUAL_COPY_TARGET_POSITION_REQUIRED")
    # Validate the unmodified draft first: a bad existing source is not
    # something the operator can repair by clicking another copy position.
    existing = tuple(target_features)
    api.propose_operator_physical_sheet_hole_features(
        "base_plate", target_context, existing,
    )
    # The same authoritative validator checks all full strokes and holes.
    # Only the candidate-specific ValueError permits another click.
    try:
        api.propose_operator_physical_sheet_hole_features(
            "base_plate", target_context, existing + (clone,),
        )
    except ValueError as exc:
        raise ManualCopyPlacementRejected(str(exc)) from exc
    return clone


def list_saved_endcap_marking_copy_candidates(source):
    """Project readable geometry from the same sealed saved marks as their copy keys."""
    from math import hypot
    from .operator_manual_marking import is_manual_round_mark
    from .operator_manual_marking_groups import group_member_world_points, group_parameters, is_manual_group
    from .operator_physical_sheet_marking import is_manual_straight_mark
    _, _, marks = _open_ordinary_saved_copy_source(**source)
    candidates = []
    for mark in marks:
        key = _ordinary_saved_copy_key(mark)
        if key is None:
            continue
        if is_manual_straight_mark(mark):
            a, b = mark.points
            x, y = (a.x + b.x) / 2, (a.y + b.y) / 2
            kind, size = "line", hypot(b.x - a.x, b.y - a.y)
        elif is_manual_round_mark(mark):
            x, y = mark.offset.x, mark.offset.y
            kind, size = "circle", mark.diameter
        elif is_manual_group(mark):
            kind = group_parameters(mark)["kind"]
            point = group_member_world_points(mark)[0][1] if kind in ("l", "cross") else mark.offset
            x, y, size = point.x, point.y, None
        else:
            raise ValueError("MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS")
        candidates.append((key, kind, x, y, size))
    keys = tuple(row[0] for row in candidates)
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS")
    return tuple(candidates)


def list_saved_endcap_marking_copy_groups(source):
    """Compatibility projection of selection keys, not operator-facing text."""
    return tuple(row[0] for row in list_saved_endcap_marking_copy_candidates(source))


def verify_saved_endcap_marking_copy(*, source_group_id, source, target):
    """Recheck the read-only source and current destination; no writes here."""
    return _verify_ordinary_saved_copy_sources(source_group_id=source_group_id, source=source, target=target)


def place_saved_endcap_marking_copy(*, source_group_id, source, target, target_features, target_position):
    """Create a vetted group; the normal editor remains the transaction owner."""
    return _copy_ordinary_saved_group(source_group_id=source_group_id, source=source, target=target,
                                     target_features=target_features, target_position=target_position)
