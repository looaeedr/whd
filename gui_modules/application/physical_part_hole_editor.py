"""Connect physical preview identities to their existing hole owners."""


def open_workspace_sheet_editor(host, key):
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    from phase6_part_navigation import operator_part_label, is_box_body_physical_piece_key
    from ae_engine.physical_sheet_features import physical_sheet_feature_context
    from ae_engine.custom_fold_manufacturing import custom_fold_feature_context

    app = host.fold_designer_app
    workspace = app.designer_workspace
    if key not in workspace.available_parts:
        raise ValueError(f'板件已不存在：{key}')
    piece = is_box_body_physical_piece_key(key)
    payload = build_scene_payload_for_app(app, 'box_body' if piece else key)
    features = workspace.features_for(key)
    payload['features'] = ()  # baseline must not duplicate editable holes
    if piece:
        payload['physical_piece_features'] = {}
        structure = host._query_fold_designer_render_data('box_body', payload)
        render = next((p.render_data for p in structure.pieces
                       if f'box_body:{p.role}' == key), None)
        if render is None:
            raise ValueError(f'找不到實體箱身板件：{key}')
    else:
        render = host._query_fold_designer_render_data(key, payload)
    if key.startswith('custom:'):
        spec, _ = host._fold_designer_part_spec_from_payload(key, payload)
        surface, width, height, guide = custom_fold_feature_context(spec)
    else:
        surface, width, height, guide = physical_sheet_feature_context(key, render)

    def commit():
        if key not in workspace.available_parts:
            raise ValueError(f'板件已不存在：{key}')
        workspace.stash_features(key, features)
        if workspace.active_part == key:
            app._load_part_holes(key)
        app.submit_update_intent('geometry', commit=True)

    return host._open_unified_hole_editor(
        key, operator_part_label(key, snapshot=payload), surface, width, height,
        reference_guide=guide, feature_list_override=features,
        sync_callback=commit, baseline_scene=render.scene,
    ) or getattr(host, 'last_unified_hole_editor', None)
