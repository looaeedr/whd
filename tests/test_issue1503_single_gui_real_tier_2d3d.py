# -*- coding: utf-8 -*-
"""#1503 user-observed RED: final Single Confirm must produce real 2D/3D parts.

This is the ENTIRE native Tk receiving workflow, not a standalone source
fixture. The canonical assembly must show distinct NFB-tier Base Plates,
formed fixing plates and SIDE marking outlines on the user's real current
cabinet. An edited opening alone does not meet the acceptance contract.

Never accept a fabricated drawing or silently set manufacturing_ready=True.
"""
from __future__ import annotations

from tkinter import ttk
import tkinter as tk

import pytest


def _walk(widget):
    stack = [widget]
    while stack:
        w = stack.pop()
        yield w
        try:
            stack.extend(reversed(w.winfo_children()))
        except tk.TclError:
            continue


def _pump(root):
    root.update_idletasks()
    root.update()


def _buttons(widget, name):
    return [w for w in _walk(widget)
            if isinstance(w, (ttk.Button, tk.Button))
            and str(w.cget("text")) == name]


def _pick_400(root, state, layer):
    row = state["rows"][layer]
    # Fresh receiving Single now starts with one Shihlin 2P400 in its
    # *uncommitted* editable draft. Never add a duplicate while using the
    # old helper to populate another/empty layer.
    if row["assigned"].size() == 1 and "2P400" in row["assigned"].get(0):
        return
    source = row["available"]
    index = next(i for i in range(source.size())
                 if "2P400" in str(source.get(i)))
    source.selection_clear(0, tk.END)
    source.selection_set(index)
    source.activate(index)
    buttons = _buttons(row["section"], "＋加入")
    assert len(buttons) == 1
    buttons[0].invoke()
    _pump(root)
    assert row["assigned"].size() == 1


