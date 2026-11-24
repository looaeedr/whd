"""Connect physical preview identities to their existing hole owners."""


def open_workspace_sheet_editor(host, key, *, verified_only=False):
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    from phase6_part_navigation import operator_part_label
    from ae_engine import manufacturing_api

    app = host.fold_designer_app
    workspace = app.designer_workspace
    if key not in workspace.available_parts:
        raise ValueError(f'板件已不存在：{key}')

    def current_context():
        piece = manufacturing_api.is_box_body_physical_piece_key(key)
        query_key = 'box_body' if piece else key
        payload = build_scene_payload_for_app(app, query_key)
        payload['features'] = ()  # baseline must not duplicate editable holes
        if piece:
            payload['physical_piece_features'] = {}
        render = host._query_fold_designer_render_data(query_key, payload)
        custom_spec = None
        if manufacturing_api.is_custom_part(key):
            custom_spec, _ = host._fold_designer_part_spec_from_payload(key, payload)
        return payload, manufacturing_api.resolve_physical_sheet_editor_context(
            key, render, custom_spec=custom_spec,
        )

    payload, context = current_context()
    features = workspace.features_for(key)
    opened = (
        manufacturing_api.open_physical_sheet_marking(key, context=context, features=features)
        if manufacturing_api.first_sheet_manual_marking_supported(key, context.render_data)
        else None
    )
    project_epoch = host.project_controller.project_load_epoch if opened is not None else None

    snapshot = current_workspace_marking_source(app)
    owner = manufacturing_api.resolve_workspace_physical_root_owner(snapshot, key)
    claim = owner is not None and manufacturing_api.read_workspace_marking_owner_record(snapshot, owner)
    legacy_marks = any(manufacturing_api.is_manual_mark(row) for row in features)
    if claim and legacy_marks:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")
    if snapshot and (opened is not None or verified_only) and not legacy_marks:
        try:
            return _open_owner_bound_workspace_marking_editor(
                host, key, editing_context=context, role_features=features,
            )
        except ValueError as exc:
            # Only explicit ordinary capability absence selects legacy. A
            # stale/corrupt bound source must not silently fall through.
            if claim:
                raise
            if not (str(exc) == "PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED"
                    or (verified_only and str(exc).startswith((
                        "OWNER_MARKING_", "MARKING_PREVIEW_",
                    )))):
                raise
    if verified_only:
        return None
    if claim:
        raise ValueError("ROOT_MARKING_SOURCE_STALE")

    def commit(pending):
        if key not in workspace.available_parts:
            raise ValueError(f'板件已不存在：{key}')
        if opened is not None:
            _require_current_project(host, app, workspace, project_epoch)
            _, fresh_context = current_context()
            fresh = manufacturing_api.open_physical_sheet_marking(
                key, context=fresh_context, features=workspace.features_for(key),
            )
            accepted = manufacturing_api.commit_physical_sheet_marking(fresh, opened, pending).features
        else:
            accepted = manufacturing_api.propose_operator_physical_sheet_hole_features(
                key, context, pending,
            )
        workspace.stash_features(key, accepted)
        if workspace.active_part == key:
            app._load_part_holes(key)
        app.submit_update_intent('geometry', commit=True)

    # Physical edits remain transient until confirmed.  Cancel restores
    # the session's original Features without re-submitting a stale mark.
    def validate_before_confirm(pending):
        commit(pending)

    return _present_physical_sheet_editor(
        host, key, operator_part_label(key, snapshot=payload), context, features,
        opened, validate_before_confirm, sync_callback=commit,
    )


