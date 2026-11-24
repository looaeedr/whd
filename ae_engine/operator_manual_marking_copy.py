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
from pathlib import Path
from uuid import uuid4

from .sheetmetal_feature_core import ProfileFeature


def _file_identity(path, digest, role):
    if not isinstance(path, (str, Path)):
        raise ValueError("MANUAL_COPY_" + role + "_PROJECT_REQUIRED")
    target = Path(path).resolve(strict=True)
    if target.suffix.lower() != ".p6fold" or not target.is_file():
        raise ValueError("MANUAL_COPY_" + role + "_PROJECT_REQUIRED")
    actual = sha256(target.read_bytes()).hexdigest()
    if not isinstance(digest, str) or digest != actual:
        raise ValueError("MANUAL_COPY_" + role + "_SAVED_SOURCE_CHANGED")
    return str(target), actual


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


def copy_saved_manual_marking_group_to_selected_sheet(
    *, source_snapshot, source_project_path, source_project_sha256,
    target_snapshot, target_project_path, target_project_sha256,
    target_context, target_features, source_group_id,
):
    """Return a NEW feature; never mutate either sheet or publish source DXF.

    Only a real saved source and explicitly selected live target can pass.
    The target's material/BEND is recomputed independently from its saved
    scope; target CUTTING/hole and dashed blanks are revalidated as a whole.
    The existing target editor Session owns Confirm/Undo/Save.
    """
    from . import manufacturing_api as api
    from .contracts import ManufacturingContext
    from .operator_manual_marking_groups import _rebuild
    from .operator_manual_marking import require_first_sheet_manual_marking_render

    source_file, _source_digest = _file_identity(
        source_project_path, source_project_sha256, "SOURCE",
    )
    target_file, _target_digest = _file_identity(
        target_project_path, target_project_sha256, "TARGET",
    )
    if source_file == target_file:
        raise ValueError("MANUAL_COPY_SAME_PHYSICAL_PROJECT")
    source = _unique_single_sheet(source_snapshot, "SOURCE")
    target = _unique_single_sheet(target_snapshot, "TARGET")
    original = _saved_source_features(source)
    if not isinstance(source_group_id, str) or not source_group_id:
        raise ValueError("MANUAL_COPY_EXPLICIT_GROUP_ID_REQUIRED")
    source_rows = [f for f in original if api.is_manual_group(f)
                   and api.group_parameters(f)["group_id"] == source_group_id]
    if len(source_rows) != 1:
        raise ValueError("MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS")
    if (target_context is None
            or target_context.part_key != "base_plate"
            or target_features is None):
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
                     if row.layer in ("CUTTING", "BEND"))
            != tuple(row for row in target_context.render_data.scene.primitives
                     if row.layer in ("CUTTING", "BEND"))):
        raise ValueError("MANUAL_COPY_TARGET_SAVED_PHYSICAL_SOURCE_CHANGED")

    group = source_rows[0]
    params = dict(api.group_parameters(group))
    params["group_id"] = uuid4().hex
    clone = _rebuild(replace(group, source_params=()), params)
    if (api.group_parameters(clone)["group_id"] == source_group_id
            or clone is group or not isinstance(clone, ProfileFeature)):
        raise ValueError("MANUAL_COPY_NEW_GROUP_ID_REQUIRED")
    # The target's actual current holes, full stroke and every hidden dash
    # space are checked by the *original* first-sheet Engine gate.
    api.propose_operator_physical_sheet_hole_features(
        "base_plate", target_context, tuple(target_features) + (clone,),
    )
    return clone
