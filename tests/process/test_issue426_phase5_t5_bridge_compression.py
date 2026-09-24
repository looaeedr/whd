# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import inspect
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
import phase6_assembly_presentation as presentation
from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel


T0_BOUNDARY = (
    "_phase6_on_assembly_part_visibility_changed",
    "_phase6_assembly_presentation_groups",
    "_phase6_current_assembly_panel_part_keys",
    "_phase6_refresh_assembly_parts_panel_if_topology_changed",
    "_phase6_refresh_assembly_parts_panel",
    "_phase6_show_assembly",
)

CURRENT_REFRESH_CALLS = (
    (
        "_phase6_apply_settings_profile_projection",
        "_phase6_refresh_assembly_parts_panel_if_topology_changed",
    ),
    (
        "_phase6_refresh_assembly_parts_panel_if_topology_changed",
        "_phase6_refresh_assembly_parts_panel",
    ),
    ("_phase6_install_part_editor_compatibility", "_phase6_refresh_assembly_parts_panel"),
    ("_fix11_refresh_part_buttons", "_phase6_refresh_assembly_parts_panel"),
)


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


def _bridge_ast():
    text = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    return text, ast.parse(text)


def _function_source(name: str) -> str:
    """Return one accepted Bridge compatibility boundary.

    Phase 6 v1.4 allows behavior-identical thin delegates to collapse into a
    direct owner alias. Treat a top-level name = owner_callable assignment as
    the same compatibility boundary instead of requiring a FunctionDef.
    """
    text, tree = _bridge_ast()
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\\n".join(lines[node.lineno - 1:node.end_lineno])
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return "\\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"missing bridge compatibility boundary: {name}")




def _refresh_call_inventory():
    _, tree = _bridge_ast()
    targets = {
        "_phase6_refresh_assembly_parts_panel_if_topology_changed",
        "_phase6_refresh_assembly_parts_panel",
    }
    rows = []
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func.id if isinstance(node.func, ast.Name) else None
            if callee in targets:
                rows.append((fn.name, callee))
    return tuple(rows)


def test_t5_pure_owner_exposes_legacy_group_projection_and_bridge_is_thin_delegate():
    helper = getattr(presentation, "legacy_assembly_presentation_groups", None)
    assert callable(helper), (
        "T5 requirement RED: pure Assembly presentation grouping compatibility "
        "projection is missing"
    )

    values = (
        "box_body",
        "head",
        "door_c1_r1",
        "door_c1_r2",
        "base_plate_c1_r1",
        "base_plate_c1_r2",
        "tail",
    )
    expected = (
        ("box_body", ()),
        ("head", ()),
        ("door", ("door_c1_r1", "door_c1_r2")),
        ("base_plate", ("base_plate_c1_r1", "base_plate_c1_r2")),
        ("tail", ()),
    )
    assert helper(values) == expected
    assert bridge._phase6_assembly_presentation_groups(values) == expected

    source = _function_source("_phase6_assembly_presentation_groups")
    assert "legacy_assembly_presentation_groups" in source
    assert "build_assembly_presentation_model" not in source
    assert "for " not in source
    assert ".append(" not in source


def test_t5_refresh_callsite_inventory_tracks_accepted_owner_seams():
    # Phase 5 Settings ownership intentionally moved the former direct
    # baseline/profile refresh callsites behind application/projection owners.
    # Preserve the refresh policy, but bind the oracle to the accepted owners.
    assert _refresh_call_inventory() == CURRENT_REFRESH_CALLS


def test_t5_refresh_policy_keeps_fixed_root_conditional_and_unconditional_paths():
    conditional = _function_source(
        "_phase6_refresh_assembly_parts_panel_if_topology_changed"
    )
    assert "if current == wanted:" in conditional
    assert "return False" in conditional
    assert "_phase6_refresh_assembly_parts_panel(self)" in conditional

    refresh_buttons = _function_source("_fix11_refresh_part_buttons")
    assert 'getattr(self, "assembly_parts_panel", None) is not None' in refresh_buttons
    assert "_phase6_refresh_assembly_parts_panel(self)" in refresh_buttons

    installer = _function_source("_phase6_install_part_editor_compatibility")
    assert "_phase6_refresh_assembly_parts_panel(self)" in installer

    init = _function_source("_fix11_init")
    assert "_phase6_install_part_editor_compatibility(self)" in init
    assert "_phase6_refresh_assembly_parts_panel(self)" not in init


def test_t5_mount_unmount_transition_sources_match_shared_host_owner():
    show = _function_source("_phase6_show_assembly")
    corner = _function_source("_phase6_show_corner_data")
    activate = _function_source("_fix11_activate_part")

    # #429/#431 moved presentation mount ownership into the one shared-content
    # controller.  Bridge entrypoints select a mode; they must no longer pack
    # or forget the Assembly panel directly.
    assert '_phase6_mount_shared_content(self, "assembly")' in show
    assert '_phase6_mount_shared_content(self, "corner_data")' in corner
    assert '_phase6_mount_shared_content(self, "single")' in activate

    for source in (show, corner, activate):
        assert "assembly_panel.pack(" not in source
        assert "assembly_panel.pack_forget()" not in source