def current_workspace_marking_source(app):
    """Transport selected workspace authority; GUI does not classify records."""
    from collections.abc import Mapping
    from ae_engine import manufacturing_api as api

    source = getattr(app, "_phase6_input_snapshot", None)
    reader = getattr(getattr(app, "designer_workspace", None), "snapshot", None)
    # The legacy independent sheet editor owns only surface + Features. It
    # has no project-owned marking capability and must retain its hole path.
    state = reader() if callable(reader) else None
    if not isinstance(source, Mapping) or not isinstance(state, Mapping):
        for readable in (source, state):
            if not isinstance(readable, Mapping):
                continue
            nested = readable.get("workspace")
            nested = nested if isinstance(nested, Mapping) else {}
            raw = readable.get(api.ROOT_MARKING_STORE_KEY, nested.get(api.ROOT_MARKING_STORE_KEY))
            if api.normalize_workspace_root_marking_store(raw)["records"]:
                raise ValueError("ROOT_MARKING_PROJECT_SOURCE_REQUIRED")
        return {}
    snapshot = dict(source)
    for field in ("existing_parts", "part_features", api.ROOT_PHYSICAL_OCCUPANCY_KEY, api.ROOT_MARKING_STORE_KEY):
        if field in state:
            snapshot[field] = state[field]
        elif field in (api.ROOT_PHYSICAL_OCCUPANCY_KEY, api.ROOT_MARKING_STORE_KEY):
            snapshot.pop(field, None)
    workspace = snapshot.get("workspace")
    if isinstance(workspace, dict):
        snapshot["workspace"] = {k: v for k, v in workspace.items()
                                 if k not in (api.ROOT_PHYSICAL_OCCUPANCY_KEY, api.ROOT_MARKING_STORE_KEY)}
    return snapshot


def _open_owner_bound_workspace_marking_editor(host, key, *, editing_context, role_features):
    from ae_engine import manufacturing_api as api
    from phase6_part_navigation import operator_part_label
    from phase6_manufacturing_adapter import build_scene_payload_for_app

    app = host.fold_designer_app
    workspace = app.designer_workspace
    project_epoch = host.project_controller.project_load_epoch

    unset = object()

    def selected_snapshot(expected_owner):
        _require_current_project(host, app, workspace, project_epoch)
        if key not in workspace.available_parts:
            raise ValueError("ROOT_MARKING_SELECTION_STALE")
        snapshot = current_workspace_marking_source(app)
        if not snapshot:
            raise ValueError("ROOT_MARKING_PROJECT_SOURCE_REQUIRED")
        if (expected_owner is not unset
                and api.resolve_workspace_physical_root_owner(snapshot, key) != expected_owner):
            raise ValueError("ROOT_MARKING_OWNER_STALE")
        return snapshot

    def read_current(expected_owner=unset, next_holes=None):
        selected_snapshot(expected_owner)
        payload = build_scene_payload_for_app(app, key)
        if next_holes is not None:
            payload["features"] = next_holes
        render = host._query_fold_designer_render_data(key, payload)
        geometry = api.selected_normal_marking_inventory(key, render)
        snapshot = selected_snapshot(expected_owner)
        if next_holes is not None:
            snapshot["part_features"] = {**snapshot.get("part_features", {}), key: next_holes}
        return snapshot, api.open_selected_ordinary_marking_modal_source(snapshot, geometry, key)

    snapshot, opened = read_current()
    draft = (api.open_workspace_owner_marking_draft(snapshot, opened)
             if opened.owner_id is not None else None)
    role_features = tuple(role_features)
    modal = (api.open_physical_sheet_marking(key, context=editing_context, features=role_features)
             if opened.output_capability == "existing_normal" else opened)

    def confirm(pending):
        def guarded_source(next_holes=None):
            state = read_current(opened.owner_id, next_holes)
            if tuple(workspace.features_for(key)) != role_features:
                raise ValueError("ROOT_MARKING_ROLE_FEATURES_STALE")
            return state

        current_snapshot, fresh = guarded_source()
        accepted = api.validate_physical_sheet_marking_draft(modal, pending)
        pending_holes = tuple(row for row in accepted if not api.is_manual_mark(row))
        pending = tuple(row for row in accepted if api.is_manual_mark(row))
        holes_changed = pending_holes != role_features
        if holes_changed and not pending and (draft is None or not draft.saved_marks):
            workspace.stash_features(key, pending_holes)
            if workspace.active_part == key:
                app._load_part_holes(key)
            app.submit_update_intent("geometry", commit=True)
            return
        prospective = guarded_source(pending_holes)[1] if holes_changed else None
        if draft is None:
            proposal = api.prepare_workspace_initial_owner_marking_commit(
                current_snapshot, opened, fresh, pending, proposed_receipt=prospective,
            )
        else:
            proposal = api.prepare_workspace_owner_marking_commit(
                current_snapshot, draft, fresh, pending, proposed_receipt=prospective,
            )
        if proposal is not None:
            workspace.commit_owner_marking_update(
                proposal, model=current_snapshot["model"],
                read_current_receipt=lambda: guarded_source()[1],
                read_proposed_receipt=(lambda: guarded_source(pending_holes)[1]) if holes_changed else None,
                pending_role_features=pending_holes if holes_changed else None,
            )
            if holes_changed:
                if workspace.active_part == key:
                    app._load_part_holes(key)
                app.submit_update_intent("geometry", commit=True)
            app._phase6_publish_live_state(force=True)
            if getattr(app, "_phase6_3d_display_mode", None) in {"corner_data", "single", "assembly"}:
                # Presentation errors cannot turn a successful committed edit
                # into a failed Confirm. Read current view after the modal exits.
                def refresh_visible_part():
                    mode = app._phase6_3d_display_mode
                    if mode == "corner_data":
                        refresh = getattr(app, "_phase6_refresh_corner_data_unfold_view", None)
                        if callable(refresh):
                            refresh()
                    elif mode in {"single", "assembly"}:
                        app.submit_update_intent("display", commit=True)

                app.root.after_idle(refresh_visible_part)

    saved_marks = draft.saved_marks if draft is not None else ()
    return _present_physical_sheet_editor(
        host, key, operator_part_label(key, snapshot=snapshot), editing_context,
        (*role_features, *saved_marks), modal, confirm,
        solid_marking_only=("circle" not in modal.allowed_tools),
    )


