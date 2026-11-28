"""Saved, owner-bound Receiving C-divider input to the existing resolver.

The bounded four-part dependency closure is not a replacement resolver or a
manufacturing/marking qualification. Other dependency graphs remain unsupported.
"""
from collections.abc import Mapping
from copy import deepcopy

from .contracts import ManufacturingContext, ResolvedManufacturingGeometry
from .manufacturing_contracts import ManufacturingPartInput, ManufacturingResolveRequest
from .manufacturing_equivalence import ManufacturingParameters, manufacturing_equivalence_payload
from .manufacturing_scene_access import owner_render_data
from .receiving_horizontal_divider_owner import open_receiving_horizontal_divider_owner_receipt
from .receiving_layout import normalize_receiving_layout
from .inner_door_frames import inner_door_frame_stable_id
from .door_dividers import divider_stable_id
from .physical_part_identity import is_box_body_physical_piece_key


def is_c_divider_source_guard_key(part_key):
    """Recognize the bounded slot for an extra rejection check, not admission."""
    if not isinstance(part_key, str) or not part_key.startswith('box_body:divider:'):
        return False
    scope, sep, suffix = part_key[len('box_body:divider:'):].partition(':')
    return bool(scope and sep and suffix and part_key == divider_stable_id(scope, 'HORIZONTAL', 'C0:R0|R1'))


def _saved_field(snapshot, workspace, key):
    if key not in workspace:
        raise ValueError(f"C_DIVIDER_SAVED_SOURCE_REQUIRED:{key}")
    value = workspace[key]
    if key in snapshot and snapshot[key] != value:
        raise ValueError(f"C_DIVIDER_SAVED_SOURCE_CONFLICT:{key}")
    return deepcopy(value)


