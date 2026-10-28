# -*- coding: utf-8 -*-
"""Original 3D double-click direct inner-door Confirm All commits real NFBs."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real visible Tk")
def test_direct_3d_doubleclick_add_second_nfb_confirm_all_updates_physical_assembly():
    import gui
    import fold_designer_bridge as bridge

    def walk(root):
        yield root
        for child in root.winfo_children():
            yield from walk(child)

    def pump(root):
        root.update_idletasks()
        root.update()

    def button(root, title):
        found = [w for w in walk(root)
                 if isinstance(w, (ttk.Button, tk.Button))
                 and str(w.cget("text")) == title]
        assert len(found) == 1, (title, len(found))
        return found[0]

    root = tk.Tk()
    root.geometry("1200x850+50+50")
    designer = None
    try:
        box = gui.BoxCalculatorGUI(root)
        box.baseline_var.set("受電箱")
        pump(root)
        designer = box.open_original_fold_designer()
        pump(root)
        assert designer.designer_workspace.active_mode == "set_bay"
        key = "inner_door:upper:panel"
        designer.activate_part(key)
        pump(root)
        # This entry is what the Assembly 3D double-click dispatch invokes.
        # It must NOT be replaced by Single Settings or a candidate version.
        box.open_part_hole_editor(key)
        pump(root)
        editor = box.last_unified_hole_editor
        assert editor.winfo_exists()
        assert getattr(editor, "_receiving_settings_mode", None) is None

        snap = designer._phase6_input_snapshot
        bay = snap["receiving_layout"]["sets"][0]["bays"][0]
        before = len((bay.get("nfb_config") or {}).get("holes", ()))
        assert before == 1
        editor._receiving_config_tabs.select(1)
        pump(root)
        frames = [w for w in walk(editor)
                  if getattr(w, "_receiving_inner_switch_state", None) is not None]
        assert len(frames) == 1
        frame = frames[0]
        state = frame._receiving_inner_switch_state
        row = state["rows"][0]
        assert len(state["chosen"][0]) == 1
        available = row["available"]
        index = next(i for i in range(available.size())
                     if available.get(i) == "3P125SN")
        available.selection_set(index)
        button(row["section"], "＋加入").invoke()
        pump(root)
        assert len(state["chosen"][0]) == 2
        assert len(editor._receiving_pending_features()) == 2

        # Until Confirm All: only transient 2D preview, not physical Bay.
        assert len((bay.get("nfb_config") or {}).get("holes", ())) == 1
        button(frame, "確定").invoke()
        pump(root)
        assert editor._receiving_config_tabs.index(
            editor._receiving_config_tabs.select()
        ) == 0
        assert len(editor._receiving_pending_features()) == 2
        assert editor._receiving_staged_config is not None
        button(editor, "確定全部").invoke()
        pump(root)

        # These assertions failed before the repair, even though Canvas
        # displayed two orange CUTTING outlines.
        snapshot = designer._phase6_input_snapshot
        bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
        holes = bay["nfb_config"]["holes"]
        assert bay["nfb_config_submitted"] is True
        assert len(holes) == 2
        assert [(h["slot_index"], h["model_filename"].split(":")[-1])
                for h in holes] == [(0, "2P400"), (1, "3P125SN")]
        assert all(h["manual_x_state"] == "UNVERIFIED_BASIS" for h in holes)
        from ae_engine.receiving_shared_settings import setting_value
        saved = setting_value(
            snapshot["receiving_layout"]["sets"][0], 0, "inner_door_features",
        )
        assert len(saved[key]) == 2
        assert len(snapshot["part_features"][key]) == 2
        scene = bridge._phase6_final_scene_adapter(
            designer
        ).query_assembly_render_data()
        panel = next(
            part.render_data for part in scene.assembly_parts
            if part.part_key == key
        )
        assert len(panel.material.interiors) == 2
        assert len(set(panel.metadata["nfb_v5_hole_ids"])) == 2
    finally:
        if designer is not None:
            try:
                designer.root.destroy()
            except tk.TclError:
                pass
        root.destroy()
