from __future__ import annotations

from types import SimpleNamespace
import os

import pytest

import gui
import fold_designer_bridge as bridge


def _require_display():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")


def _configure_five_door_layout(app):
    app.w_var.set("1100")
    app.h_var.set("1800")
    app.multi_door_enabled_var.set(True)
    app.set_door_layout_columns([
        (600, [600, 500, 700]),
        (500, [800, 1000]),
    ])
    app.toggle_multi_door_layout()
    app.update_calculations()


def test_corner_data_multidoor_overview_keeps_real_stable_keys_and_full_interaction_parity(monkeypatch):
    """#92/#98: move the old multi-door 2D capability, not only its callback names.

    The operator-facing overview is a View only.  It may compose current door
    topology and already-authoritative PartRenderData, but it must not invent an
    aggregate ``door`` manufacturing identity or call the old per-cell result
    builder as a second manufacturing path.
    """
    _require_display()
    import tkinter as tk

    root = tk.Tk()
    root.geometry("1200x900+0+0")
    app = None
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        _configure_five_door_layout(app)
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks(); root.update()

        keys = tuple(bridge._phase6_corner_data_part_keys(designer))
        door_keys = tuple(key for key in keys if str(key).startswith("door_c"))
        assert door_keys == (
            "door_c1_r1", "door_c1_r2", "door_c1_r3", "door_c2_r1", "door_c2_r2",
        )
        assert "door" not in keys
        assert not hasattr(app, "notebook")

        # T4 already accepts this sink as authoritative for ordinary physical
        # parts.  A multi-door overview must compose these existing sinks rather
        # than recompute a separate Door result inside the View.
        original_sink = bridge._phase6_render_data_for_blank
        sink_calls = []

        def traced_sink(owner, part_key):
            sink_calls.append(str(part_key))
            return original_sink(owner, part_key)

        monkeypatch.setattr(bridge, "_phase6_render_data_for_blank", traced_sink)
        monkeypatch.setattr(
            app,
            "_door_layout_cell_result",
            lambda *_a, **_k: (_ for _ in ()).throw(
                AssertionError("corner-data View must not rebuild multi-door manufacturing geometry")
            ),
        )

        assert bridge._phase6_select_corner_data_part(designer, "door_c1_r1") == "door_c1_r1"
        root.update_idletasks(); root.update()

        canvas = designer.corner_data_canvas
        assert canvas is not None and canvas.winfo_ismapped()
        assert canvas is not app.canvas_door
        assert set(door_keys) <= set(sink_calls)

        # The old overview capability must now live in the reachable Fold
        # Designer viewport: editable topology dimensions plus cell hit regions.
        assert set(app.door_layout_cell_bounds) == {"0:0", "0:1", "0:2", "1:0", "1:1"}
        assert len(app.door_layout_width_entries) == 2
        assert len(app.door_layout_height_entries) == 5
        assert all(entry.master is canvas for entry in app.door_layout_width_entries.values())
        assert all(entry.master is canvas for entry in app.door_layout_height_entries.values())

        # One click changes the corner-data *View* stable identity only.  It must
        # not use activate_part() and must not depend on retired Notebook tabs.
        x1, y1, x2, y2 = app.door_layout_cell_bounds["0:1"]
        event = SimpleNamespace(x=int((x1 + x2) / 2), y=int((y1 + y2) / 2), time=1000)
        assert app.on_door_canvas_press(event) == "break"
        root.update_idletasks(); root.update()
        assert app.door_layout_selected_var.get() == "0:1"
        assert designer._phase6_corner_data_selected_part_key == "door_c1_r2"
        assert designer.designer_workspace.active_part != "door_c1_r2"

        # A second click in the same cell opens that exact physical-cell editor.
        opened = []
        monkeypatch.setattr(app, "open_door_layout_cell_editor", lambda c, r: opened.append((c, r)))
        event.time = 1250
        assert app.on_door_canvas_press(event) == "break"
        assert opened == [(0, 1)]
        assert designer._phase6_corner_data_selected_part_key == "door_c1_r2"
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
