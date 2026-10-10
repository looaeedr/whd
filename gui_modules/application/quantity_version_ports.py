"""Application ports for feature-only quantity edits; no geometry calculation."""
from copy import deepcopy
from ae_engine.sheetmetal_features import (
    resolve_endcap_finished_face_guide, feature_surface_from_rect, RectGuide, Vec2,
)
from ae_engine.receiving_quantity_box import require_valid_quantity_features


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
        snapshot = source()
        version_id = model().selected_version_id
        features = model().features_for_version(version_id, role)
        if snapshot["model"] == "受電箱":
            # The quantity model must have an explicitly initialized common
            # box. Never silently borrow Set/Bay dimensions to fabricate one.
            from ae_engine.receiving_quantity_box import normalize_common_box, BOX_KEY
            dimensions = normalize_common_box(snapshot.get(BOX_KEY))
        else:
            dimensions = snapshot
        width, depth = float(dimensions["w"]), float(dimensions["d"])
        guide = resolve_endcap_finished_face_guide(width, depth, float(snapshot.get("t", 2)))
        surface = feature_surface_from_rect(f"{role}_finished_face", guide.min_point, guide.max_point)
        host = getattr(app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_open_unified_hole_editor"):
            raise ValueError("目前未連接既有 Hole Editor")

        def commit():
            # Capture identity, not selection: another version may be selected
            # while this modeless editor is open. A deleted ID fails closed.
            current = source()
            from phase6_quantity_model import QuantityModel
            candidate = QuantityModel.from_payload(model().snapshot())
            candidate.set_version_features(version_id, role, features)
            current["quantity"] = candidate.snapshot()
            require_valid_quantity_features(current)
            previous = model().features_for_version(version_id, role)
            edit(lambda owner: owner.set_version_features(version_id, role, features))
            if previous != features and version_id == model().selected_version_id:
                app.submit_update_intent("geometry", commit=True)

        win = host._open_unified_hole_editor(
            role, f'{version_id}／{"封頭" if role == "head" else "封尾"}',
            surface, width, depth, feature_list_override=features,
            sync_callback=commit,
            reference_guide=RectGuide(Vec2(0, 0), Vec2(width, depth), "finished_boundary"),
        )
        return win or getattr(host, "last_unified_hole_editor", None)

    return {
        "snapshot": lambda: app.designer_workspace.quantity_model.snapshot() if app.designer_workspace.quantity_model else None,
        "select": lambda version_id: edit(lambda owner: owner.select(version_id)),
        "add": lambda: edit(lambda owner: owner.add_version()),
        "delete": lambda confirmed: edit(lambda owner: owner.delete_selected(confirmed=confirmed)),
        "count": lambda value: edit(lambda owner: owner.set_piece_count(value)),
        "holes": holes,
    }
