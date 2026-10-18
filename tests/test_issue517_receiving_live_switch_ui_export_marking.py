from __future__ import annotations

import os
from pathlib import Path

import pytest


# Windows has native Tk and does not set the Unix DISPLAY environment variable.
# Keep Linux's explicit X display requirement; on Windows run real GUI tests and
# let Tk startup fail visibly if no desktop exists rather than silently skip.
pytestmark = pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
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

def _assembly_part_signatures(designer):
    import fold_designer_bridge as bridge

    data = bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
    rows = {}
    for part in tuple(data.assembly_parts or ()):
        render_data = part.render_data
        material = getattr(render_data, "material", None)
        material_bounds = None
        if material is not None and not getattr(material, "is_empty", True):
            material_bounds = tuple(round(float(v), 3) for v in material.bounds)
        piece_bounds = []
        for piece in tuple(getattr(render_data, "pieces", ()) or ()):
            piece_material = getattr(getattr(piece, "render_data", None), "material", None)
            if piece_material is not None and not getattr(piece_material, "is_empty", True):
                piece_bounds.append(
                    (
                        str(getattr(piece, "role", "") or ""),
                        tuple(round(float(v), 3) for v in piece_material.bounds),
                    )
                )
        rows[str(part.part_key)] = {
            "placement": str(part.placement),
            "offset": tuple(round(float(v), 3) for v in tuple(part.offset or ())),
            "x": tuple(round(float(seg.get("len", 0.0)), 3) for seg in tuple(part.x_profile or ())),
            "y": tuple(round(float(seg.get("len", 0.0)), 3) for seg in tuple(part.y_profile or ())),
            "material": material_bounds,
            "pieces": tuple(piece_bounds),
        }
    return rows