def build_saved_receiving_c_divider_request(snapshot, part_key, *, set_index=0, bay_index=0):
    """Materialize only the verified single-Bay C/box/left/right closure.

    All raw sheets use the same existing PartSpec, Family and profile owners
    as the Primary request adapter. No caller render, preview, default Factory
    request or Tk callback is accepted. Read-only; never allocates an owner.
    """
    from . import manufacturing_api as api

    owner = open_receiving_horizontal_divider_owner_receipt(
        snapshot, part_key, set_index=set_index, bay_index=bay_index,
    )
    layout = normalize_receiving_layout(snapshot['receiving_layout'])
    if len(layout['sets']) != 1 or len(layout['sets'][0]['bays']) != 1:
        raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    workspace = snapshot.get('workspace')
    settings = snapshot.get('settings')
    if not isinstance(workspace, Mapping) or not isinstance(settings, Mapping):
        raise ValueError('C_DIVIDER_SAVED_WORKSPACE_REQUIRED')
    # Explicit assembly joints may introduce dependencies outside the four
    # proved inputs. Do not silently discard them or replay a partial solve.
    declared_rows = snapshot.get('assembly_joints', ())
    if not declared_rows and int(snapshot.get('assembly_joint_schema_version', 0) or 0) <= 1:
        # The canonical graph owner reads this alias in schema 0/1 and can
        # discard inferred rows during migration. Check the actual declaration first.
        declared_rows = snapshot.get('joints', ())
    if any(not isinstance(j, Mapping) or j.get('source') != 'LEGACY_MIGRATED'
           for j in declared_rows):
        raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    if snapshot.get('joint_relief_state'):
        raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    # A detached catalog entry is not a dependency of the four-part replay.
    # Keep rejecting explicit joints above, and also reject a custom endpoint
    # even if a migrated joint carries it.
    from .assembly_joint import AssemblyJoint
    from .custom_part_catalog import resolve_custom_part_catalog

    custom_ids = set(resolve_custom_part_catalog(snapshot).snapshot()['items'])
    if custom_ids:
        try:
            # Use the graph owner's normalization before migration can discard
            # a joint with an unavailable endpoint.
            declared = tuple(AssemblyJoint.from_dict(raw) for raw in declared_rows)
        except (TypeError, ValueError) as exc:
            raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED') from exc
        if any(custom_ids.intersection((joint.subject_part, joint.target_part)) for joint in declared):
            raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    relief = snapshot.get('assembly_relief', {})
    if not isinstance(relief, Mapping) or not isinstance(relief.get('parts', {}), Mapping) or set(relief.get('parts', {})) - {'head', 'tail'}:
        raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    presence = _saved_field(snapshot, workspace, 'existing_parts')
    if 'box_body' not in presence:
        raise ValueError('C_DIVIDER_SAVED_SOURCE_REQUIRED:box_body')
    body_profile = _saved_field(snapshot, workspace, 'box_body_profile')
    structure = _saved_field(snapshot, workspace, 'box_body_structure')
    profiles = _saved_field(snapshot, workspace, 'part_profiles')
    features = _saved_field(snapshot, workspace, 'part_features')
    faces = _saved_field(snapshot, workspace, 'part_face_features')
    if (not isinstance(body_profile, (tuple, list)) or not body_profile
            or not isinstance(structure, Mapping) or not structure
            or any(not isinstance(v, Mapping) for v in (profiles, features, faces))):
        raise ValueError('C_DIVIDER_SAVED_BODY_SOURCE_REQUIRED')
    source = api.project_receiving_bay_legacy_aliases(
        snapshot, set_index=set_index, bay_index=bay_index,
    )
    # Bay back-panel selection is the existing authority, not the root cache.
    structure = source['workspace']['box_body_structure']
    if source.get('nfb_config_submitted') or source.get('nfb_config'):
        raise ValueError('C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED')
    whd = {k: source[k] for k in ('w', 'h', 'd')}
    for k in ('t', 'fw'):
        if k not in source or k not in settings or source[k] != settings[k]:
            raise ValueError(f'C_DIVIDER_SAVED_SOURCE_CONFLICT:{k}')
    settings = api.project_receiving_manufacturing_request_settings(source, settings, whd)
    source = api.project_operator_manufacturing_request_snapshot(source, settings, whd)
    values = {**source, **api.project_manufacturing_scene_settings_overlay(source, settings), **whd}
    values['box_body_structure'] = structure
    values.update(api.project_manufacturing_scene_joint_source(source))
    items = source.get('inner_doors', ())
    if not isinstance(items, (tuple, list)) or len(items) != 1 or not isinstance(items[0], Mapping):
        raise ValueError('C_DIVIDER_SAVED_FRAME_DEPENDENCY_REQUIRED')
    item = items[0]
    if (not item.get('stable_id') or item.get('lower_frame_role', {}).get('divider_stable_id') != part_key
            or not {'left', 'right'}.issubset(item.get('included_frame_sides', ()))):
        raise ValueError('C_DIVIDER_SAVED_FRAME_DEPENDENCY_REQUIRED')
    frames = tuple(inner_door_frame_stable_id(item['stable_id'], side) for side in ('left', 'right'))
    derived = api.project_operator_derived_divider_inner_profiles(values)
    if tuple(derived.divider_profiles) != (part_key,) or any(k not in derived.inner_profiles for k in frames):
        raise ValueError('C_DIVIDER_SAVED_FRAME_DEPENDENCY_REQUIRED')
    if any(features.get(k) or faces.get(k) for k in (part_key, *frames)):
        # This slice does not authorize existing loose manual/feature data.
        raise ValueError('C_DIVIDER_SAVED_DERIVED_FEATURE_SOURCE_UNVERIFIED')

    # Exact saved BoxBody Fold readback; no merge with fresh/default profile.
    body_values = {**values, **api.read_box_body_outside_dimensions(body_profile, values)}
    if any(body_values[k] != whd[k] for k in ('w', 'd')) or body_values['fw'] != values['fw']:
        raise ValueError('C_DIVIDER_SAVED_BODY_DIMENSIONS_MISMATCH')
    bottom = api.project_manufacturing_endcap_bottom_fold_inputs(profiles)
    if set(bottom) != {'head_ybottom1', 'tail_ybottom1'}:
        raise ValueError('C_DIVIDER_SAVED_ENDCAP_BOTTOM_SOURCE_REQUIRED')
    body_values.update(bottom)
    body_values.update(api.resolve_fold_designer_legacy_numeric_settings(body_values, part_name='box_body'))
    body_values['physical_piece_features'] = {k: rows for k, rows in features.items() if is_box_body_physical_piece_key(k)}
    corners = source.get('corner_state')
    corner_keys = {'top_left', 'top_right', 'bottom_left', 'bottom_right'}
    if not isinstance(corners, Mapping) or any(
        not isinstance(corners.get(k), Mapping) or not corner_keys.issubset(corners[k])
        for k in ('head', 'tail')
    ):
        raise ValueError('C_DIVIDER_SAVED_CORNER_SOURCE_REQUIRED')
    policies = {k: api.resolve_operator_fold_designer_payload_corner_policy(
        corners, k, body_values['fw'], family_source=body_values,
        thickness=body_values['t'], structure_state=structure,
    ) for k in ('head', 'tail')}
    spec = api.build_box_body_operator_part_spec(
        body_values, model_name=source['model'], features=features.get('box_body', ()),
        face_features=faces.get('box_body', {}), head_corner_policy=policies['head'],
        tail_corner_policy=policies['tail'], fold_profile=body_profile,
        structure_state=structure, source_part_features=features,
        head_ybottom1=bottom['head_ybottom1'], tail_ybottom1=bottom['tail_ybottom1'],
        snapshot=body_values,
    )
    context = ManufacturingContext(draw_stock=False)
    body = api.build_operator_part_render_data(spec, context)
    parts = [ManufacturingPartInput('box_body', scene_values=body_values, render_data=body,
                                    committed_render_data=body, x_profile=body_profile,
                                    features=features.get('box_body', ()), face_features=faces.get('box_body', {}),
                                    box_body_structure=structure)]
    divider_input = api.project_operator_fold_designer_divider_input(
        part_key, values, default_depth=values['d'], default_thickness=values['t'],
    )
    divider = api.resolve_fold_designer_divider_part(part_key, divider_input)
    raw = api.build_box_body_divider_render_data(divider)
    fold = derived.divider_profiles[part_key]
    parts.append(ManufacturingPartInput(part_key, scene_values=values, render_data=raw,
                                       committed_render_data=raw, x_profile=fold['X'], y_profile=fold['Y'],
                                       box_body_structure=structure))
    for key in frames:
        frame = api.resolve_fold_designer_frame_part(key, values, default_thickness=values['t'])
        raw = api.build_inner_door_frame_render_data(frame)
        fold = derived.inner_profiles[key]
        parts.append(ManufacturingPartInput(key, scene_values=values, render_data=raw,
                                           committed_render_data=raw, x_profile=fold['X'], y_profile=fold['Y'],
                                           box_body_structure=structure))
    dimension_policies = {k: api.resolve_operator_snapshot_corner_policy(
        k, corner_state=corners, input_snapshot=source, settings_values=settings,
        endcap_fw_state=source.get('endcap_fw'),
    ) for k in ('head', 'tail')}
    dims = api.resolve_live_operator_finished_dimensions(
        'box_body', input_snapshot=source, settings_values=settings, working_box=whd,
        head_corner_policy=dimension_policies['head'], tail_corner_policy=dimension_policies['tail'],
    )
    return owner, ManufacturingResolveRequest(
        input_snapshot=source, settings=settings, box_dimensions=whd, corner_state=corners,
        endcap_fw=source.get('endcap_fw'), endcap_bottom_wrap=source.get('endcap_bottom_wrap'),
        assembly_graph=api.project_manufacturing_scene_joint_source(source),
        canonical_part_keys=tuple(p.part_key for p in parts), parts=tuple(parts),
        operator_finished_dimensions=dims, assembly_intent=source.get('assembly_type', ''),
        cabinet_model=source['model'],
        relief_clearance=api.normalize_operator_relief_clearance(relief.get('clearance')),
        allow_3d_fallback=api.normalize_operator_3d_fallback_flag(relief.get('fallback_enabled')),
    )


