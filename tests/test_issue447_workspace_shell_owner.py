# -*- coding: utf-8 -*-
"""Issue #447 / T5 Workspace Shell deletion-test contracts."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ROUTER = ROOT / "gui_modules" / "application" / "command_router.py"
CENSUS = ROOT / "docs" / "superpowers" / "checkpoints" / "issue447-t5-workspace-shell-census.md"
PROSPECTIVE_SHELL = ROOT / "phase6_workspace_shell.py"

SINGLE_CALLER_BUILDERS = {
    "_phase6_build_persistent_top_area",
    "_phase6_build_project_toolbar",
    "_phase6_build_transaction_buttons",
    "_phase6_build_global_persistent_controls",
    "_phase6_build_output_controls",
    "_phase6_build_visual_controls",
    "_phase6_install_keyboard_shortcuts",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_functions(path: Path) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in _tree(path).body
        if isinstance(node, ast.FunctionDef)
    }


def _name_call_count(path: Path, name: str) -> int:
    tree = _tree(path)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def test_t5_deletion_test_accepts_no_extraction_instead_of_shallow_wrapper():
    text = CENSUS.read_text(encoding="utf-8")
    assert "DECISION=NO_EXTRACTION" in text
    assert not PROSPECTIVE_SHELL.exists(), (
        "T5 decision forbids creating a shallow phase6_workspace_shell.py wrapper"
    )


def test_t5_shell_composition_and_subbuilders_remain_single_caller():
    funcs = _top_level_functions(BRIDGE)
    missing = sorted(SINGLE_CALLER_BUILDERS - set(funcs))
    assert not missing, f"accepted shell composition functions disappeared: {missing}"
    counts = {name: _name_call_count(BRIDGE, name) for name in SINGLE_CALLER_BUILDERS}
    assert counts == {name: 1 for name in SINGLE_CALLER_BUILDERS}, (
        f"shell callback/build multiplication detected: {counts}"
    )


def test_t5_fullscreen_has_one_state_owner_and_two_routes_only():
    source = BRIDGE.read_text(encoding="utf-8")
    funcs = _top_level_functions(BRIDGE)
    assert "_phase6_toggle_fullscreen" in funcs
    # One direct F11 adapter route + one button route. Definition is not counted here.
    assert _name_call_count(BRIDGE, "_phase6_toggle_fullscreen") == 2
    assert source.count("self._phase6_fullscreen =") >= 2
    assert "phase6_workspace_shell" not in source


def test_t5_keyboard_binding_loop_has_one_bridge_installer():
    bridge = BRIDGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    assert bridge.count("install_fold_designer_keyboard_shortcuts(") == 1
    assert router.count('root.bind("<F11>", on_fullscreen, add="+")') == 1
    assert router.count('root.bind(sequence, on_save, add="+")') == 1
    assert router.count('root.bind(sequence, on_open, add="+")') == 1


def test_t5_shared_content_source_keeps_direct_single_slot_mounting():
    funcs = _top_level_functions(BRIDGE)
    mount = ast.get_source_segment(
        BRIDGE.read_text(encoding="utf-8"),
        funcs["_phase6_mount_shared_content"],
    ) or ""
    assert '"single": getattr(self, "input_content_host", None)' in mount
    assert '"assembly": getattr(self, "assembly_parts_panel", None)' in mount
    assert '"corner_data": getattr(self, "corner_data_panel", None)' in mount
    assert "widget.pack_forget()" in mount
    assert "shared_content_host = self.left" in BRIDGE.read_text(encoding="utf-8")


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#447 runtime shell contract requires real Tk/Xvfb")
def test_t5_runtime_active_mode_surface_count_is_exactly_one_without_separate_regions():
    import fold_designer_bridge as bridge

    snapshot = {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, snapshot)
    try:
        for _ in range(3):
            root.update_idletasks()
            root.update()

        def mapped():
            return tuple(
                widget
                for widget in (
                    app.input_content_host,
                    app.assembly_parts_panel,
                    getattr(app, "corner_data_panel", None),
                )
                if widget is not None and widget.winfo_manager()
            )

        app.activate_part("head")
        root.update_idletasks(); root.update()
        assert mapped() == (app.input_content_host,)

        bridge._phase6_show_assembly(app)
        root.update_idletasks(); root.update()
        assert mapped() == (app.assembly_parts_panel,)

        bridge._phase6_show_corner_data(app)
        root.update_idletasks(); root.update()
        assert mapped() == (app.corner_data_panel,)

        assert app.shared_content_host is app.left
        assert app.input_content_host.master is app.left
        assert app.assembly_parts_panel.master is app.left
        assert app.corner_data_panel.master is app.left
        assert not hasattr(app, "_phase6_physical_content_height")
    finally:
        root.destroy()
