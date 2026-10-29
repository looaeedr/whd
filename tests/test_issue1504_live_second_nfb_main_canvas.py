# -*- coding: utf-8 -*-
"""Second NFB must be a visible native hole immediately after ＋加入."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要可見 Tk 作業環境")
def test_second_nfb_add_live_2d_undo_cancel_and_confirm_all():
    import gui
    import fold_designer_bridge as bridge
    from ae_engine.cabinet_types import policy

    def walk(widget):
        pending = [widget]
        while pending:
            child = pending.pop()
            yield child
            pending.extend(child.winfo_children())

    def pump(root):
        root.update_idletasks()
        root.update()

    def button(root, name):
        matches = [item for item in walk(root)
                   if isinstance(item, (ttk.Button, tk.Button))
                   and str(item.cget("text")) == name]
        assert len(matches) == 1, (name, len(matches))
        return matches[0]

    root = tk.Tk()
    root.geometry("1200x850+60+60")
    designer = None
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

        drawings = [w for w in walk(editor) if isinstance(w, tk.Canvas)]
        canvas = max(drawings, key=lambda w: len(w.find_all()))

        def distinct_nfb_profiles():
            return {
                canvas.bbox(item) for item in canvas.find_all()
                if canvas.type(item) == "polygon"
                and canvas.itemcget(item, "outline").lower() == "#ff9f0a"
            }

        def active_tab():
            frames = [w for w in walk(editor)
                      if getattr(w, "_receiving_inner_switch_state", None) is not None]
            assert len(frames) == 1
            return frames[0], frames[0]._receiving_inner_switch_state

        def add_second(frame, state):
            row = state["rows"][0]
            assert row["assigned"].size() == 1
            options = row["available"]
            index = next(i for i in range(options.size())
                         if options.get(i) == "2P400")
            options.selection_clear(0, tk.END)
            options.selection_set(index)
            options.activate(index)
            button(row["section"], "＋加入").invoke()
            pump(root)
            assert row["assigned"].size() == 2

        assert len(editor._receiving_pending_features()) == 1
        tabs.select(1)
        pump(root)
        frame, state = active_tab()
        add_second(frame, state)
        # No extra inner-tab Confirm: one real pending Feature per source NFB.
        features = tuple(editor._receiving_pending_features())
        assert len(features) == 2
        assert [dict(f.source_params)["slot_index"] for f in features] == [0, 1]
        tabs.select(0)
        pump(root)
        # The original Canvas used to draw a duplicate overlapping legacy
        # polygon. Distinct geometry, not raw canvas item count, is authoritative.
        assert len(distinct_nfb_profiles()) == 2
        assert len(tuple(designer.designer_workspace.features_for(
            policy.derive_inner_door_panels(designer._phase6_input_snapshot)[0].stable_id
        ))) == 1

        tabs.select(1)
        pump(root)
        frame, state = active_tab()
        button(frame, "復原 NFB").invoke()
        pump(root)
        assert len(editor._receiving_pending_features()) == 1
        add_second(frame, state)
        assert len(editor._receiving_pending_features()) == 2
        button(frame, "取消").invoke()
        pump(root)
        assert len(editor._receiving_pending_features()) == 1
        assert getattr(editor, "_receiving_staged_config", None) is None

        tabs.select(1)
        pump(root)
        frame, state = active_tab()
        add_second(frame, state)
        button(frame, "確定").invoke()
        pump(root)
        assert len(editor._receiving_pending_features()) == 2
        button(editor, "確定全部").invoke()
        pump(root)
        part = policy.derive_inner_door_panels(
            designer._phase6_input_snapshot
        )[0].stable_id
        assert len(designer.designer_workspace.features_for(part)) == 2
        assert len(designer._phase6_input_snapshot["nfb_config"]["holes"]) == 2
    finally:
        if designer is not None:
            try:
                designer.root.destroy()
            except tk.TclError:
                pass
        root.destroy()
