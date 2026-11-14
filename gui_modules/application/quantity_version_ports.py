"""Application ports for feature-only quantity edits; no geometry calculation."""
from copy import deepcopy
from ae_engine import manufacturing_api


def quantity_ports(composition, namespace):
    app = composition.app

    def model():
        value = app.designer_workspace.quantity_model
        if value is None:
            raise ValueError("目前不是數量模式")
        return value

    def source():
        snapshot = deepcopy(app._phase6_input_snapshot)
        snapshot.update(deepcopy(app._settings_values))
        snapshot.update(deepcopy(app._phase6_box_whd))
        snapshot.update(app.designer_workspace.snapshot())
        snapshot["model"] = app.baseline_model_var.get()
        return snapshot

    def hole_source():
        """Use the same physical W/H/D/T precedence as the manufacturing request.

        Navigation may remain available on incomplete historic Quantity data;
        opening or committing an actual physical hole must not substitute a
        stale Settings thickness for an explicitly saved project thickness.
        """
        snapshot = source()
        physical = manufacturing_api.project_operator_manufacturing_request_snapshot(
            app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
        )
        for axis in ("w", "h", "d", "t"):
            if axis in physical:
                snapshot[axis] = physical[axis]
        return snapshot

    def changed():
        payload = model().snapshot()
        app._phase6_input_snapshot["active_mode"] = "quantity"
        app._phase6_input_snapshot["quantity"] = payload
        active = app.designer_workspace.active_part
        if active in {"head", "tail"}:
            app._load_part_holes(active)
        # The version model is the sole owner. Selection/count updates and
        # 2D editors save only working state; project persistence is manual.
        composition.publish_live_state(namespace, force=True)
        return payload

    def edit(action):
        before = model().snapshot()
        result = action(model())
        if before != model().snapshot():
            changed()
        return result

    def holes(role):
        if role not in {"head", "tail"}:
            raise ValueError("孔型版本只覆寫封頭／封尾 Features")
        # Missing editor is an operator/UI capability error, not a reason to
        # resolve or fabricate physical manufacturing dimensions first.
        host = getattr(app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_open_unified_hole_editor"):
            raise ValueError("目前未連接既有 Hole Editor")
        snapshot = hole_source()
        version_id = model().selected_version_id
        features = model().features_for_version(version_id, role)
        geometry = manufacturing_api.project_operator_quantity_endcap_hole_editor_geometry(
            snapshot, role=role,
        )
        width, depth = geometry.width, geometry.height

        def commit():
            # Capture identity, not selection: another version may be selected
            # while this modeless editor is open. A deleted ID fails closed.
            changed_holes = edit(
                lambda owner: manufacturing_api.commit_operator_quantity_version_holes(
                    hole_source(), owner, version_id=version_id, role=role,
                    features=features,
                )
            )
            if changed_holes and version_id == model().selected_version_id:
                app.submit_update_intent("geometry", commit=True)

        win = host._open_unified_hole_editor(
            role, f'{version_id}／{"封頭" if role == "head" else "封尾"}',
            geometry.surface, width, depth, feature_list_override=features,
            sync_callback=commit,
            reference_guide=geometry.reference_guide,
        )
        return win or getattr(host, "last_unified_hole_editor", None)

    return {
        "snapshot": lambda: (
            manufacturing_api.project_operator_quantity_version_controls(
                app.designer_workspace.quantity_model.snapshot()
            )
            if app.designer_workspace.quantity_model else None
        ),
        "select": lambda version_id: edit(
            lambda owner: manufacturing_api.commit_operator_quantity_version_action(
                source(), owner, action="select", version_id=version_id,
            )
        ),
        "add": lambda: edit(
            lambda owner: manufacturing_api.commit_operator_quantity_version_action(
                source(), owner, action="add",
                version_id=owner.selected_version_id,
            )
        ),
        "delete": lambda confirmed: edit(
            lambda owner: manufacturing_api.commit_operator_quantity_version_action(
                source(), owner, action="delete",
                version_id=owner.selected_version_id, confirmed=confirmed,
            )
        ),
        "count": lambda value: edit(
            lambda owner: manufacturing_api.commit_operator_quantity_version_action(
                source(), owner, action="count",
                version_id=owner.selected_version_id, piece_count=value,
            )
        ),
        "holes": holes,
    }
