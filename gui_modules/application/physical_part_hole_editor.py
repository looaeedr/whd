"""Connect physical preview identities to their existing hole owners."""


def open_workspace_sheet_editor(host, key):
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

    def commit(pending=None):
        if key not in workspace.available_parts:
            raise ValueError(f'板件已不存在：{key}')
        pending = features if pending is None else pending
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


def _present_physical_sheet_editor(
    host, key, title, context, features, draft, confirm, *, sync_callback=None, on_close=None,
):
    return host._open_unified_hole_editor(
        key, title, context.feature_surface, context.width, context.height,
        reference_guide=context.reference_guide, feature_list_override=list(features),
        on_confirm_features=confirm, sync_callback=sync_callback, on_close=on_close,
        baseline_scene=context.render_data.scene, manual_marking_draft=draft,
        defer_workspace_sync=True, skip_cancel_sync=True,
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

    def read_current():
        snapshot = app._phase6_input_snapshot
        opened = api.open_physical_sheet_marking(
            "base_plate", snapshot=snapshot, selection=(set_index, bay_index),
        )
        if expected_owner is not None and opened.owner_id != expected_owner:
            raise ValueError("SCOPED_MARK_EDITOR_OWNER_STALE")
        return snapshot, opened

    _, opened = read_current()
    context = opened.context

    def confirm(pending):
        _require_current_project(host, app, workspace, project_epoch)
        snapshot, fresh = read_current()
        result = api.commit_physical_sheet_marking(fresh, opened, pending)
        snapshot[api.SCOPED_BASE_PLATE_MARKS] = result.scoped_store
        workspace.mark_dirty()

    return _present_physical_sheet_editor(
        host, "base_plate", f"底板打標 Set{set_index + 1}/Bay{bay_index + 1}",
        context, opened.saved_marks, opened, confirm, on_close=on_close,
    )