def test_live_switch_visible_3d_round_trip_vault_receiving_vault_replaces_geometry_both_ways():
    tk, root, _app, designer = _open_vault_designer()
    try:
        assert designer._phase6_3d_display_mode == "assembly"
        scene_renderer = designer.final_scene_view
        assert scene_renderer is not None
        before = _mesh_bounds(scene_renderer.last_cutting_mesh)
        before_parts = _assembly_part_signatures(designer)
        assert not bool(designer.box_body_piece_selector.winfo_ismapped())

        designer.baseline_model_var.set("受電箱")
        _pump(root, 10)

        assert str(designer._phase6_input_snapshot.get("model") or "") == "受電箱"
        assert designer._phase6_3d_display_mode == "assembly"
        assert str(designer.part_var.get()) == "組合體"
        assert bool(designer.assembly_parts_panel.winfo_ismapped())
        assert designer._phase6_assembly_panel_owner.multi_settings_button.winfo_ismapped()
        assert not bool(designer.box_body_piece_selector.winfo_ismapped()), (
            "Assembly mode must not re-pack 左側板/後面板/右側板 child tabs"
        )
        receiving = _mesh_bounds(scene_renderer.last_cutting_mesh)
        assert receiving != before, (
            "Visible 3D mesh bounds stayed identical after live-switch to 受電箱; "
            f"before={before!r} receiving={receiving!r}"
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

        designer.baseline_model_var.set("金庫型")
        _pump(root, 10)

        assert str(designer._phase6_input_snapshot.get("model") or "") == "金庫型"
        assert designer._phase6_3d_display_mode == "assembly"
        assert str(designer.part_var.get()) == "組合體"
        assert scene_renderer.cutting_mesh_error is None
        restored = _mesh_bounds(scene_renderer.last_cutting_mesh)
        restored_parts = _assembly_part_signatures(designer)
        assert restored == before, (
            "受電箱→金庫型 did not restore the original Vault assembly mesh; "
            f"before={before!r} receiving={receiving!r} restored={restored!r}; "
            f"before_parts={before_parts!r}; restored_parts={restored_parts!r}"
        )
        assert not any(
            str(key).startswith("box_body:")
            for key in designer.designer_workspace.available_parts
        )
        assert not bool(designer.box_body_piece_selector.winfo_ismapped())
        assert not bool(designer.receiving_set_bay_control.winfo_ismapped())
        assert not designer._phase6_assembly_panel_owner.multi_settings_button.winfo_ismapped()
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
        # Operator has explicitly moved multi-box settings out of BoxBody.
        assert not _visible_back_panel_selector(designer)
        assert not designer.receiving_set_bay_control.winfo_ismapped()
        assert str(designer.back_panel_mode_var.get()) == "全板"

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
        # A production bottom plate needs an explicitly selected physical
        # variant. The three sample drawings are candidates, not a universal
        # default. This fixture chooses a real physical spec before batch DXF.
        from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
        designer._phase6_input_snapshot["receiving_base_plate"] = {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 280.0, "shrink_top": 20.0, "shrink_bottom": 20.0,
            "shrink_left": 85.0, "shrink_right": 85.0, "bend": 20.0,
        }

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
        # Equal file counts are not manufacturing acceptance. Reopen the
        # ACTUAL operator-exported DXFs and use the canonical verifier to
        # compare filenames, entity/layer counts, CUTTING material, BEND
        # guides and CUTTING holes against the same committed physical parts.
        # This detects wrong shapes even when GUI export count looks right.
        from ae_engine.manufacturing_api import (
            verify_saved_resolved_manufacturing_geometry_dxf,
        )
        verified = verify_saved_resolved_manufacturing_geometry_dxf(
            resolved, tmp_path
        )
        assert verified.ok, [
            (issue.part_id, issue.category, issue.detail)
            for issue in verified.issues
        ]
        assert len(verified.part_results) == len(expected)
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

        # Each actual side plate now carries the pre-existing inner-frame
        # contact AND the newly verified Divider terminal contact.
        for role in ("left_side", "right_side"):
            rows = tuple(dict(pieces[role].metadata or {}).get("joint_markings") or ())
            assert {row["attached_part_id"] for row in rows} == {
                f"inner_door:upper:{role.split('_')[0]}_frame",
                "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
            }
            assert len(receiver_sources[role]) == 2
        assert len(receiver_sources["head"]) == 1
        assert len(divider_marks) == 2
        assert sum(len(rows) for rows in receiver_sources.values()) + len(divider_marks) == 7

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
        assert len(visible_marks) >= 7, (
            "All seven canonical receiver-owned contact MARKING lines exist in "
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

        # BoxBody must remain focused on sheet-metal inputs only.
        assert not designer.receiving_set_bay_control.winfo_ismapped()
        assert not designer.receiving_mode_controls.frame.winfo_manager()
        # The single receiving operator entry is in Assembly.
        import fold_designer_bridge as bridge
        bridge._phase6_show_assembly(designer)
        _pump(root, 5)
        owner = designer._phase6_assembly_panel_owner
        assert owner.multi_settings_button.winfo_ismapped()
        win = bridge._phase6_open_receiving_multi_settings(designer)
        _pump(root, 3)
        assert win.title() == "多連設定"
        # The main Quantity mode was removed; Set/Bay is selected on entry.
        mode_buttons = win._receiving_multi_mode_controls.winfo_children()
        assert not mode_buttons
        assert win._receiving_multi_mode_var.get() == "set_bay"
        _pump(root, 3)
        # Only user-specified elements are exposed, no legacy editor or
        # extra brand/common-box/quantity-version controls.
        texts = _mapped_widget_texts(win)
        for expected in (
            "－套", "＋套", "第1套", "－連", "＋連", "套用",
        ):
            assert expected in texts, (expected, texts)
        assert [w.cget("text") for w in win._receiving_multi_set_buttons] == [
            "－套", "＋套"
        ]
        for unwanted in ("開關", "共用箱體", "套用品牌", "件數"):
            assert unwanted not in texts, (unwanted, texts)
        assert win._receiving_multi_mode_var.get() == "set_bay"
        assert win._receiving_multi_applied["set_index"] is None
        assert len(win._receiving_multi_canvas._receiving_bay_hitboxes) == 1
        win.destroy()
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
            remove = designer.receiving_layer_controls.remove_layer_button
            assert "disabled" in remove.state()
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
            assert "disabled" not in remove.state()
            rows[0]["plus_button"].invoke()
            _pump(root, 5)
            remove.invoke()
            _pump(root, 5)
            rows = tuple(
                getattr(
                    designer.receiving_layer_controls.layer_host,
                    "_phase6_receiving_layer_rows",
                    (),
                )
                or ()
            )
            assert len(rows) == 1
            assert "disabled" in remove.state()
        finally:
            canvas.draw = original_draw
            canvas.draw_idle = original_draw_idle

        assert calls == {"draw": 0, "draw_idle": 0}, (
            "＋套／－套／＋連 are configuration-only and must not redraw/reload 3D: "
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

def test_receiving_preview_uses_real_current_2d_scenes_per_connection_and_lock_holes():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        _select_box_body_through_tree(designer, root)
        _pump(root, 6)


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
        request = preview_payload["render_request"]
        assert request.part_key == "assembly"
        bay_requests = tuple(preview_payload["bay_requests"])
        assert len(bay_requests) == 3
        rendered_parts = tuple(part for bay in bay_requests for part in bay.render_data.assembly_parts)
        assert len(rendered_parts) == 3 * len(preview_payload["assembly_part_keys"])
        assert {"box_body", "head", "tail"} <= set(preview_payload["assembly_part_keys"])
        assert len(preview_payload["assembly_part_keys"]) >= 5, (
            "Preview must resolve the complete assembly, not only the current input part"
        )
        assert preview_payload["lock_circles"] == (), "接合孔必須由 canonical features 產生，不能另畫 overlay"
        from ae_engine.sheetmetal_drawing import CirclePrimitive
        for bay_request in bay_requests:
            box = next(part.render_data for part in bay_request.render_data.assembly_parts if part.part_key == "box_body")
            lock_holes = [primitive for piece in box.pieces for primitive in piece.render_data.scene.primitives
                          if isinstance(primitive, CirclePrimitive)
                          and primitive.layer == "CUTTING"
                          and primitive.source_type == "receiving_joint_side_lock"]
            assert lock_holes, "每連實體側板必須包含可匯出 DXF 的 canonical 接合孔"

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
        assert win._phase6_receiving_preview_mesh_count == 0
        assert win._phase6_receiving_preview_uses_final_scene_renderer is False
        assert win._phase6_receiving_preview_canvas.figure.axes[0].name == 'rectilinear'
        assert len(win._phase6_receiving_preview_2d.requests) == 3
        assert win._phase6_receiving_preview_lock_circle_count == 0
        assert win._phase6_receiving_preview_feature_segment_count == 0
        assert win.title() == "第1套設定"

        canvas_widget = win._phase6_receiving_preview_canvas.get_tk_widget()
        assert bool(canvas_widget.winfo_ismapped())
        assert canvas_widget.winfo_width() > 100
        assert canvas_widget.winfo_height() > 100
        assert canvas_widget.winfo_width() >= int(win.winfo_width() * 0.75)
        assert canvas_widget.winfo_height() >= int(win.winfo_height() * 0.55)
        preview_texts = _mapped_widget_texts(win)
        assert not any(
            "box_body:" in text or "inner_door:" in text or "indicator_box:" in text
            for text in preview_texts
        ), preview_texts
        assert "Radiobutton" not in {
            str(child.winfo_class())
            for child in win.winfo_children()
        }
        win.destroy()
    finally:
        _close(tk, root, designer)


def test_primary_multi_settings_matches_mode_and_first_connection_is_fast():
    import time
    import fold_designer_bridge as bridge
    from gui_modules.application.fold_designer_composition_receiving import _current_mode_snapshot
    from phase6_manufacturing_adapter import build_manufacturing_cache_key
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set('受電箱')
        _pump(root, 8)
        composition = bridge._phase6_composition(designer)
        current = _current_mode_snapshot(composition, vars(bridge))['active_mode']
        win = bridge._phase6_open_receiving_multi_settings(designer)
        _pump(root, 4)
        assert win._receiving_multi_mode_var.get() == "set_bay"
        assert win._receiving_multi_applied['mode'] == "set_bay"
        assert _current_mode_snapshot(composition, vars(bridge))['active_mode'] == 'set_bay'
        assert win._receiving_multi_mode_controls.winfo_children() == []
        row = win._receiving_multi_rows_host.winfo_children()[0]
        plus = next(button for button in row.winfo_children()
                    if button.winfo_class() == 'TButton' and button.cget('text') == '＋連')
        counts = []
        durations = []
        for _ in range(2):
            started = time.perf_counter()
            plus.invoke()
            _pump(root, 4)
            durations.append(time.perf_counter() - started)
            counts.append(composition.receiving_switch_adapter(vars(bridge)).connection_counts()[0])
        assert counts == [2, 3]
        assert max(durations) < 1.0, durations
        # Exact Windows UAT repro: topology changed, then close immediately.
        # The modal click path stays fast; the one required manufacturing flush
        # happens at the close boundary before Assembly is remounted.
        win._receiving_multi_close()
        _pump(root, 6)
        assert designer._phase6_last_resolved_manufacturing_signature == (
            build_manufacturing_cache_key(designer).fingerprint
        )
        assert designer.final_scene_view.cutting_mesh_error is None
        assert designer.final_scene_view.last_cutting_mesh
        assert designer.part_var.get() == "組合體"
    finally:
        _close(tk, root, designer)


def test_issue1796_multi_dimension_change_close_commits_finalscene():
    """Real Tk: change one Bay W/H/D and close immediately; Assembly consumes the new receipt."""
    import fold_designer_bridge as bridge
    from phase6_manufacturing_adapter import build_manufacturing_cache_key

    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        win = bridge._phase6_open_receiving_multi_settings(designer)
        _pump(root, 4)
        assert win._receiving_multi_apply(0) is True
        values = win._receiving_dimension_group_input
        values["width"].set("820")
        values["height"].set("1600")
        values["depth"].set("350")
        values["count"].set("1")

        # Do not pump Tk between confirmation and close. This is the reported
        # operator sequence that previously let Assembly race stale geometry.
        assert win._receiving_dimension_group_confirm() is True
        win._receiving_multi_close()
        _pump(root, 6)

        assert float(designer._phase6_box_whd["w"]) == 820.0
        assert float(designer.v_w.get()) == 820.0
        assert float(designer._phase6_last_w) == 820.0
        width_core = next(
            segment for segment in designer.state.profiles_vault["箱身"]
            if segment.get("core") == "W"
        )
        from phase6_fold_profiles import engine_segment_length_to_ui
        assert float(engine_segment_length_to_ui(width_core)) == 820.0
        # Bottom fixing-plate applicability/manufacturing belongs to #1503
        # and is intentionally outside this #1796 modal/FinalScene regression.
        assert designer._phase6_last_resolved_manufacturing_signature == (
            build_manufacturing_cache_key(designer).fingerprint
        )
        assert designer.final_scene_view.cutting_mesh_error is None
        assert designer.final_scene_view.last_cutting_mesh
        assert designer.part_var.get() == "組合體"
    finally:
        _close(tk, root, designer)


def test_primary_selected_version_popup_draws_real_geometry_without_live_mutation():
    from copy import deepcopy
    import fold_designer_bridge as bridge
    from ae_engine.receiving_hole_candidates import create_candidate
    from gui_modules.application.fold_designer_composition_receiving import _switch_mode
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set('受電箱')
        _pump(root, 8)
        composition = bridge._phase6_composition(designer)
        _switch_mode(composition, vars(bridge), 'set_bay')
        designer._phase6_input_snapshot['receiving_hole_candidates'], _version = create_candidate(None, 'head', [])
        win = bridge._phase6_open_receiving_multi_settings(designer)
        _pump(root, 4)
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate('<<ListboxSelect>>')
        _pump(root, 2)
        before = deepcopy(designer._phase6_input_snapshot)
        chooser = win._receiving_multi_candidate_combos['head']
        chooser.set('版本一')
        chooser.event_generate('<<ComboboxSelected>>')
        _pump(root, 4)
        preview = win._receiving_multi_real_preview
        assert preview['view'].tiles, preview['status'].get()
        widget = preview['view'].canvas.get_tk_widget()
        assert widget.winfo_ismapped() and widget.winfo_width() > 100
        assert preview['view'].ax.collections
        assert designer._phase6_input_snapshot == before
        win._receiving_multi_close_real_preview()
        win._receiving_multi_close()
    finally:
        _close(tk, root, designer)



def test_primary_receiving_inner_door_is_visible_selectable_and_real_panel_without_multi_settings():
    """#1702: production main-window entry, not the legacy 2D calculator.

    A generated available_parts entry is not enough: the user must SEE the
    sheet in the real part menu and Assembly and SELECT its manufacturing scene.
    """
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 10)
        physical = "inner_door:upper:panel"
        present = tuple(designer.designer_workspace.available_parts)
        assert physical in present, {
            "stage": "PRIMARY_WORKSPACE",
            "present": present,
            "inner_doors": designer._phase6_input_snapshot.get("inner_doors"),
            "multi_door_enabled": designer._phase6_input_snapshot.get("multi_door_enabled"),
        }

        # User-visible part menu, not just the hidden model/metadata.
        menu = designer.part_choice_menu
        labels = tuple(str(menu.entrycget(i, "label")) for i in range(int(menu.index("end")) + 1))
        assert "上層內門門板" in labels, {
            "stage": "PRIMARY_MENU",
            "labels": labels,
            "present": present,
        }
        owner = designer._phase6_assembly_panel_owner
        assert physical in owner.visible_vars, {
            "stage": "PRIMARY_ASSEMBLY",
            "rendered": tuple(owner.visible_vars),
            "present": present,
        }
        assert str(owner.checkbuttons[physical].cget("text")) == "上層內門門板"

        # Exercise the actual operator menu action and renderer authority.
        menu.invoke(labels.index("上層內門門板"))
        _pump(root, 6)
        assert designer.designer_workspace.active_part == physical
        assert designer.active_part_key == physical
        assert str(designer.part_var.get()) == "上層內門門板"
        render = designer._scene_query_callback(physical, designer._phase6_input_snapshot)
        assert render is not None
        assert render.metadata["stable_id"] == physical
        assert render.material.area > 0
        assert render.fold_guides
        assert any(str(item.layer).upper() == "CUTTING" for item in render.scene.primitives)
    finally:
        _close(tk, root, designer)


def test_receiving_part_switch_back_to_assembly_still_renders_true_3d():
    """A standalone sheet preview must not poison the following Assembly view."""
    import fold_designer_bridge as bridge
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        renderer = designer.final_scene_view
        available = tuple(designer.designer_workspace.available_parts)
        # Receiving's outer Door is dynamically split into door_cN_rN,
        # so test a REAL available Door, not Vault's standalone `door` key.
        outer_door = next(
            key for key in available
            if key == "door" or key.startswith("door_c")
        )
        side = "box_body:left_side" if "box_body:left_side" in available else "box_body"
        for part in (outer_door, side, "head"):
            assert part in available
            designer.activate_part(part)
            _pump(root, 3)
            assert renderer.cutting_mesh_error is None, (
                part, renderer.cutting_mesh_error
            )
            bridge._phase6_show_assembly(designer)
            _pump(root, 5)
            assert designer._phase6_3d_display_mode == "assembly"
            assert designer.part_var.get() == "組合體"
            assert renderer.cutting_mesh_error is None, (
                part, renderer.cutting_mesh_error
            )
            assert renderer.last_cutting_mesh, (
                "組合體 must not be blank after returning from a standalone 3D part"
            )
    finally:
        _close(tk, root, designer)


def test_receiving_dynamic_outer_doors_retain_real_nameplate_mount_cutting():
    """Certified Vault nameplate mounts must survive Receiving's split Door topology."""
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    from shapely.geometry import Point
    import fold_designer_bridge as bridge

    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 7)
        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        doors = {
            part.part_key: part.render_data
            for part in resolved.parts
            if part.part_key.startswith("door_c")
        }
        assert set(doors) == {"door_c1_r1", "door_c1_r2"}
        for part_key, data in doors.items():
            mounts = [
                primitive for primitive in data.scene.primitives
                if isinstance(primitive, CirclePrimitive)
                and str(getattr(primitive, "source_type", "")) == "nameplate_mount"
                and str(getattr(primitive, "layer", "")).upper() == "CUTTING"
            ]
            assert len(mounts) == 2, (part_key, mounts)
            assert {
                str(getattr(mount, "source_id", "")) for mount in mounts
            } == {"door:nameplate_mount:left", "door:nameplate_mount:right"}
            # They are actual through-holes in manufacturing material, not
            # preview-only decoration or an overlay added by Matplotlib.
            for mount in mounts:
                center = Point(float(mount.center.x), float(mount.center.y))
                assert not data.material.covers(center), (part_key, mount.center)
    finally:
        _close(tk, root, designer)


def test_receiving_modal_first_entry_defers_baselines_and_close_mounts_assembly(monkeypatch):
    """Opening with no Set selection must neither stretch DXF nor hide Assembly."""
    import fold_designer_bridge as bridge
    tk, root, app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 6)
        # Seed the exact committed scene that the real Assembly 3D uses.
        bridge._phase6_resolve_manufacturing_geometry(designer)
        calls = []
        old = app._door_layout_baseline_scene

        def count_baseline(*args, **kwargs):
            calls.append((args, kwargs))
            return old(*args, **kwargs)

        monkeypatch.setattr(app, "_door_layout_baseline_scene", count_baseline)
        for button in (
            bridge._phase6_open_receiving_single_settings,
            bridge._phase6_open_receiving_multi_settings,
        ):
            calls.clear()
            win = button(designer)
            _pump(root, 3)
            assert calls == [], "unapplied modal must not parse Door DXF"
            assert win._receiving_multi_canvas.find_withtag("receiving_nameplate"), (
                "cached real Door nameplate mounts must show on initial sketch"
            )
            assert win._receiving_multi_applied["set_index"] is None
            # Reproduce the reported desync: mode/selection says Assembly,
            # but the shared slot still shows Box Body's input content.
            bridge._phase6_mount_shared_content(designer, "single")
            assert designer.input_content_host.winfo_manager()
            win._receiving_multi_close()
            _pump(root, 2)
            assert designer._phase6_3d_display_mode == "assembly"
            assert designer.part_var.get() == "組合體"
            assert designer.assembly_parts_panel.winfo_manager()
            assert not designer.input_content_host.winfo_manager()
    finally:
        _close(tk, root, designer)


