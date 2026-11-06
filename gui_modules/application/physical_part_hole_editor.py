"""Connect physical preview identities to their existing hole owners."""


def open_workspace_sheet_editor(host, key):
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    from phase6_part_navigation import operator_part_label
    from ae_engine import manufacturing_api

    app = host.fold_designer_app
    workspace = app.designer_workspace
    if key not in workspace.available_parts:
        raise ValueError(f'板件已不存在：{key}')
    piece = manufacturing_api.is_box_body_physical_piece_key(key)
    payload = build_scene_payload_for_app(app, 'box_body' if piece else key)
    features = workspace.features_for(key)
    payload['features'] = ()  # baseline must not duplicate editable holes
    if piece:
        payload['physical_piece_features'] = {}
    render = host._query_fold_designer_render_data('box_body' if piece else key, payload)
    custom_spec = None
    if manufacturing_api.is_custom_part(key):
        custom_spec, _ = host._fold_designer_part_spec_from_payload(key, payload)
    context = manufacturing_api.resolve_physical_sheet_editor_context(
        key, render, custom_spec=custom_spec,
    )

    def commit():
        if key not in workspace.available_parts:
            raise ValueError(f'板件已不存在：{key}')
        workspace.stash_features(key, features)
        if workspace.active_part == key:
            app._load_part_holes(key)
        app.submit_update_intent('geometry', commit=True)

    return host._open_unified_hole_editor(
        key, operator_part_label(key, snapshot=payload),
        context.feature_surface, context.width, context.height,
        reference_guide=context.reference_guide, feature_list_override=features,
        sync_callback=commit, baseline_scene=context.render_data.scene,
    ) or getattr(host, 'last_unified_hole_editor', None)