def _present_physical_sheet_editor(
    host, key, title, context, features, draft, confirm, *, sync_callback=None, on_close=None,
    solid_marking_only=False,
):
    editor_features = list(features)

    def sync_editor_features(pending=None):
        # The legacy no-argument callback reads the same detached list that
        # the editor received, never the older committed workspace features.
        return sync_callback(editor_features if pending is None else pending)

    return host._open_unified_hole_editor(
        key, title, context.feature_surface, context.width, context.height,
        reference_guide=context.reference_guide, feature_list_override=editor_features,
        on_confirm_features=confirm, on_close=on_close,
        sync_callback=sync_editor_features if sync_callback is not None else None,
        baseline_scene=context.render_data.scene, manual_marking_draft=draft,
        defer_workspace_sync=True, skip_cancel_sync=True,
        **({"solid_marking_only": True} if solid_marking_only else {}),
    ) or getattr(host, "last_unified_hole_editor", None)


def _require_current_project(host, app, workspace, project_epoch):
    if (host.fold_designer_app is not app or app.designer_workspace is not workspace
            or host.project_controller.project_load_epoch != project_epoch):
        raise ValueError("PHYSICAL_MARK_PROJECT_SESSION_STALE")


def open_scoped_receiving_base_plate_editor(
    host, set_index, bay_index, *, expected_owner=None, on_close=None,
):
    """Explicit scoped port; never falls back to the workspace's role-only board."""
    from ae_engine import manufacturing_api as api

    app = host.fold_designer_app
    workspace = app.designer_workspace
    project_epoch = host.project_controller.project_load_epoch

    def read_current(owner_witness):
        snapshot = app._phase6_input_snapshot
        draft = api.open_physical_sheet_marking(
            "base_plate", snapshot=snapshot, selection=(set_index, bay_index),
            expected_owner=owner_witness,
        )
        return snapshot, draft

    _, opened = read_current(expected_owner)
    context = opened.context

    def confirm(pending):
        _require_current_project(host, app, workspace, project_epoch)
        snapshot, fresh = read_current(opened.owner_id)
        result = api.commit_physical_sheet_marking(fresh, opened, pending)
        snapshot[api.SCOPED_BASE_PLATE_MARKS] = result.scoped_store
        workspace.mark_dirty()

    return _present_physical_sheet_editor(
        host, "base_plate", f"底板打標 Set{set_index + 1}/Bay{bay_index + 1}",
        context, opened.saved_marks, opened, confirm, on_close=on_close,
    )
