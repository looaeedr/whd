# -*- coding: utf-8 -*-
"""Issue #447 superseded by Phase 6 v1.4 / #527 B2 Workspace Shell contracts."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ROUTER = ROOT / "gui_modules" / "application" / "command_router.py"
PRIOR_CENSUS = ROOT / "docs" / "superpowers" / "checkpoints" / "issue447-t5-workspace-shell-census.md"
SHELL = ROOT / "phase6_workspace_shell.py"

SHELL_COMPAT_FUNCTIONS = {
    "_phase6_build_persistent_top_area",
    "_phase6_build_project_toolbar",
    "_phase6_toggle_fullscreen",
    "_phase6_mount_shared_content",
}
C0_ZERO_CONSUMER_REMOVED = {
    "_phase6_build_transaction_buttons": "build_transaction_buttons",
    "_phase6_build_global_persistent_controls": "build_global_persistent_controls",
    "_phase6_build_output_controls": "build_output_controls",
    "_phase6_build_visual_controls": "build_visual_controls",
}
MAX_COMPAT_SPAN = 36


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


def _imports(path: Path) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_b2_supersedes_no_extraction_with_deep_shell_owner():
    prior = PRIOR_CENSUS.read_text(encoding="utf-8")
    assert "DECISION=NO_EXTRACTION" in prior  # provenance remains historical
    assert SHELL.is_file(), (
        "B2 RED: v1.4 Deletion-Test selected B2_EXTRACT_DEEP_SHELL_OWNER"
    )
    imports = _imports(SHELL)
    forbidden = {
        "fold_designer_bridge",
        "phase6_manufacturing_geometry",
        "phase6_manufacturing_service",
        "ae_engine.manufacturing",
    }
    assert not (imports & forbidden)
    source = SHELL.read_text(encoding="utf-8")
    assert "class WorkspaceShellOwner" in source
    assert "WorkspaceShellActions" in source
    assert "self.app" not in source
    assert "full_app" not in source.lower()


def test_b2_bridge_shell_compatibility_surface_is_thin():
    funcs = _top_level_functions(BRIDGE)
    missing = sorted(SHELL_COMPAT_FUNCTIONS - set(funcs))
    assert not missing
    assert C0_ZERO_CONSUMER_REMOVED.keys().isdisjoint(funcs)
    oversized = {
        name: _span(funcs[name])
        for name in sorted(SHELL_COMPAT_FUNCTIONS)
        if _span(funcs[name]) > MAX_COMPAT_SPAN
    }
    assert oversized == {}, f"B2 RED: bridge still owns deep shell bodies: {oversized}"

    shell_tree = _tree(SHELL)
    owner = next(
        node
        for node in shell_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "WorkspaceShellOwner"
    )
    owner_methods = {
        node.name
        for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(C0_ZERO_CONSUMER_REMOVED.values()) <= owner_methods


def test_b2_fullscreen_routes_to_shell_owner_without_second_binding_loop():
    bridge = BRIDGE.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    assert "toggle_fullscreen(" in shell
    assert _name_call_count(BRIDGE, "_phase6_toggle_fullscreen") == 2
    assert router.count('root.bind("<F11>", on_fullscreen, add="+")') == 1
    assert router.count('root.bind(sequence, on_save, add="+")') == 1
    assert router.count('root.bind(sequence, on_open, add="+")') == 1
    assert "phase6_workspace_shell" in bridge


def test_b2_shared_content_policy_moves_to_shell_owner():
    bridge_funcs = _top_level_functions(BRIDGE)
    mount = ast.get_source_segment(
        BRIDGE.read_text(encoding="utf-8"),
        bridge_funcs["_phase6_mount_shared_content"],
    ) or ""
    shell = SHELL.read_text(encoding="utf-8")
    assert "mount_shared_content" in shell
    assert "input_content_host" in mount
    assert "assembly_parts_panel" in mount
    assert "corner_data_panel" in mount
    assert "shared_content_host = self.left" in BRIDGE.read_text(encoding="utf-8")


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#527 runtime shell contract requires real Tk/Xvfb")
def test_b2_runtime_active_mode_surface_count_is_exactly_one_without_separate_regions():
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