def test_issue1796_real_tk_vault_receiving_single_setbay_modal_roundtrip_without_orphans(
    monkeypatch, record_property,
):
    """Cross-mode GUI acceptance: receipt, visible Assembly, focus and cleanup stay in sync."""
    import time
    from tkinter import messagebox
    import fold_designer_bridge as bridge
    from phase6_manufacturing_adapter import build_manufacturing_cache_key

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError(
            f"unexpected blocking Tk dialog during #1796 mode roundtrip: {args!r} {kwargs!r}"
        )

    for name in ("showwarning", "showerror", "showinfo"):
        monkeypatch.setattr(messagebox, name, unexpected_dialog)

    tk, root, _app, designer = _open_vault_designer()
    rows = []
    try:
        scene = designer.final_scene_view
        vault_mesh = _mesh_bounds(scene.last_cutting_mesh)
        vault_parts = _assembly_part_signatures(designer)

        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        # Baseline switching may correctly preserve the active Quantity
        # session; enter Set/Bay via the actual operator modal, not an
        # invented default-mode assumption.
        if designer.designer_workspace.active_mode != "set_bay":
            initial = bridge._phase6_open_receiving_multi_settings(designer)
            try:
                _pump(root, 4)
                assert designer.designer_workspace.active_mode == "set_bay"
            finally:
                if initial.winfo_exists():
                    initial._receiving_multi_close()
                _pump(root, 3)
        assert designer.designer_workspace.active_mode == "set_bay"
        assert designer.root.grab_current() is None
        receiving_mesh = _mesh_bounds(scene.last_cutting_mesh)
        receiving_parts = _assembly_part_signatures(designer)
        assert receiving_mesh != vault_mesh

        for expected_mode, opener in (
            ("quantity", bridge._phase6_open_receiving_single_settings),
            ("set_bay", bridge._phase6_open_receiving_multi_settings),
        ):
            started = time.perf_counter()
            window = opener(designer)
            try:
                _pump(root, 5)
                assert window.winfo_exists()
                assert designer.designer_workspace.active_mode == expected_mode
                assert window._receiving_multi_applied["mode"] == expected_mode
                # Do not force a new solve just to pass the test. The existing
                # committed manufacturing receipt must match the working state.
                current_key = build_manufacturing_cache_key(designer).fingerprint
                assert current_key == designer._phase6_last_resolved_manufacturing_signature
                assert designer._phase6_last_resolved_manufacturing_geometry is not None
                assert _assembly_part_signatures(designer)
            finally:
                if window.winfo_exists():
                    window._receiving_multi_close()
                _pump(root, 3)
            assert designer.root.grab_current() is None
            assert getattr(designer.root, "_receiving_multi_settings_window", None) is None
            scheduler = designer._phase6_update_scheduler
            assert not scheduler.dirty
            assert scheduler._after_job is None
            assert designer.part_var.get() == "組合體"
            assert scene.cutting_mesh_error is None
            rows.append((expected_mode, round((time.perf_counter() - started) * 1000, 2)))

        # Returning to the preserved Set/Bay session cannot silently replace
        # its physical 2D/3D scene with the temporary Quantity session.
        assert _mesh_bounds(scene.last_cutting_mesh) == receiving_mesh
        assert _assembly_part_signatures(designer) == receiving_parts

        designer.baseline_model_var.set("金庫型")
        _pump(root, 8)
        restored_mesh = _mesh_bounds(scene.last_cutting_mesh)
        restored_parts = _assembly_part_signatures(designer)
        differing_parts = {
            key: {"before": vault_parts.get(key), "restored": restored_parts.get(key)}
            for key in sorted(set(vault_parts) | set(restored_parts))
            if vault_parts.get(key) != restored_parts.get(key)
        }
        assert restored_mesh == vault_mesh, (
            f"Vault mesh drift after Receiving modal roundtrip: before={vault_mesh}, "
            f"after={restored_mesh}, changed_parts={differing_parts!r}, "
            f"model={designer._phase6_input_snapshot.get('model')!r}, "
            f"active_mode={designer.designer_workspace.active_mode!r}, "
            f"available_parts={tuple(designer.designer_workspace.available_parts)!r}"
        )
        assert restored_parts == vault_parts, differing_parts
        assert designer.root.grab_current() is None
        record_property("issue1796_real_tk_modal_mode_wall_ms", repr(rows))
    finally:
        _close(tk, root, designer)