def test_t5_repeated_bridge_refresh_preserves_alias_identity_and_ui_state(tk_root):
    panel = Phase6AssemblyPanel(
        tk_root,
        actions=AssemblyPanelActions(on_visibility_changed=lambda: None),
    )
    fake = SimpleNamespace(
        _phase6_assembly_panel_owner=panel,
        _phase6_input_snapshot={},
        designer_workspace=SimpleNamespace(
            available_parts=("box_body", "head", "tail"),
        ),
    )
    bridge._phase6_install_assembly_panel_aliases(fake, panel)
    bridge._phase6_refresh_assembly_parts_panel(fake)

    alias_refs = {
        "assembly_part_visible_vars": fake.assembly_part_visible_vars,
        "assembly_part_corner_vars": fake.assembly_part_corner_vars,
        "assembly_part_formed_vars": fake.assembly_part_formed_vars,
        "assembly_part_blank_vars": fake.assembly_part_blank_vars,
        "assembly_part_detail_frames": fake.assembly_part_detail_frames,
        "assembly_presentation_group_detail_frames":
            fake.assembly_presentation_group_detail_frames,
        "assembly_box_body_piece_visible_vars":
            fake.assembly_box_body_piece_visible_vars,
        "assembly_box_body_piece_formed_vars":
            fake.assembly_box_body_piece_formed_vars,
    }

    fake.assembly_part_visible_vars["head"].set(False)
    fake.assembly_part_formed_vars["head"].set("成形尺寸：保留")
    panel.set_part_details_open("head", True)

    bridge._phase6_refresh_assembly_parts_panel(fake)
    bridge._phase6_refresh_assembly_parts_panel(fake)

    for name, ref in alias_refs.items():
        assert getattr(fake, name) is ref, f"stale legacy alias: {name}"
    assert bool(fake.assembly_part_visible_vars["head"].get()) is False
    assert fake.assembly_part_formed_vars["head"].get() == "成形尺寸：保留"
    assert fake.assembly_part_detail_frames["head"].winfo_manager() == "pack"



def test_t5_bridge_has_no_assembly_row_or_piece_row_tk_construction():
    logical = _function_source("_phase6_refresh_assembly_parts_panel")
    forbidden = (
        "ttk.Frame(",
        "ttk.Checkbutton(",
        "ttk.Label(",
        "ttk.Button(",
        "BooleanVar(",
        "StringVar(",
        "Canvas(",
        "create_window(",
    )
    for token in forbidden:
        assert token not in logical

    panel_source = inspect.getsource(Phase6AssemblyPanel.refresh_box_body_piece_info)
    assert "box_piece_" in panel_source

def test_t5_bridge_collapse_scroll_and_visibility_policy_are_delegation_only():
    panel_source = inspect.getsource(Phase6AssemblyPanel)
    for method in (
        "set_part_details_open",
        "toggle_part_details",
        "set_box_piece_details_open",
        "toggle_box_piece_details",
        "scroll",
        "bind_scroll",
        "resolve_visibility",
    ):
        assert f"def {method}(" in panel_source

    bridge_source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    for retired in (
        "_phase6_set_assembly_part_details_open",
        "_phase6_toggle_assembly_part_details",
        "_phase6_set_box_body_piece_details_open",
        "_phase6_toggle_box_body_piece_details",
        "_phase6_scroll_assembly_parts",
        "_phase6_bind_assembly_scroll",
        "_phase6_final_scene_visibility",
    ):
        assert f"def {retired}(" not in bridge_source


def test_t5_compatibility_boundary_count_does_not_grow():
    _, tree = _bridge_ast()
    names = {
        node.name for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            )
    present = tuple(name for name in T0_BOUNDARY if name in names)
    assert present == T0_BOUNDARY
    assert len(present) == 6

def test_t5_legacy_alias_installer_keeps_t0_proven_registry_names():
    source = _function_source("_phase6_install_assembly_panel_aliases")
    expected = {
        "assembly_parts_panel": "host",
        "assembly_parts_canvas": "canvas",
        "assembly_parts_content": "content",
        "assembly_part_visible_vars": "visible_vars",
        "assembly_part_corner_vars": "corner_vars",
        "assembly_part_formed_vars": "formed_vars",
        "assembly_part_blank_vars": "blank_vars",
        "assembly_part_sections": "sections",
        "assembly_part_detail_frames": "detail_frames",
        "assembly_part_detail_buttons": "detail_buttons",
        "assembly_presentation_group_sections": "group_sections",
        "assembly_presentation_group_detail_frames": "group_detail_frames",
        "assembly_presentation_group_detail_buttons": "group_detail_buttons",
        "assembly_box_body_piece_visible_vars": "box_piece_visible_vars",
        "assembly_box_body_piece_formed_vars": "box_piece_formed_vars",
        "assembly_box_body_piece_blank_vars": "box_piece_blank_vars",
        "assembly_box_body_piece_corner_vars": "box_piece_corner_vars",
    }
    for legacy, owner in expected.items():
        assert f"self.{legacy} = owner.{owner}" in source



def test_t5_corner_snapshot_is_retained_because_t0_has_test_reader():
    source = inspect.getsource(Phase6AssemblyPanel.set_corner_texts)
    assert "corner_vars" in source
    bridge_source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "def _phase6_final_scene_corner_text_sink(" not in bridge_source

def test_t5_right_diagnostics_remain_outside_assembly_compression_boundary():
    for name in T0_BOUNDARY:
        source = _function_source(name)
        assert "assembly_diagnostics_frame" not in source or name == "_phase6_show_assembly"
    # _phase6_show_assembly owns the existing mount/event seam only; T5 must not
    # move right-side diagnostics construction or diagnostics logic into panel.
    panel_source = inspect.getsource(__import__("phase6_assembly_panel"))
    assert "assembly_diagnostics_frame" not in panel_source
    assert "diagnostic" not in panel_source.lower()
