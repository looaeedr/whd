# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#435 T5 requires real Tk/Xvfb"
)


def _snapshot():
    return {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }


def _pump(root, cycles=2):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open(snapshot=None):
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, snapshot or _snapshot())
    _pump(root, 3)
    return root, app


def _surfaces(app):
    return (
        app.input_content_host,
        app.assembly_parts_panel,
        getattr(app, "corner_data_panel", None),
    )


def _mapped_surface_count(app):
    return sum(
        1 for widget in _surfaces(app)
        if widget is not None and widget.winfo_manager()
    )


def _cycle_modes(app, root):
    app.activate_part("head")
    _pump(root)
    bridge._phase6_show_assembly(app)
    _pump(root)
    bridge._phase6_show_corner_data(app)
    _pump(root)
    app.activate_part(app.designer_workspace.active_part)
    _pump(root)


def test_t5_repeated_three_mode_cycles_keep_one_host_and_one_surface_tree():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        host = app.shared_content_host
        fold = app.fold_editor_host
        input_surface = app.input_content_host
        assembly = app.assembly_parts_panel
        corner = app.corner_data_panel
        assembly_owner = app._phase6_assembly_panel_owner
        corner_adapter = bridge._phase6_corner_data_view(app)

        for _ in range(6):
            _cycle_modes(app, root)
            assert app.shared_content_host is host
            assert app.shared_content_host is app.left
            assert app.fold_editor_host is fold
            assert app.fold_editor_host is app.input_content_host
            assert app.input_content_host is input_surface
            assert app.assembly_parts_panel is assembly
            assert app.corner_data_panel is corner
            assert app._phase6_assembly_panel_owner is assembly_owner
            assert bridge._phase6_corner_data_view(app) is corner_adapter
            assert _mapped_surface_count(app) == 1

        owned = tuple(host.winfo_children())
        assert owned.count(input_surface) == 1
        assert owned.count(assembly) == 1
        assert owned.count(corner) == 1
    finally:
        root.destroy()


def test_t5_refresh_replaces_rows_without_leaving_stale_widget_references():
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        detail_registry = owner.detail_frames
        target = "head" if "head" in detail_registry else next(iter(detail_registry))
        old_detail = detail_registry[target]

        bridge._phase6_refresh_assembly_parts_panel(app)
        _pump(root)

        assert owner.detail_frames is detail_registry
        assert not bool(old_detail.winfo_exists())
        assert target in detail_registry
        assert bool(detail_registry[target].winfo_exists())
        assert detail_registry[target] is not old_detail

        bridge._phase6_show_corner_data(app)
        _pump(root)
        corner_rows = app.corner_data_part_rows
        corner_target = "head" if "head" in corner_rows else next(iter(corner_rows))
        old_row = corner_rows[corner_target]

        app._phase6_3d_display_mode = "assembly"
        bridge._phase6_mount_shared_content(app, "assembly")
        bridge._phase6_refresh_corner_data_parts_panel(app)
        _pump(root)

        assert not bool(old_row.winfo_exists())
        assert corner_target in app.corner_data_part_rows
        assert bool(app.corner_data_part_rows[corner_target].winfo_exists())
        assert app.corner_data_part_rows[corner_target] is not old_row
    finally:
        root.destroy()


def test_t5_repeated_refresh_does_not_multiply_owner_bindings_or_callbacks(monkeypatch):
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        callback = owner.actions.on_visibility_changed
        binding_before = {
            sequence: owner.canvas.bind(sequence)
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>")
        }
        assert all(binding_before.values())

        calls = []
        monkeypatch.setattr(
            bridge,
            "_phase6_on_assembly_part_visibility_changed",
            lambda _app: calls.append("visibility"),
        )

        for _ in range(5):
            bridge._phase6_refresh_assembly_parts_panel(app)
            _cycle_modes(app, root)

        binding_after = {
            sequence: owner.canvas.bind(sequence)
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>")
        }
        assert owner.actions.on_visibility_changed is callback
        assert binding_after == binding_before

        owner.notify_visibility_changed()
        assert calls == ["visibility"]
    finally:
        root.destroy()


def test_t5_export_reopen_preserves_domain_state_without_cross_instance_widgets():
    root1, app1 = _open()
    root2 = None
    try:
        app1.activate_part("head")
        _pump(root1)
        if "door" not in app1.designer_workspace.available_parts:
            bridge._fix11_add_part(app1, "door")
            _pump(root1)
        app1.activate_part("head")
        _pump(root1)

        before_parts = tuple(app1.designer_workspace.available_parts)
        before_active = app1.designer_workspace.active_part
        exported = bridge._phase6_build_project_snapshot(app1)["snapshot"]

        first_widgets = {
            id(app1.fold_editor_host),
            id(app1.input_content_host),
            id(app1.assembly_parts_panel),
        }

        assert exported.get("active_part") == before_active

        root2, app2 = _open(exported)
        bridge._phase6_show_corner_data(app2)
        _pump(root2)

        assert tuple(app2.designer_workspace.available_parts) == before_parts
        assert _mapped_surface_count(app2) == 1

        # Entering Fold Designer still follows the accepted startup contract:
        # assembly view is backed by box_body. The persisted active part must
        # remain available and be restorable without creating a second state owner.
        assert app2.designer_workspace.active_part == "box_body"
        app2.activate_part(before_active)
        _pump(root2)
        assert app2.designer_workspace.active_part == before_active
        assert _mapped_surface_count(app2) == 1

        second_widgets = {
            id(app2.fold_editor_host),
            id(app2.input_content_host),
            id(app2.assembly_parts_panel),
            id(app2.corner_data_panel),
        }
        assert first_widgets.isdisjoint(second_widgets)
    finally:
        if root2 is not None:
            root2.destroy()
        root1.destroy()


def test_t5_current_panel_owner_mousewheel_wrapper_has_no_exception_or_direction_drift(monkeypatch):
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        calls = []
        monkeypatch.setattr(
            owner.canvas,
            "yview_scroll",
            lambda steps, unit: calls.append((steps, unit)),
        )

        cases = (
            (SimpleNamespace(delta=120, num="??"), (-1, "units")),
            (SimpleNamespace(delta=-120, num="??"), (1, "units")),
            (SimpleNamespace(delta=0, num=4), (-1, "units")),
            (SimpleNamespace(delta=0, num=5), (1, "units")),
        )
        for event, expected in cases:
            calls.clear()
            assert app._phase6_assembly_panel_owner.scroll(event) == "break"
            assert calls == [expected]

        calls.clear()
        assert app._phase6_assembly_panel_owner.scroll(
            SimpleNamespace(delta="", num=None)
        ) == "break"
        assert calls == []
    finally:
        root.destroy()