def test_issue1796_absent_vault_door_stays_absent_after_receiving_modals(monkeypatch):
    """Roundtripping mode buffers must not invent a part the operator removed.

    Regression for the part-presence restore introduced after the #1808 RED:
    restoring the user's old Vault inventory is different from forcing Door.
    """
    from tkinter import messagebox
    import fold_designer_bridge as bridge
    from phase6_manufacturing_adapter import build_manufacturing_cache_key

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError(
            f"unexpected blocking GUI dialog during absent-Door roundtrip: "
            f"{args!r}, {kwargs!r}"
        )

    for name in ("showwarning", "showerror", "showinfo"):
        monkeypatch.setattr(messagebox, name, unexpected_dialog)

    tk, root, _host, designer = _open_vault_designer()
    try:
        assert "door" in designer.designer_workspace.available_parts
        assert "door" in _assembly_part_signatures(designer)

        # The actual Designer removal handler is the user's part-presence
        # authority; do not mutate a detached test fixture's existing_parts.
        assert designer.remove_part("door") is True
        designer.submit_update_intent("assembly", commit=True)
        _pump(root, 8)
        assert "door" not in designer.designer_workspace.available_parts
        assert "door" not in _assembly_part_signatures(designer)
        without_door = _mesh_bounds(designer.final_scene_view.last_cutting_mesh)

        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)
        for opener in (
            bridge._phase6_open_receiving_single_settings,
            bridge._phase6_open_receiving_multi_settings,
        ):
            window = opener(designer)
            try:
                _pump(root, 5)
                assert window.winfo_exists()
            finally:
                if window.winfo_exists():
                    window._receiving_multi_close()
                _pump(root, 4)
            assert designer.root.grab_current() is None

        designer.baseline_model_var.set("金庫型")
        _pump(root, 8)
        assert designer._phase6_input_snapshot.get("model") == "金庫型"
        assert "door" not in designer.designer_workspace.available_parts
        assert "door" not in _assembly_part_signatures(designer)
        assert _mesh_bounds(designer.final_scene_view.last_cutting_mesh) == without_door
        assert designer._phase6_last_resolved_manufacturing_signature == (
            build_manufacturing_cache_key(designer).fingerprint
        )
        assert designer.final_scene_view.cutting_mesh_error is None
        assert designer.root.grab_current() is None
        scheduler = designer._phase6_update_scheduler
        assert not scheduler.dirty and scheduler._after_job is None
    finally:
        _close(tk, root, designer)


