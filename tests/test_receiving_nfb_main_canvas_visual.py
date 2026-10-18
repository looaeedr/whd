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
            return tuple(i for i in drawing.find_all()
                         if drawing.type(i) == "polygon"
                         and drawing.itemcget(i, "outline").lower() == "#ff9f0a")

        assert drawn_nfb_profiles() == ()
        tabs.select(1)
        pump(root)
        frame, state = layer_state(editor)
        assert tuple(float(v.get()) for v in state["layer_heights_mm"]) == (550, 800)
        add_real_csv_nfb(root, state, 0)
        radios = [w for w in walk(frame)
                  if isinstance(w, ttk.Radiobutton)
                  and w.cget("text") == "2" and str(w.cget("value")) == "2"]
        assert radios
        radios[0].invoke()
        pump(root)
        add_real_csv_nfb(root, state, 1)
        assert float(state["layer_heights_mm"][0].get()) == 300.0

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
        assert designer.designer_workspace.features_for(part) == []
        # Native Cancel All still owns the transaction: nothing in the
        # above tab interactions has written to the physical part.
        button(editor, "取消全部").invoke()
        pump(root)
        assert designer.designer_workspace.features_for(part) == []
    finally:
        try:
            if getattr(box, "fold_designer_window", None) is not None:
                box.fold_designer_window.destroy()
        except (AttributeError, tk.TclError):
            pass
        root.destroy()
