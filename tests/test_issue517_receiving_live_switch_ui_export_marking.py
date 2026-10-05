from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="#517 exact GUI regressions require real Tk/Xvfb",
)


def _pump(root, cycles=5):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open_vault_designer():
    """Open the real production primary lifecycle, then normalize it to Vault."""
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    assert designer is not None
    try:
        designer.root.deiconify()
        designer.root.geometry("1400x900+0+0")
    except Exception:
        pass
    _pump(root, 5)

    designer.baseline_model_var.set("金庫型")
    _pump(root, 8)
    assert str(designer._phase6_input_snapshot.get("model") or "") == "金庫型"
    return tk, root, app, designer


def _close(tk, root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def _visible_back_panel_selector(designer):
    expected = ("全板", "半截", "背開孔")
    stack = [designer.root]
    matches = []
    while stack:
        widget = stack.pop()
        try:
            children = list(widget.winfo_children())
        except Exception:
            children = []
        stack.extend(children)
        try:
            values = tuple(widget.cget("values"))
        except Exception:
            continue
        if values == expected and bool(widget.winfo_ismapped()):
            matches.append(widget)
    return matches


def _mesh_bounds(triangles):
    points = [point for tri in tuple(triangles or ()) for point in tuple(tri or ())]
    assert points, "visible 3D mesh must exist"
    axes = tuple(zip(*points))
    return tuple(
        (round(min(float(v) for v in axis), 6), round(max(float(v) for v in axis), 6))
        for axis in axes
    )


def test_live_switch_with_visible_3d_replaces_vault_render_with_receiving_geometry():
    tk, root, _app, designer = _open_vault_designer()
    try:
        assert designer._phase6_3d_display_mode == "assembly"
        scene_renderer = designer.final_scene_view
        assert scene_renderer is not None
        before = _mesh_bounds(scene_renderer.last_cutting_mesh)

        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        assert str(designer._phase6_input_snapshot.get("model") or "") == "受電箱"
        assert designer._phase6_3d_display_mode == "assembly", (
            "Live-switch from a visible Vault assembly must preserve assembly mode"
        )
        assert str(designer.part_var.get()) == "組合體"
        assert bool(designer.assembly_parts_panel.winfo_ismapped())
        after = _mesh_bounds(scene_renderer.last_cutting_mesh)
        assert after != before, (
            "Visible 3D mesh bounds stayed identical after live-switch to 受電箱; "
            f"before={before!r} after={after!r}"
        )
        box_children = {
            str(key) for key in designer.designer_workspace.available_parts
            if str(key).startswith("box_body:")
        }
        assert {
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        } <= box_children
    finally:
        _close(tk, root, designer)


def test_structure_tree_selecting_back_panel_exposes_mapped_back_panel_mode_selector():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        tree = designer.structure_tree
        assert tree.exists("part:box_body:back")
        tree.selection_set("part:box_body:back")
        tree.focus("part:box_body:back")
        tree.event_generate("<<TreeviewSelect>>")
        _pump(root, 5)

        assert designer.designer_workspace.active_part == "box_body:back"
        selectors = _visible_back_panel_selector(designer)
        assert len(selectors) == 1, (
            "Selecting 後面板 through the real Structure Tree must expose exactly one "
            "mapped 後面板形式 selector in the existing visible input region"
        )
        selector = selectors[0]
        assert str(selector.get()) == "全板"

        # This is a normal product choice, not an advanced parameter.  When the
        # operator selects 後面板 it must live in the same normal input surface
        # as the Fold editor; parameter unlock must not own its reachability.
        input_host = designer.input_content_host
        assert bool(input_host.winfo_ismapped())
        parent = selector
        inside_input = False
        while parent is not None:
            if parent is input_host:
                inside_input = True
                break
            parent = getattr(parent, "master", None)
        assert inside_input, (
            "後面板形式 is mapped, but not inside the operator's normal input region"
        )

        # The same canonical product choice must also be visible from 截角資料
        # when the operator selects the physical rear panel there. This is a
        # second presentation of the same state, never a second authority.
        tree.selection_set("mode:corner_data")
        tree.focus("mode:corner_data")
        tree.event_generate("<<TreeviewSelect>>")
        _pump(root, 5)
        assert designer._phase6_3d_display_mode == "corner_data"
        assert "box_body:back" in designer.corner_data_part_buttons
        designer.corner_data_part_buttons["box_body:back"].invoke()
        _pump(root, 4)

        selectors = _visible_back_panel_selector(designer)
        assert len(selectors) == 1, (
            "Selecting 後面板 in 截角資料 must expose the canonical 後面板形式 selector"
        )
        selector = selectors[0]
        parent = selector
        inside_corner_data = False
        while parent is not None:
            if parent is designer.corner_data_panel:
                inside_corner_data = True
                break
            parent = getattr(parent, "master", None)
        assert inside_corner_data, (
            "截角資料的後面板形式 selector must live inside the existing Corner Data region"
        )
    finally:
        _close(tk, root, designer)


def test_receiving_side_back_children_keep_independent_profiles_and_back_panel_is_flat():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        wanted = (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        assert set(wanted) <= set(designer.designer_workspace.available_parts)

        signatures = []
        for key in wanted:
            profiles = designer.designer_workspace.profiles_for(key, {}) or {}
            rows = tuple(dict(row) for row in tuple(profiles.get("X") or ()))
            assert rows, f"{key} must own an independent physical-piece X profile"
            signatures.append(tuple(str(row.get("phase6_key") or "") for row in rows))
        assert len(set(signatures)) == 3, (
            "left/back/right physical pieces must not collapse into one shared editor profile"
        )

        import fold_designer_bridge as bridge
        from ae_engine.sheetmetal_drawing import LinePrimitive

        back = bridge._phase6_box_body_piece_render_data(designer, "box_body:back")
        bends = [
            primitive for primitive in tuple(back.scene.primitives)
            if isinstance(primitive, LinePrimitive)
            and str(primitive.layer).upper() == "BEND"
        ]
        assert bends == [], "Receiving rear panel is a flat plate and must not expose BEND lines"
        assert tuple(back.fold_guides or ()) == ()
    finally:
        _close(tk, root, designer)


def test_actual_gui_batch_export_matches_canonical_resolved_physical_inventory(
    tmp_path, monkeypatch
):
    tk, root, app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        # Operator asks the actual 3D Output surface to export every selectable kind.
        for var in designer.output_export_vars.values():
            var.set(True)
        _pump(root, 2)

        import gui_modules.project.export_actions as export_actions
        monkeypatch.setattr(export_actions.filedialog, "askdirectory", lambda **_kw: str(tmp_path))
        monkeypatch.setattr(export_actions.messagebox, "showinfo", lambda *_a, **_kw: None)
        monkeypatch.setattr(export_actions.messagebox, "showwarning", lambda *_a, **_kw: None)
        monkeypatch.setattr(export_actions.messagebox, "showerror", lambda *_a, **_kw: None)

        expected_root = tmp_path / "_canonical"
        expected_root.mkdir()
        resolved = designer._phase6_resolve_manufacturing_geometry()

        from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf
        expected = save_resolved_manufacturing_geometry_dxf(
            resolved, expected_root, overwrite=True
        )

        designer.output_export_button.invoke()
        _pump(root, 5)

        actual_files = tuple(
            path for path in tmp_path.glob("*.dxf")
            if path.parent == tmp_path
        )
        assert len(actual_files) == len(expected), (
            "Actual GUI DXF export is missing canonical physical parts: "
            f"actual={sorted(p.name for p in actual_files)!r} "
            f"canonical_count={len(expected)}"
        )
    finally:
        _close(tk, root, designer)


def test_receiving_assembly_view_visibly_projects_receiver_mother_plate_markings():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        # Reach assembly through the real operator navigation, not a private helper.
        tree = designer.structure_tree
        tree.selection_set("mode:assembly")
        tree.focus("mode:assembly")
        tree.event_generate("<<TreeviewSelect>>")
        _pump(root, 5)
        assert designer._phase6_3d_display_mode == "assembly"

        from ae_engine.sheetmetal_drawing import LinePrimitive
        resolved = designer._phase6_resolve_manufacturing_geometry()

        def marking_lines(render_data):
            return [
                primitive
                for primitive in tuple(render_data.scene.primitives)
                if isinstance(primitive, LinePrimitive)
                and str(primitive.layer).upper() == "MARKING"
            ]

        def receiver_joint_marking_lines(render_data):
            owned = {
                tuple(sorted((
                    (round(float(row["p1"][0]), 9), round(float(row["p1"][1]), 9)),
                    (round(float(row["p2"][0]), 9), round(float(row["p2"][1]), 9)),
                )))
                for row in tuple(dict(render_data.metadata or {}).get("joint_markings") or ())
                if str(row.get("source") or "") == "JOINT_PLACEMENT_MARKING"
            }
            return [
                primitive
                for primitive in marking_lines(render_data)
                if tuple(sorted((
                    (round(float(primitive.p1.x), 9), round(float(primitive.p1.y), 9)),
                    (round(float(primitive.p2.x), 9), round(float(primitive.p2.y), 9)),
                ))) in owned
            ]

        box = resolved.part("box_body").render_data
        pieces = {str(piece.role): piece.render_data for piece in tuple(box.pieces or ())}
        receiver_sources = {
            "left_side": receiver_joint_marking_lines(pieces["left_side"]),
            "right_side": receiver_joint_marking_lines(pieces["right_side"]),
            "head": receiver_joint_marking_lines(resolved.part("head").render_data),
        }
        divider_marks = []
        for part in tuple(resolved.parts or ()):
            if str(part.part_key).startswith("box_body:divider:"):
                divider_marks.extend(marking_lines(part.render_data))

        assert len(receiver_sources["left_side"]) == 1
        assert len(receiver_sources["right_side"]) == 1
        assert len(receiver_sources["head"]) == 1
        assert len(divider_marks) == 2
        assert sum(len(rows) for rows in receiver_sources.values()) + len(divider_marks) == 5

        for frame_id in (
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
        ):
            assert receiver_joint_marking_lines(resolved.part(frame_id).render_data) == [], (
                "#1050 supersedes frame-owned #509 MARKING; the receiver mother "
                f"plate must own the contact line instead: {frame_id}"
            )

        scene_renderer = designer.final_scene_view
        assert scene_renderer is not None
        ax = scene_renderer.renderer.ax3d
        visible_marks = [
            line for line in tuple(ax.lines)
            if str(line.get_color()).lower() == "#f59e0b"
        ]
        assert len(visible_marks) >= 5, (
            "All five canonical receiver-owned contact MARKING lines exist in "
            "FinalScene/DXF but are not visibly projected in Receiving assembly 3D"
        )
        assert all(float(line.get_zorder()) >= 10.0 for line in visible_marks)
        assert all(float(line.get_linewidth()) >= 1.8 for line in visible_marks)
    finally:
        _close(tk, root, designer)


def _mapped_widget_texts(root_widget):
    stack = [root_widget]
    texts = []
    while stack:
        widget = stack.pop()
        try:
            stack.extend(list(widget.winfo_children()))
        except Exception:
            pass
        try:
            if not bool(widget.winfo_ismapped()):
                continue
        except Exception:
            continue
        try:
            value = str(widget.cget("text") or "").strip()
        except Exception:
            value = ""
        if value:
            texts.append(value)
    return tuple(texts)


def _select_box_body_through_tree(designer, root):
    tree = designer.structure_tree
    assert tree.exists("part:box_body")
    tree.selection_set("part:box_body")
    tree.focus("part:box_body")
    tree.event_generate("<<TreeviewSelect>>")
    _pump(root, 6)
    assert designer.designer_workspace.active_part == "box_body"


def test_receiving_operator_controls_are_visibly_chinese_above_fold_notebook():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        _select_box_body_through_tree(designer, root)

        frame = designer.receiving_set_bay_control
        assert bool(frame.winfo_ismapped()), "Receiving control frame is still hidden"
        packed = list(designer.input_content_host.pack_slaves())
        assert frame in packed and designer.bend_ui.nb in packed
        assert packed.index(frame) < packed.index(designer.bend_ui.nb), (
            "Receiving controls must be inserted before the expanding fold notebook"
        )

        texts = _mapped_widget_texts(frame)
        for expected in ("開關", "＋層", "第1層", "1連", "－連", "＋連", "預覽"):
            assert expected in texts, f"operator-visible Receiving text missing: {expected!r}; got={texts!r}"
        assert not any("Layer" in text or "Connection" in text for text in texts), texts
    finally:
        _close(tk, root, designer)


def test_receiving_layer_connection_config_edits_do_not_redraw_3d_canvas():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 10)
        _select_box_body_through_tree(designer, root)
        _pump(root, 10)

        canvas = designer.renderer.canvas
        calls = {"draw": 0, "draw_idle": 0}
        original_draw = canvas.draw
        original_draw_idle = canvas.draw_idle

        def blocked_draw(*_args, **_kwargs):
            calls["draw"] += 1
            return None

        def blocked_draw_idle(*_args, **_kwargs):
            calls["draw_idle"] += 1
            return None

        canvas.draw = blocked_draw
        canvas.draw_idle = blocked_draw_idle
        try:
            designer.receiving_layer_controls.add_layer_button.invoke()
            _pump(root, 5)
            rows = tuple(
                getattr(
                    designer.receiving_layer_controls.layer_host,
                    "_phase6_receiving_layer_rows",
                    (),
                )
                or ()
            )
            assert len(rows) >= 2
            rows[0]["plus_button"].invoke()
            _pump(root, 5)
        finally:
            canvas.draw = original_draw
            canvas.draw_idle = original_draw_idle

        assert calls == {"draw": 0, "draw_idle": 0}, (
            "＋層／＋連 are configuration-only and must not redraw/reload 3D: "
            f"{calls!r}"
        )
    finally:
        _close(tk, root, designer)


def test_parameter_lock_is_direct_canvas_overlay_not_layout_row():
    tk, root, _app, designer = _open_vault_designer()
    try:
        _pump(root, 6)
        canvas_widget = designer.renderer.canvas.get_tk_widget()
        button = designer.parameter_lock_button
        assert button.master is canvas_widget
        assert button.winfo_manager() == "place"
        assert bool(button.winfo_ismapped())
        assert button.winfo_y() <= 24
        assert button.winfo_x() >= (
            canvas_widget.winfo_width() - button.winfo_width() - 24
        )
    finally:
        _close(tk, root, designer)

def test_receiving_preview_uses_real_current_3d_mesh_per_connection_and_lock_holes():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        _select_box_body_through_tree(designer, root)
        _pump(root, 6)

        source_mesh = tuple(designer.final_scene_view.last_cutting_mesh or ())
        assert source_mesh, "Receiving current 3D mesh must exist before preview"

        rows = tuple(
            getattr(
                designer.receiving_layer_controls.layer_host,
                "_phase6_receiving_layer_rows",
                (),
            )
            or ()
        )
        assert rows
        rows[0]["plus_button"].invoke()
        rows[0]["plus_button"].invoke()
        _pump(root, 4)

        import fold_designer_bridge as bridge
        preview_payload = bridge._phase6_composition(designer).receiving_layer_preview_payload(
            bridge.__dict__,
            0,
        )
        assert preview_payload["connection_count"] == 3
        assert len(preview_payload["connection_meshes"]) == 3
        assert tuple(preview_payload["connection_meshes"][0]) == source_mesh, (
            "Preview must replicate the current resolved CUTTING mesh, not draw a simplified box"
        )
        assert len(preview_payload["lock_circles"]) > 0, (
            "3連 preview must include canonical mating/lock hole circles between adjacent cabinets"
        )

        rows = tuple(
            getattr(
                designer.receiving_layer_controls.layer_host,
                "_phase6_receiving_layer_rows",
                (),
            )
            or ()
        )
        rows[0]["preview_button"].invoke()
        _pump(root, 6)

        preview_windows = [
            child
            for child in designer.root.winfo_children()
            if hasattr(child, "_phase6_receiving_preview_canvas")
        ]
        assert len(preview_windows) == 1
        win = preview_windows[0]
        assert win._phase6_receiving_preview_connection_count == 3
        assert win._phase6_receiving_preview_mesh_count == 3
        assert win._phase6_receiving_preview_lock_circle_count > 0
        assert win._phase6_receiving_preview_feature_segment_count > 0

        canvas_widget = win._phase6_receiving_preview_canvas.get_tk_widget()
        assert bool(canvas_widget.winfo_ismapped())
        assert canvas_widget.winfo_width() > 100
        assert canvas_widget.winfo_height() > 100
        assert "Radiobutton" not in {
            str(child.winfo_class())
            for child in win.winfo_children()
        }
        win.destroy()
    finally:
        _close(tk, root, designer)