def test_single_confirm_makes_real_tier_parts_and_side_marks_not_only_hole_draft(tmp_path):
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk()
    root.withdraw()
    try:
        calc = gui.BoxCalculatorGUI(root)
        calc.baseline_var.set("受電箱")
        _pump(root)
        designer = calc.open_original_fold_designer()
        _pump(root)
        settings = bridge._phase6_open_receiving_single_settings(designer)
        _pump(root)
        # #1502 real GUI regression: operator has submitted NFB numeric CSV,
        # and LEFT 2P400+2P400 is uniquely known from original CUTTING source.
        # Do NOT manufacture test success by silently entering a second
        # hand-picked receiving_base_plate setting before the NFB workflow.
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None
        selected = settings._receiving_multi_setting_list
        selected.selection_clear(0, tk.END)
        selected.selection_set(1)
        selected.event_generate("<<ListboxSelect>>")
        _pump(root)
        entries = _buttons(settings._receiving_multi_settings_host, "編輯")
        assert len(entries) == 1
        entries[0].invoke()
        _pump(root)

        editor = calc.last_unified_hole_editor
        editor._receiving_config_tabs.select(1)
        _pump(root)
        frame = next(x for x in _walk(editor)
                     if hasattr(x, "_receiving_inner_switch_state")
                     and x.winfo_exists())
        state = frame._receiving_inner_switch_state
        _pick_400(root, state, 0)
        radio = next(w for w in _walk(frame)
                     if isinstance(w, ttk.Radiobutton)
                     and str(w.cget("text")) == "2"
                     and str(w.cget("value")) == "2")
        radio.invoke()
        _pump(root)
        _pick_400(root, state, 1)
        assert len(_buttons(frame, "確定")) == 1
        _buttons(frame, "確定")[0].invoke()
        _pump(root)

        assert editor._receiving_config_tabs.index(
            editor._receiving_config_tabs.select()) == 0
        assert len(editor._receiving_pending_features()) == 2
        _buttons(editor, "確定全部")[0].invoke()
        _pump(root)

        assert not editor.winfo_exists()
        holes = designer.designer_workspace.features_for("inner_door:upper:panel")
        assert len([f for f in holes if f.source_type == "NFB_CSV_SOURCE"]) == 2

        # First actionable condition: the actual current physical cabinet
        # must own two distinct mounted source plates instead of the stale
        # generic single root. These are expected real 2D/3D PartRenderData.
        scene = bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        physical = {part.part_key: part for part in scene.assembly_parts}
        assert "base_plate" not in physical
        for index in (0, 1):
            key = f"base_plate:nfb_layer:{index}"
            assert key in physical, f"missing physical 2D/3D {key}"
            part = physical[key]
            assert part.render_data.material.area > 0
            assert part.render_data.unfolded_topology.piece_id == key
            assert part.render_data.metadata.get("manufacturing_ready") is False
            # 2D operator sheet selector must list this actual per-tier part,
            # and its active-sheet renderer must use the SAME physical source
            # material as the 3D assembly (not just an invisible scene DTO).
            assert key in designer.designer_workspace.available_parts
            from phase6_part_navigation import operator_part_selector_keys
            assert key in operator_part_selector_keys(
                designer.designer_workspace.available_parts
            )
            from phase6_manufacturing_adapter import build_scene_payload_for_app
            source = build_scene_payload_for_app(designer, key)
            preview = designer._scene_query_callback(key, source)
            assert preview.unfolded_topology.piece_id == key
            assert preview.material.area == part.render_data.material.area

        formed = tuple(scene.formed_fixing_plate_skins or ())
        assert len(formed) == 4, "two tiers require four real side-fixed plates"
        assert len({part.part_id for part in formed}) == 4
        # These must be real source contact geometry, not 16 handmade strokes.
        from ae_engine.receiving_fixed_plate_side_contact import (
            derive_receiving_ear_side_contact_from_formed_skin,
        )
        contacts = tuple(derive_receiving_ear_side_contact_from_formed_skin(row)
                         for row in formed)
        assert {x.side_piece_id for x in contacts} == {
            "box_body:left_side", "box_body:right_side"
        }
        assert all(len(x.world_surface_boundary) == 4 for x in contacts)
        # The scene owning correct DTOs is not sufficient: verify the actual
        # production Matplotlib 3D renderer drew all four formed EAR skins
        # and eight source-contact MARKING segments on EACH side plate.
        # No raw/preselected/fabricated lines are passed to the renderer.
        designer._phase6_3d_display_mode = "assembly"
        renderer = designer.final_scene_view
        adapter = bridge._phase6_final_scene_adapter(designer)
        request = adapter.build_request()
        assert request is not None and request.part_key == "assembly"
        renderer.render(request)
        assert set(renderer.last_formed_ear_display_ids) == {
            row.part_id for row in formed
        }
        assert len(renderer.last_receiving_ear_marking_segments) == 16
        # A segment-count pass is not a visible-pixel pass. Render the SAME
        # physical FinalScene twice at the SAME camera; toggle ONLY the real
        # production renderer's formed-EAR contact overlay. This captures
        # whether Matplotlib actually made contrasting pixels on its canvas.
        import numpy as np
        ax = renderer.renderer.ax3d
        canvas = renderer.renderer.canvas
        original = renderer._draw_receiving_ear_side_markings

        def actual_canvas_pixels(*, marking, camera, label):
            ax.clear()
            if not marking:
                renderer._draw_receiving_ear_side_markings = lambda *a, **kw: ()
            try:
                renderer.render(request)
                ax.view_init(elev=camera[0], azim=camera[1])
                canvas.draw()
                pixels = np.asarray(canvas.buffer_rgba()).copy()
                # Opt-in evidence only: save the unedited native Tk canvas.
                # No synthetic image or altered production rendering.
                import os
                output = os.environ.get("WHD_1503_PIXEL_RECEIPT_DIR")
                if output:
                    from pathlib import Path
                    from PIL import Image
                    folder = Path(output)
                    folder.mkdir(parents=True, exist_ok=True)
                    suffix = "with_marks" if marking else "without_marks"
                    Image.fromarray(pixels).save(folder / f"{label}_{suffix}.png")
                return pixels
            finally:
                renderer._draw_receiving_ear_side_markings = original

        for label, camera in (
            ("normal_operator_view", (50., -90.)),
            ("side_interior_inspection_view", (32., 125.)),
        ):
            without = actual_canvas_pixels(marking=False, camera=camera, label=label)
            with_marks = actual_canvas_pixels(marking=True, camera=camera, label=label)
            assert with_marks.shape == without.shape
            delta = np.max(
                np.abs(
                    with_marks[:, :, :3].astype(np.int16)
                    - without[:, :, :3].astype(np.int16)
                ),
                axis=2,
            )
            import os
            output = os.environ.get("WHD_1503_PIXEL_RECEIPT_DIR")
            if output:
                from pathlib import Path
                from PIL import Image
                heatmap = np.clip(delta.astype(np.int16) * 4, 0, 255).astype(np.uint8)
                Image.fromarray(heatmap).save(Path(output) / f"{label}_difference_heatmap.png")
            visible = int(np.count_nonzero(delta > 32))
            total = int(delta.size)
            print(
                f"REAL_3D_PIXEL_MARKING {label}: "
                f"visible_pixels={visible}, all_pixels={total}, "
                f"percent={visible * 100 / total:.5f}%",
                flush=True,
            )
            if label == "side_interior_inspection_view":
                # This view faces the actual physical SIDE inner surface;
                # 16 theoretical segments but zero legible pixels is RED.
                assert visible >= 250, (
                    "EAR_3D_VISIBLE_MARKING_NOT_RENDERED_ON_SIDE_INSPECTION"
                )

        # 2D must be native Tk pixels from the real WHD Canvas drawing sink,
        # not just metadata, fabricated strokes, or a matplotlib source sketch.
        # This comparison uses an explicitly operator-selected physical source;
        # the original unconfigured problem-project fixture stays unchanged.
        from types import SimpleNamespace
        from PIL import ImageGrab
        from gui_modules.rendering.box_body_view import draw_box_body_piece_preview
        from ae_engine.sheetmetal_drawing import LinePrimitive
        from gui_modules.application.receiving_ear_side_2d import (
            present_receiving_ear_side_piece_2d,
        )
        import os
        box_part = next(part for part in scene.assembly_parts
                        if part.part_key == "box_body")
        box_data = box_part.render_data
        body = {p.role: p for p in box_data.pieces}
        tk_stage = tk.Toplevel(root)
        tk_stage.geometry("1000x880+30+30")
        stage_canvas = tk.Canvas(tk_stage, width=950, height=820, bg="#172233")
        stage_canvas.pack(fill=tk.BOTH, expand=True)
        _pump(root)
        host = SimpleNamespace(
            canvas_z=stage_canvas,
            draw_stock_var=tk.BooleanVar(master=root, value=False),
            _box_body_piece_label=calc._box_body_piece_label,
            COLOR_TEXT_MUTED=calc.COLOR_TEXT_MUTED,
        )
        from gui import (
            _phase6_2d_material_viewport, render_drawing_scene,
            _draw_phase6_annotation_projection,
        )
        output = os.environ.get("WHD_1503_PIXEL_RECEIPT_DIR")
        def capture_side(side, selected):
            stage_canvas.delete("all")
            draw_box_body_piece_preview(
                host, box_data, selected, "box_body:" + side,
                viewport=_phase6_2d_material_viewport,
                scene_renderer=render_drawing_scene,
                annotation_drawer=_draw_phase6_annotation_projection,
            )
            _pump(root)
            if selected.render_data.metadata.get("ear_side_mark_preview_only"):
                authentic = stage_canvas.find_withtag(
                    "receiving_source_ear_marking_preview"
                )
                assert len(authentic) == 8, (
                    "ACTUAL_TK_OPERATOR_SIDE_EAR_LINES_NOT_VISIBLE:" + side
                )
            x, y = stage_canvas.winfo_rootx(), stage_canvas.winfo_rooty()
            w, h = stage_canvas.winfo_width(), stage_canvas.winfo_height()
            assert min(w, h) >= 500, "2D canvas not actually mapped"
            return np.asarray(ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGB")).copy()

        for side in ("left_side", "right_side"):
            original_side = body[side]
            # Current native Side PartRenderData already contains the REAL
            # canonical MARKING. A display-only overlay on top of it would
            # legitimately fail with EXISTING_MARKING_CONFLICT. Never
            # manufacture duplicates to satisfy a pixel threshold.
            primitives = tuple(original_side.render_data.scene.primitives)
            ear_lines = tuple(p for p in primitives if (
                isinstance(p, LinePrimitive) and
                str(getattr(p, "layer", "")).upper() == "MARKING"
            ))
            # Honest RED witness: distinguish pre-existing joint marks from
            # the per-tier EAR projected weld contact, without adding strokes.
            from ae_engine.receiving_fixed_plate_side_uv_marking import (
                resolve_receiving_ear_side_uv_receipts,
            )
            from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
            resolved_manufacturing = designer._phase6_resolve_manufacturing_geometry()
            world_geometry = _phase6_build_joint_world_geometry(
                tuple(resolved_manufacturing.parts),
                (float(designer._phase6_input_snapshot["w"]),
                 float(designer._phase6_input_snapshot["h"]),
                 float(designer._phase6_input_snapshot["d"])),
                float(designer._phase6_input_snapshot["t"]),
            )
            receipts = resolve_receiving_ear_side_uv_receipts(
                designer._phase6_input_snapshot,
                world_geometry=world_geometry,
                geometry=resolved_manufacturing,
            )
            from shapely.geometry import LineString, Polygon
            patches = [Polygon(rec.side_source_flat_boundary) for rec in receipts
                       if rec.side_piece_id == "box_body:" + side]
            print("SIDE_SOURCE_MARKING_DIAGNOSTIC", side, "source_lines",
                  [((round(item.p1.x, 2), round(item.p1.y, 2)),
                    (round(item.p2.x, 2), round(item.p2.y, 2))) for item in ear_lines],
                  "ear_patches", [
                      (tuple(round(v, 2) for v in p.bounds), round(p.area, 2))
                      for p in patches
                  ], "overlap_lengths", [
                      [round(LineString(((item.p1.x, item.p1.y), (item.p2.x, item.p2.y))).intersection(
                          p).length, 3) for p in patches]
                      for item in ear_lines
                  ], flush=True)
            shown, blocker = present_receiving_ear_side_piece_2d(
                calc, box_data, original_side, "box_body:" + side,
            )
            assert blocker is None, blocker
            assert shown.render_data.metadata["ear_side_mark_preview_count"] == 8
            assert shown.render_data.metadata["ear_side_mark_preview_only"] is True
            assert shown.render_data.metadata["ear_side_existing_marking_overlap_display_mode"] is True
            after_primitives = tuple(shown.render_data.scene.primitives)
            after_lines = tuple(p for p in after_primitives if (
                isinstance(p, LinePrimitive) and
                str(getattr(p, "layer", "")).upper() == "MARKING"
            ))
            assert len(after_lines) == len(ear_lines) + 8, (
                "REAL_SOURCE_2D_EAR_PREVIEW_MISSING_EIGHT_PER_SIDE:" + side
            )
            assert tuple(original_side.render_data.scene.primitives) == primitives, (
                "preview mutated source geometry"
            )
            # Both are actual live Tk 2D renderings from the identical
            # source. The AFTER view adds only the verified EAR UV receipt
            # lines; the factory's original joint MARKING stays untouched.
            without_2d = capture_side(side, original_side)
            with_2d = capture_side(side, shown)
            assert with_2d.shape == without_2d.shape
            diff = np.max(np.abs(
                with_2d.astype(np.int16) - without_2d.astype(np.int16),
            ), axis=2)
            # Remove the top info text from pixel witness so a changed
            # "8 marks" LABEL never masquerades as geometric 2D lines.
            visible_2d = int(np.count_nonzero(diff[220:, :] > 45))
            print(f"REAL_TK_2D_MARKING {side}: visible_pixels={visible_2d}", flush=True)
            assert visible_2d >= 250, "REAL_TK_SIDE_MARKS_NOT_VISIBLE:" + side
            if output:
                from pathlib import Path
                folder = Path(output)
                folder.mkdir(parents=True, exist_ok=True)
                from PIL import Image
                Image.fromarray(without_2d).save(folder / f"real_tk_2d_{side}_without.png")
                Image.fromarray(with_2d).save(folder / f"real_tk_2d_{side}_with.png")
        tk_stage.destroy()

        # #1502 end-to-end actual operator DXF: the SAME no-manual-base
        # native Tk cabinet must export real CUTTING/BEND and SIDE MARKING
        # through its ORIGINAL visible export button, not a helper's
        # synthetic scene or a second CSV-only button.
        from unittest.mock import patch
        import gui_modules.project.export_actions as export_actions
        from pathlib import Path
        import ezdxf
        export_dir = tmp_path / "no_manual_two_tier_actual_gui_dxf"
        export_dir.mkdir()
        errors=[]
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None
        # The Single settings screen is the production QuantityModel flow:
        # CHECK/Q deliberately names *geometry-equivalent* manufacturing
        # groups by hash (part_<hash>.dxf). A filename substring can NEVER
        # prove that a physical source sheet is absent. Instrument the
        # unchanged grouping seam to witness exactly which physical source
        # members the ORIGINAL UI actually wrote and in what quantities.
        import phase6_quantity_manufacturing as qmanufacture
        actual_group_resolver = qmanufacture.quantity_manufacturing_groups
        emitted_groups=[]
        def record_real_group_receipts(*args,**kwargs):
            groups=actual_group_resolver(*args,**kwargs)
            emitted_groups.extend(groups)
            return groups
        # Never bypass EAR Z identity checks. Preserve exact runtime
        # source/selector evidence when an authentic GUI export is rejected.
        authority = designer._phase6_input_snapshot
        active = authority.get("_receiving_runtime_selection")
        sets = (authority.get("receiving_layout") or {}).get("sets") or ()
        print("ISSUE1503_REAL_GUI_EAR_Z_SOURCE_IDENTITY", {
            "active_mode": authority.get("active_mode"),
            "selection": active,
            "current_set_ids": tuple(row.get("stable_id") for row in sets),
            "current_bay_ids": tuple(
                tuple(b.get("stable_id") for b in row.get("bays") or ())
                for row in sets
            ),
            "quantity_selected_version": (
                (authority.get("quantity") or {}).get("selected_version_id")
            ),
            "nfb_submitted": authority.get("nfb_config_submitted"),
        }, flush=True)
        for setting in designer.output_export_vars.values():
            setting.set(True)
        with (
            patch.object(export_actions.filedialog,"askdirectory",
                         return_value=str(export_dir)),
            patch.object(export_actions.messagebox,"showerror",
                         side_effect=lambda title,msg: errors.append((title,msg))),
            patch.object(export_actions.messagebox,"showinfo",
                         return_value=None),
            patch.object(export_actions.messagebox,"showwarning",
                         return_value=None),
            patch.object(export_actions.messagebox,"askyesno",
                         return_value=False),
            patch.object(qmanufacture,"quantity_manufacturing_groups",
                         side_effect=record_real_group_receipts),
        ):
            designer.output_export_button.invoke()
            _pump(root)
        assert not errors, "NATIVE_GUI_CSV_DXF_EXPORT_FAILED: " + repr(errors)
        actual_dxfs = tuple(export_dir.glob("*.dxf"))
        names = tuple(p.name for p in actual_dxfs)
        from gui_modules.project.export_actions import _selected_export_flags
        print("ISSUE1502_NATIVE_EXPORT_TRACE", {
            "dxfs": names,
            "main_existing": sorted(calc._phase6_current_existing_parts()),
            "real_workspace": designer.designer_workspace.available_parts,
            "base_toggle": bool(calc.export_base_plate_var.get()),
            "resolved_flags": _selected_export_flags(
                calc, calc._phase6_current_existing_parts(),
                calc._has_any_indicator_box(),
            ),
        }, flush=True)
        assert emitted_groups, "GUI_DXF_CHECK_Q_GROUP_RECEIPTS_MISSING"
        output_set=set(names)
        assert output_set=={g.filename for g in emitted_groups}, (
            "GUI_DXF_CHECK_Q_FILE_OR_SOURCE_GROUP_MISMATCH",names,
        )
        physical_receipts=tuple(row for g in emitted_groups for row in g.members)
        def written_count(starts):
            return sum(row.quantity for row in physical_receipts
                       if row.physical_id.startswith(starts))
        assert written_count("base_plate:nfb_layer:")==2, (
            "GUI_MISSING_TWO_REAL_BASE_DXF",
            tuple((row.version_id,row.physical_id,row.quantity)
                  for row in physical_receipts),
        )
        assert written_count("base_plate:fixing_plate:")==4, (
            "GUI_MISSING_FOUR_FORMED_FIXING_DXF",physical_receipts,
        )
        assert written_count("inner_door:upper:panel")>=1, (
            "GUI_MISSING_REAL_INNER_DOOR_DXF",physical_receipts,
        )
        assert written_count("box_body:box_body_left_side")>=1
        assert written_count("box_body:box_body_right_side")>=1
        for group in emitted_groups:
            assert group.quantity==sum(row.quantity for row in group.members)
            assert (export_dir/group.filename).is_file()
        for path in actual_dxfs:
            ezdxf.readfile(path)
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None

        # Only now persist the explicitly configured source + Confirm All
        # through the product Save As, and ACTUALLY reopen it in the GUI.
        from unittest.mock import patch
        saved_path = tmp_path / "configured_two_tier_native_gui.p6fold"
        with patch("tkinter.filedialog.asksaveasfilename", return_value=str(saved_path)):
            saved = designer.save_project_file_as()
        assert saved_path.exists() and saved
        reloaded = calc.load_phase6_project(saved_path, open_designer=True)
        _pump(root)
        # The Save/Reload must keep the NFBConfig as the single authority,
        # with actual physical tiers rebuilt automatically from numeric CSV.
        assert reloaded._phase6_input_snapshot.get("receiving_base_plate") is None
        restored = bridge._phase6_final_scene_adapter(reloaded).query_assembly_render_data()
        restored_parts = {p.part_key: p for p in restored.assembly_parts}
        assert all(f"base_plate:nfb_layer:{i}" in restored_parts for i in (0, 1))
        assert len(restored.formed_fixing_plate_skins) == 4
        reloaded._phase6_3d_display_mode = "assembly"
        reloaded_view = reloaded.final_scene_view
        restored_request = bridge._phase6_final_scene_adapter(reloaded).build_request()
        assert restored_request is not None
        reloaded_view.render(restored_request)
        assert len(reloaded_view.last_receiving_ear_marking_segments) == 16
        for side, target_x in (("left_side", -398.), ("right_side", 398.)):
            lines = tuple((a,b) for a,b in reloaded_view.last_receiving_ear_marking_segments
                          if abs(a[0]-target_x) < 1e-5 and abs(b[0]-target_x) < 1e-5)
            assert len(lines) == 8, "RELOADED_LEFT_RIGHT_EAR_MARKING_MISSING:" + side
    finally:
        root.destroy()
