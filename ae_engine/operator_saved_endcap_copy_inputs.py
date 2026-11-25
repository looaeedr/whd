"""Prepare explicit saved EndCap inputs for the existing Engine renderer.

No dimensions or folds are derived here. This is not a rendering authorization:
owner records and exact rendered stock remain separately checked by the copy path.
"""
from collections.abc import Mapping
from copy import deepcopy


def select_saved_endcap_copy_inputs(snapshot, selected_part):
    """Project one saved EndCap, never the active tab or neighboring EndCap."""
    if selected_part not in ("head", "tail"):
        raise ValueError("MANUAL_COPY_EXPLICIT_ORDINARY_SOURCE_REQUIRED")
    if not isinstance(snapshot, Mapping):
        raise ValueError("MANUAL_COPY_SAVED_SNAPSHOT_REQUIRED")
    workspace = snapshot.get("workspace", {})
    if not isinstance(workspace, Mapping):
        raise ValueError("MANUAL_COPY_SAVED_WORKSPACE_INVALID")

    def authored(field, *, child=None, default=None):
        data = tuple(doc[field] for doc in (snapshot, workspace) if field in doc)
        if child is not None:
            if any(not isinstance(item, Mapping) for item in data):
                raise ValueError(f"MANUAL_COPY_SAVED_{field.upper()}_INVALID")
            data = tuple(item[child] for item in data if child in item)
        if len(data) == 2 and data[0] != data[1]:
            raise ValueError(f"MANUAL_COPY_SAVED_{field.upper()}_CONFLICT")
        return data[0] if data else default

    presence = authored("existing_parts")
    if not isinstance(presence, (tuple, list)) or presence.count(selected_part) != 1:
        raise ValueError("MANUAL_COPY_SAVED_ENDCAP_NOT_PRESENT")
    profiles = authored("part_profiles", child=selected_part)
    if not isinstance(profiles, Mapping) or any(
        not isinstance(profiles.get(axis), (list, tuple)) or not profiles[axis]
        for axis in ("X", "Y")
    ):
        raise ValueError("MANUAL_COPY_SAVED_ENDCAP_FOLD_REQUIRED")
    body_profile = authored("box_body_profile")
    if not isinstance(body_profile, (list, tuple)) or not body_profile:
        raise ValueError("MANUAL_COPY_SAVED_BOX_FOLD_REQUIRED")
    # Do not let a display artifact stand in for a committed physical source.
    # The canonical renderer is responsible for decoding the authored
    # structure, corner, FW, joint, and relief data; this step supplies them.
    return deepcopy({
        "part_key": selected_part,
        "fold_profiles": {axis: profiles[axis] for axis in ("X", "Y")},
        "box_body_profile": body_profile,
        "saved_inputs": {
            key: value for key, value in snapshot.items() if key != "final_geometry"
        },
    })


def resolve_saved_endcap_copy_geometry(snapshot, part_key):
    """Build selected saved stock from the same Engine owners as the live editor."""
    from . import manufacturing_api as api
    from .contracts import ManufacturingContext

    selected = select_saved_endcap_copy_inputs(snapshot, part_key)
    raw = selected["saved_inputs"]
    body = selected["box_body_profile"]
    folds = selected["fold_profiles"]
    vals = dict(raw)
    for name in ("w", "h", "d", "t", "fw"):
        vals[name] = api.normalize_operator_source_dimension(raw[name], field=name)
    # Save materializes the project's effective settings and box controls at root.
    # Fold readback is authoritative for the selected part dimensions and folds.
    vals.update(api.resolve_endcap_xy_outside_dimensions(folds, vals))
    # Endcap FW follows the saved per-part settings, based on the evaluated
    # Fold readback, exactly as build_scene_payload_for_app selects its FW.
    vals["fw"] = api.resolve_endcap_fw(
        vals, part_key, state=api.normalize_endcap_fw_state(raw),
    )
    structure = raw.get("workspace", {}).get("box_body_structure", raw.get("box_body_structure"))
    if not isinstance(structure, Mapping):
        raise ValueError("MANUAL_COPY_SAVED_BOX_STRUCTURE_REQUIRED")
    authored_structure = structure
    joints = api.project_manufacturing_scene_joint_source(raw)
    vals.update(joints)
    wrap = api.normalize_endcap_bottom_wrap_state(raw)
    structure = api.project_manufacturing_bottom_relief_structure(
        vals, part_key, structure, bottom_wrap_state=wrap,
    )
    vals["box_body_structure"] = structure
    features = tuple((raw.get("part_features") or {}).get(part_key, ()))
    if any(api.is_manual_mark(f) for f in features):
        raise ValueError("PHYSICAL_MARKING_LEGACY_ROLE_MARKS_UNBOUND")
    topology = api.resolve_fold_designer_payload_topology(part_key, vals)
    model, unknown = topology[7:9]
    policy = api.resolve_operator_fold_designer_payload_corner_policy(
        raw.get("corner_state", {}), part_key, vals["fw"],
        unknown=unknown, family_source=vals, thickness=vals["t"],
        structure_state=structure,
    )
    values = {k: vals[k] for k in ("w", "h", "d", "t", "fw")}
    values.update(api.resolve_fold_designer_legacy_numeric_settings(vals, part_name=part_key))
    relief = raw.get("assembly_relief", {})
    cuts = ()
    if api.normalize_operator_settings_boolean(relief.get("enabled", False)):
        cuts = api.resolve_operator_committed_relief_cuts(
            part_key, values, relief_state=relief,
            joint_state=vals, structure_state=authored_structure, cabinet_family=model,
            box_body_profile=body, part_profiles=folds,
        )
    spec = api.build_endcap_operator_part_spec(
        values, model_name=None if unknown else model, is_tail=part_key == "tail",
        holes=features, corner_policy=policy, fold_profiles=folds,
        resolved_assembly_relief_cuts=cuts, box_body_fold_profile=body,
        box_body_structure_state=structure, endcap_bottom_wrap_state=wrap,
        assembly_joints=vals.get("assembly_joints"), assembly_joint_state=vals,
    )
    render = api.build_operator_part_render_data(spec, ManufacturingContext(draw_stock=False))
    return api.selected_normal_marking_inventory(part_key, render)