def test_issue1796_receiving_modal_close_flushes_changed_geometry_before_assembly(monkeypatch):
    """Windows UAT regression: changed Set/Bay state must commit before Assembly remount."""
    from types import SimpleNamespace

    from gui_modules.application.fold_designer_composition_receiving import (
        _restore_receiving_assembly_after_modal,
    )
    import phase6_manufacturing_adapter as manufacturing_adapter

    events = []

    class Scheduler:
        def flush_now(self):
            events.append("flush")
            app._phase6_last_resolved_manufacturing_signature = "new"

    app = SimpleNamespace(
        _phase6_3d_display_mode="assembly",
        _phase6_last_resolved_manufacturing_signature="old",
        _phase6_update_scheduler=Scheduler(),
        submit_update_intent=lambda reason, commit=False: events.append(
            ("submit", reason, commit)
        ),
        part_var=SimpleNamespace(set=lambda value: events.append(("part", value))),
    )
    owner = SimpleNamespace(
        app=app,
        refresh_receiving_set_bay_control=lambda _ns: events.append("refresh"),
        sync_receiving_current_bay=lambda _ns, refresh_controls=False: events.append(
            "sync"
        ),
        sync_authoritative_derived_parts=lambda _ns: events.append("derived"),
    )
    monkeypatch.setattr(
        manufacturing_adapter,
        "build_manufacturing_cache_key",
        lambda _app: SimpleNamespace(fingerprint="new"),
    )
    namespace = {
        "_phase6_mount_shared_content": lambda _app, mode: events.append(
            ("mount", mode)
        )
    }

    _restore_receiving_assembly_after_modal(owner, namespace)

    assert "sync" in events
    assert "derived" in events
    assert ("submit", "geometry", False) in events
    assert "flush" in events
    assert events.index("sync") < events.index("derived")
    assert events.index("derived") < events.index(("mount", "assembly"))
    assert events.index(("mount", "assembly")) < events.index("flush")


