from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")


def _ancestors(widget):
    out = []
    cur = widget
    while cur is not None:
        try:
            parent_name = cur.winfo_parent()
        except Exception:
            break
        if not parent_name:
            break
        try:
            cur = cur._nametowidget(parent_name)
        except Exception:
            break
        out.append(cur)
    return out


def _descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_descendants(child))
    return out


def _build_app():
    import tkinter as tk
    import fold_designer_bridge as bridge
    from test_phase6_settings_center_bridge import _snapshot

    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root)
    snap = _snapshot()
    snap.update({
        "existing_parts": ["box_body", "head", "tail", "base_plate"],
        "assembly_type": "WRAP_OVERLAY",
    })
    app = bridge.Phase6FoldDesignerApp(win, snap)
    return tk, root, win, app, bridge


def test_endcap_four_edge_controls_live_on_drawing_edges_even_when_parameters_locked():
    tk, root, win, app, bridge = _build_app()
    try:
        assert app._phase6_parameters_unlocked is False
        app.activate_part("head")
        win.update_idletasks(); win.update()

        assert set(app.endcap_joint_widgets) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        hosts = app.drawing_edge_hosts
        expected_hosts = {
            "TOP": hosts.top,
            "BOTTOM": hosts.bottom,
            "LEFT": hosts.left,
            "RIGHT": hosts.right,
        }
        for edge, widget in app.endcap_joint_widgets.items():
            ancestors = _ancestors(widget)
            assert expected_hosts[edge] in ancestors
            assert app.settings_center not in ancestors
            assert widget.winfo_ismapped()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_unlock_does_not_reparent_or_duplicate_endcap_four_edge_controls():
    tk, root, win, app, bridge = _build_app()
    try:
        app.activate_part("head")
        win.update_idletasks(); win.update()
        before = dict(app.endcap_joint_widgets)
        before_parents = {edge: widget.winfo_parent() for edge, widget in before.items()}

        bridge._phase6_toggle_parameter_panel(app)
        win.update_idletasks(); win.update()

        assert app._phase6_parameters_unlocked is True
        assert set(app.endcap_joint_widgets) == set(before)
        assert {edge: widget.winfo_parent() for edge, widget in app.endcap_joint_widgets.items()} == before_parents
        for edge, widget in app.endcap_joint_widgets.items():
            assert widget is before[edge]
            assert widget.winfo_ismapped()

        settings_texts = []
        for widget in _descendants(app.settings_center):
            try:
                if "text" in widget.keys():
                    settings_texts.append(str(widget.cget("text")))
            except Exception:
                pass
        assert "四邊組合" not in settings_texts
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_base_plate_four_shrinks_live_on_drawing_edges_and_bend_stays_in_settings_panel():
    tk, root, win, app, bridge = _build_app()
    try:
        app.activate_part("base_plate")
        win.update_idletasks(); win.update()

        assert app._phase6_parameters_unlocked is False
        assert set(app.base_plate_edge_shrink_widgets) == {"TOP", "BOTTOM", "LEFT", "RIGHT"}
        hosts = app.drawing_edge_hosts
        expected_hosts = {
            "TOP": hosts.top,
            "BOTTOM": hosts.bottom,
            "LEFT": hosts.left,
            "RIGHT": hosts.right,
        }
        for edge, widget in app.base_plate_edge_shrink_widgets.items():
            ancestors = _ancestors(widget)
            assert expected_hosts[edge] in ancestors
            assert app.settings_center not in ancestors
            assert widget.winfo_ismapped()

        bridge._phase6_toggle_parameter_panel(app)
        win.update_idletasks(); win.update()
        assert "base_plate_bend" in app.settings_panel.setting_vars
        for key in (
            "base_plate_shrink_top", "base_plate_shrink_bottom",
            "base_plate_shrink_left", "base_plate_shrink_right",
        ):
            assert key not in app.settings_panel.setting_vars
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_base_plate_edge_shrink_commit_uses_canonical_settings_transaction_and_updates_dimensions():
    tk, root, win, app, bridge = _build_app()
    try:
        app.activate_part("base_plate")
        win.update_idletasks(); win.update()

        edits = {"TOP": 11.0, "BOTTOM": 22.0, "LEFT": 33.0, "RIGHT": 44.0}
        for edge, value in edits.items():
            app.base_plate_edge_shrink_vars[edge].set(str(value))
            assert bridge._phase6_commit_base_plate_edge_shrink(app, edge, str(value)) is True

        expected = {
            "base_plate_shrink_top": 11.0,
            "base_plate_shrink_bottom": 22.0,
            "base_plate_shrink_left": 33.0,
            "base_plate_shrink_right": 44.0,
        }
        for key, value in expected.items():
            assert app._settings_values[key] == pytest.approx(value)
            assert app._phase6_input_snapshot[key] == pytest.approx(value)

        dims = bridge._phase6_recalculate_part_dimensions(app)["base_plate"]
        assert dims["width"] == pytest.approx(float(app._settings_values["w"]) - 33.0 - 44.0)
        assert dims["height"] == pytest.approx(float(app._settings_values["h"]) - 11.0 - 22.0)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
