"""#1819: real Tk command ownership; re-render must NOT append Tcl callbacks.

The old _bind_settings_scroll_tree(widget) repeated 7 binds(add="+")
for every already cached page re-render. Tk kept the generated CallWrapper
commands alive while the widget was alive, even though pages did not grow.
"""
from __future__ import annotations

import gc
import weakref
import tkinter as tk
from tkinter import ttk

from phase6_settings_panel import Phase6SettingsPanel


def _commands(widget):
    return tuple(getattr(widget, "_tclCommands", ()) or ())


def test_issue1819_repeated_cached_settings_renders_keep_tcl_bindings_constant():
    root = tk.Tk()
    try:
        root.geometry("850x600+0+0")
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: {},
            stage_setting_update=lambda *_args: None,
            flush_settings=lambda: None,
            save_defaults=lambda *_args: None,
        )
        host = ttk.Frame(root)
        host.pack(fill="both", expand=True)
        group = ttk.LabelFrame(host, text="板件設定")
        group.pack(fill="both")
        field = ttk.Entry(group)
        field.pack()
        root.update()
        widgets = (host, group, field)

        before = {w: _commands(w) for w in widgets}
        panel._bind_settings_scroll_tree(host)
        first = {w: _commands(w) for w in widgets}
        assert all(len(first[w]) == len(before[w]) + 7 for w in widgets)
        assert all(w.bind("<MouseWheel>") for w in widgets)
        assert all(w.bind("<Prior>") for w in widgets)

        # Same actual widgets are used from page_cache on every render.
        for _ in range(40):
            panel._bind_settings_scroll_tree(host)
        root.update()
        assert all(_commands(w) == first[w] for w in widgets)
        assert len(panel._scroll_bound_widgets) == 3

        # A genuinely new setting field still binds exactly once.
        new_field = ttk.Entry(group)
        new_field.pack()
        panel._bind_settings_scroll_tree(host)
        new_commands = _commands(new_field)
        assert len(new_commands) == 7
        assert all(_commands(w) == first[w] for w in widgets)
        assert len(panel._scroll_bound_widgets) == 4

        # No strong reference from the guard to a destroyed child widget.
        ref = weakref.ref(new_field)
        new_field.destroy()
        del new_field
        gc.collect()
        assert ref() is None
        assert len(panel._scroll_bound_widgets) == 3
    finally:
        root.destroy()


def test_issue1819_bound_settings_scroll_actions_remain_callable_from_tk():
    root = tk.Tk()
    try:
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: {},
            stage_setting_update=lambda *_args: None,
            flush_settings=lambda: None,
            save_defaults=lambda *_args: None,
        )
        seen = []
        class Scroll:
            def yview_scroll(self, steps, units):
                seen.append(("wheel", steps, units))
            def yview_moveto(self, fraction):
                seen.append(("home", fraction))
        panel.settings_scroll_canvas = Scroll()
        # Keyboard shortcuts require a focused widget; a bare ttk.Frame
        # cannot receive the X11 KeyPress event by default.
        w = ttk.Entry(root)
        w.pack()
        root.update()
        panel._bind_settings_scroll_tree(w)
        for _ in range(15):
            panel._bind_settings_scroll_tree(w)
        w.focus_force()
        root.update()
        assert root.focus_get() is w
        w.event_generate("<MouseWheel>", delta=-120)
        w.event_generate("<Home>")
        root.update()
        assert ("wheel", 1, "units") in seen
        assert ("home", 0.0) in seen
        assert len(_commands(w)) == 7
    finally:
        root.destroy()