def test_issue1796_receiving_modal_close_equivalent_geometry_is_noop(monkeypatch):
    """No-edit close may restore Assembly but must not manufacture the same state again."""
    from types import SimpleNamespace

    from gui_modules.application.fold_designer_composition_receiving import (
        _restore_receiving_assembly_after_modal,
    )
    import phase6_manufacturing_adapter as manufacturing_adapter

    events = []

    class Scheduler:
        def flush_now(self):
            raise AssertionError("equivalent close must not flush")

    app = SimpleNamespace(
        _phase6_3d_display_mode="assembly",
        _phase6_last_resolved_manufacturing_signature="same",
        _phase6_update_scheduler=Scheduler(),
        submit_update_intent=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("equivalent close must not submit geometry")
        ),
        part_var=SimpleNamespace(set=lambda value: events.append(("part", value))),
    )
    owner = SimpleNamespace(
        app=app,
        refresh_receiving_set_bay_control=lambda _ns: events.append("refresh"),
        sync_receiving_current_bay=lambda _ns, refresh_controls=False: events.append(
            "sync"
        ),
        sync_authoritative_derived_parts=lambda _ns: events.append("derived"),
    )
    monkeypatch.setattr(
        manufacturing_adapter,
        "build_manufacturing_cache_key",
        lambda _app: SimpleNamespace(fingerprint="same"),
    )
    namespace = {
        "_phase6_mount_shared_content": lambda _app, mode: events.append(
            ("mount", mode)
        )
    }

    _restore_receiving_assembly_after_modal(owner, namespace)

    assert "sync" in events
    assert events.index("sync") < events.index(("mount", "assembly"))
