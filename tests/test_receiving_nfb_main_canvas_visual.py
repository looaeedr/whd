# -*- coding: utf-8 -*-
"""#1987: an NFB must be VISIBLE on the original main drawing, not only saved."""
import os
import tkinter as tk
from tkinter import ttk

import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要可見 Tk 測試環境")
def test_receiving_confirm_draws_two_csv_nfb_holes_on_native_main_canvas():
    import gui
    import fold_designer_bridge as bridge

    def walk(root):
        pending = [root]
        while pending:
            widget = pending.pop()
            yield widget
            pending.extend(widget.winfo_children())

    def pump(root):
        root.update_idletasks()
        root.update()

    def button(parent, label):
        matching = [w for w in walk(parent)
                    if isinstance(w, (ttk.Button, tk.Button))
                    and str(w.cget("text")) == label]
        assert len(matching) == 1, (label, len(matching))
        return matching[0]

    def layer_state(editor):
        frames = [w for w in walk(editor)
                  if getattr(w, "_receiving_inner_switch_state", None) is not None]
        assert len(frames) == 1
        return frames[0], frames[0]._receiving_inner_switch_state

    def add_real_csv_nfb(root, state, index):
        row = state["rows"][index]
        # New first-entry default owns one real Shihlin 2P400 *draft*.
        # The original canvas test should reuse it instead of creating
        # a second first-tier switch and then blaming duplicate geometry.
        if row["assigned"].size() == 1 and str(row["assigned"].get(0)) == "2P400":
            return
        options = row["available"]
        selected = next((i for i in range(options.size())
                         if "2P400" in str(options.get(i))), None)
        assert selected is not None, "測試用 CSV 必須有主孔完整的 2P400 型號"
        options.selection_clear(0, tk.END)
        options.selection_set(selected)
        options.activate(selected)
        button(row["section"], "＋加入").invoke()
        pump(root)
        assert row["assigned"].size() == 1

    root = tk.Tk()
    root.geometry("1200x850+80+80")
    try:
        box = gui.BoxCalculatorGUI(root)
        box.baseline_var.set("受電箱")
        pump(root)
        designer = box.open_original_fold_designer()
        pump(root)
        settings = bridge._phase6_open_receiving_single_settings(designer)
        pump(root)
        selection = settings._receiving_multi_setting_list
        selection.selection_set(1)
        selection.event_generate("<<ListboxSelect>>")
        pump(root)
        button(settings._receiving_multi_settings_host, "編輯").invoke()
        pump(root)
        editor = box.last_unified_hole_editor
        tabs = editor._receiving_config_tabs

        # Capture the actual original Hole Editor canvas, not the sidebar,
        # listbox, part cache, or an external assembly preview.
        canvas_candidates = [w for w in walk(editor)
                             if isinstance(w, tk.Canvas)]
        drawing = max(canvas_candidates, key=lambda w: len(w.find_all()))

        def drawn_nfb_profiles():
            # One original NFB may be redrawn twice at identical pixels by
            # the legacy baseline and editable overlay. These are NOT two
            # physical holes. Count distinct native Canvas geometries.
            return tuple(sorted({
                drawing.bbox(i) for i in drawing.find_all()
                if drawing.type(i) == "polygon"
                and drawing.itemcget(i, "outline").lower() == "#ff9f0a"
            }))

        # A new Receiving cabinet already owns one real CSV NFB opening.
        # The native editor must render its existing CUTTING before edits;
        # do not mistake it for an uncommitted empty canvas.
        initial = drawn_nfb_profiles()
        assert len(initial) == 1
        tabs.select(1)
        pump(root)
        frame, state = layer_state(editor)
        assert tuple(float(v.get()) for v in state["layer_heights_mm"]) == (550, 830)
        add_real_csv_nfb(root, state, 0)
        radios = [w for w in walk(frame)
                  if isinstance(w, ttk.Radiobutton)
                  and w.cget("text") == "2" and str(w.cget("value")) == "2"]
        actual_layer_radio = next(
            (w for w in radios
             if str(w.cget("variable")) == str(state["layers"])), None
        )
        assert actual_layer_radio is not None, "找不到內門層數的兩層選項"
        actual_layer_radio.invoke()
        pump(root)
        assert state["layers"].get() == 2
        assert state["nfb_physical_layers"].get() == 2
        add_real_csv_nfb(root, state, 1)
        assert tuple(float(v.get()) for v in state["layer_heights_mm"]) == (330, 830)

        button(frame, "確定").invoke()
        pump(root)
        assert tabs.index(tabs.select()) == 0
        assert len(editor._receiving_pending_features()) == 2
        assert len(drawn_nfb_profiles()) == 2, (
            "NFB typed Feature is staged, but original main Canvas is stale"
        )

        from ae_engine.cabinet_types import policy
        part = policy.derive_inner_door_panels(
            designer._phase6_input_snapshot
        )[0].stable_id
        # Tab Confirm must not alter the existing single-NFB baseline.
        before = tuple(designer.designer_workspace.features_for(part))
        button(editor, "取消全部").invoke()
        pump(root)
        assert tuple(designer.designer_workspace.features_for(part)) == before
        assert designer._phase6_input_snapshot["nfb_config"]["layer_count"] == 1
    finally:
        try:
            if getattr(box, "fold_designer_window", None) is not None:
                box.fold_designer_window.destroy()
        except (AttributeError, tk.TclError):
            pass
        root.destroy()