def _source_equivalence(render, thickness):
    return (manufacturing_equivalence_payload(render, ManufacturingParameters('C_DIVIDER_SAVED_SOURCE', thickness, None)),
            render.unfolded_topology, tuple(render.fold_guides))


def resolve_saved_receiving_c_divider_source(snapshot, part_key, *, set_index=0, bay_index=0):
    """Replay current persisted owner with the one canonical resolver."""
    from . import manufacturing_api as api
    owner, request = build_saved_receiving_c_divider_request(snapshot, part_key, set_index=set_index, bay_index=bay_index)
    result = api.resolve_manufacturing_request(request)
    render = owner_render_data(result.geometry, part_key)
    if render is None or (render.metadata.get('divider_assembly_relief') or {}).get('candidate_status') != 'CERTIFIED_REGISTRY_VERIFIED':
        raise ValueError('C_DIVIDER_SAVED_CERTIFIED_SOURCE_REQUIRED')
    frame_ids = set(request.canonical_part_keys[2:])
    emitted = {r.attached_part_id for r in result.diagnostics.joint_marking_results
               if r.locator_part_id == part_key and r.status == 'EMITTED'}
    if emitted != frame_ids:
        raise ValueError('C_DIVIDER_SAVED_JOINT_MARKING_SOURCE_REQUIRED')
    api.require_verified_operator_baseline_sources(request.cabinet_model)
    api._require_single_part_dxf_source(render)
    # Dependency sheets are only inputs; do not publish partial manufacturing
    # inventory for the box or frames through this selected C source API.
    return owner, ResolvedManufacturingGeometry(tuple(
        p for p in result.geometry.parts if p.part_key == part_key
    ))


