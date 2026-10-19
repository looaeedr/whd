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


def test_single_confirm_makes_real_tier_parts_and_side_marks_not_only_hole_draft():
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
        # Operator has to select the physical Base Plate variant; do not
        # make up a LEFT/CENTER/RIGHT shape for an unconfigured cabinet.
        # Use the same existing physical #1502 source through its actual
        # GUI settings transaction before committing NFB CSV hole rows.
        from tests.test_receiving_committed_nfb_depth_base_part_flow import (
            _snapshot as source_base,
        )
        designer.settings_panel._receiving_base_plate_commit(
            source_base()["receiving_base_plate"],
        )
        _pump(root)
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
            source = designer._phase6_scene_query_payload_for_part(key)
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
    finally:
        root.destroy()