def require_saved_receiving_c_divider_source(snapshot, geometry, part_key, *, set_index=0, bay_index=0):
    """Bind caller stock to independently replayed material + all existing ink."""
    owner, replay = resolve_saved_receiving_c_divider_source(snapshot, part_key, set_index=set_index, bay_index=bay_index)
    actual = owner_render_data(geometry, part_key)
    expected = owner_render_data(replay, part_key)
    if actual is None or _source_equivalence(actual, snapshot['t']) != _source_equivalence(expected, snapshot['t']):
        raise ValueError('C_DIVIDER_SAVED_SOURCE_MISMATCH')
    return owner


def resolve_saved_c_marking_owner(snapshot, part_key):
    """Identity only: one current persisted C occupant, never a geometry grant."""
    if not isinstance(snapshot, Mapping) or not is_c_divider_source_guard_key(part_key):
        return None
    from .cabinet_types.receiving import is_receiving_snapshot
    if (not is_receiving_snapshot(snapshot) or snapshot.get('active_mode', 'set_bay') != 'set_bay'
            or 'receiving_quantity_box' in snapshot or not snapshot.get('receiving_layout')):
        return None
    layout = normalize_receiving_layout(snapshot['receiving_layout'])
    if len(layout['sets']) != 1 or len(layout['sets'][0]['bays']) != 1:
        return None
    from .receiving_horizontal_divider_owner import OCCUPANCY
    occupant = layout['sets'][0]['bays'][0].get(OCCUPANCY)
    if not occupant or occupant['part_key'] != part_key:
        return None
    return open_receiving_horizontal_divider_owner_receipt(
        snapshot, part_key, set_index=0, bay_index=0,
    ).owner_id


def saved_c_marking_occupants(snapshot):
    """Read persisted occupant records before export inventory filtering."""
    from .cabinet_types.receiving import is_receiving_snapshot
    from .receiving_horizontal_divider_owner import OCCUPANCY
    if not is_receiving_snapshot(snapshot) or not snapshot.get('receiving_layout'):
        return ()
    layout = normalize_receiving_layout(snapshot['receiving_layout'])
    return tuple((o['part_key'], o['owner_id']) for group in layout['sets'] for bay in group['bays']
                 if (o := bay.get(OCCUPANCY)) is not None)


def needs_current_saved_c_marking_source(snapshot):
    """Request complete current source transport only for the supported C scope."""
    return any(resolve_saved_c_marking_owner(snapshot, key) == owner
               for key, owner in saved_c_marking_occupants(snapshot))


SAVED_C_PHYSICAL_EXPORT_MODE = '單Bay逐片(C打標)'


def supports_saved_c_physical_export_mode(snapshot):
    """Offer an explicit normal-output choice only for an active saved C mark."""
    from .operator_root_marking_store import read_workspace_marking_owner_record
    return any(resolve_saved_c_marking_owner(snapshot, key) == owner
               and read_workspace_marking_owner_record(snapshot, owner) is not None
               for key, owner in saved_c_marking_occupants(snapshot))


def normalize_saved_c_selected_export_mode(snapshot, flags, mode):
    """Translate explicit operator intent; never silently change grouped output."""
    if mode != SAVED_C_PHYSICAL_EXPORT_MODE:
        return mode
    from .operator_root_marking_store import selected_workspace_owner_marking_keys
    if not supports_saved_c_physical_export_mode(snapshot) or not any(
        resolve_saved_c_marking_owner(snapshot, key) is not None
        for key in selected_workspace_owner_marking_keys(snapshot, flags)
    ):
        raise ValueError('C_DIVIDER_MARKING_SCOPE_UNSUPPORTED')
    return None


def require_current_saved_c_marking_occupant(snapshot, current_workspace):
    """Reject delayed Designer sync after a committed Main Bay transition."""
    for key, owner in saved_c_marking_occupants(snapshot):
        if resolve_saved_c_marking_owner(snapshot, key) != owner:
            continue
        current = {**snapshot, 'receiving_layout': current_workspace.get('receiving_layout'),
                   'active_mode': current_workspace.get('active_mode', snapshot.get('active_mode'))}
        if resolve_saved_c_marking_owner(current, key) != owner:
            raise ValueError('ROOT_MARKING_OWNER_STALE')
