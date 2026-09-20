# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import importlib.util
import inspect
import tkinter as tk
from dataclasses import FrozenInstanceError

import pytest

from phase6_assembly_presentation import (
    AssemblyPresentationModel,
    AssemblyPresentationRow,
    AssemblySyntheticGroup,
)


MODULE = "phase6_assembly_panel"


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


def _module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, (
        "T2 requirement RED: phase6_assembly_panel.py does not exist yet"
    )
    return importlib.import_module(MODULE)


def _model():
    return AssemblyPresentationModel(
        entries=(
            AssemblyPresentationRow(
                part_key="box_body",
                label="箱身",
                visible_seed=True,
                formed_text_seed="成形尺寸：等待3D",
                blank_text_seed="展開料：等待3D",
                corner_text_seed="截角尺寸：等待3D",
                has_piece_host=True,
            ),
            AssemblySyntheticGroup(
                presentation_key="door",
                label="門",
                children=(
                    AssemblyPresentationRow(
                        part_key="door_c1_r1",
                        label="上門",
                        visible_seed=True,
                        formed_text_seed="成形尺寸：A",
                        blank_text_seed="展開料：A",
                        corner_text_seed="截角尺寸：A",
                    ),
                    AssemblyPresentationRow(
                        part_key="door_c1_r2",
                        label="下門",
                        visible_seed=False,
                        formed_text_seed="成形尺寸：B",
                        blank_text_seed="展開料：B",
                        corner_text_seed="截角尺寸：B",
                    ),
                ),
            ),
            AssemblyPresentationRow(
                part_key="head",
                label="封頭",
                visible_seed=True,
                formed_text_seed="成形尺寸：H",
                blank_text_seed="展開料：H",
                corner_text_seed="截角尺寸：H",
            ),
        )
    )


def _make_panel(root, on_visibility_changed=lambda: None):
    m = _module()
    actions = m.AssemblyPanelActions(on_visibility_changed=on_visibility_changed)
    panel = m.Phase6AssemblyPanel(root, actions=actions)
    return m, panel


def test_t2_actions_contract_is_frozen_and_narrow():
    m = _module()
    actions = m.AssemblyPanelActions(on_visibility_changed=lambda: None)
    with pytest.raises(FrozenInstanceError):
        actions.on_visibility_changed = lambda: None
    assert tuple(actions.__dataclass_fields__) == ("on_visibility_changed",)


def test_t2_panel_builds_host_canvas_scrollbar_and_content(tk_root):
    _, panel = _make_panel(tk_root)

    assert panel.host.winfo_exists()
    assert panel.canvas.winfo_exists()
    assert panel.scrollbar.winfo_exists()
    assert panel.content.winfo_exists()
    assert panel.canvas.cget("yscrollcommand")
    assert panel.scrollbar.cget("command")
    assert panel.canvas.type(panel.window_id) == "window"


def test_t2_render_owns_top_level_and_synthetic_child_vars_without_group_visibility(tk_root):
    _, panel = _make_panel(tk_root)
    panel.render(_model())

    assert tuple(panel.visible_vars) == (
        "box_body",
        "door_c1_r1",
        "door_c1_r2",
        "head",
    )
    assert bool(panel.visible_vars["box_body"].get()) is True
    assert bool(panel.visible_vars["door_c1_r2"].get()) is False

    assert "door" in panel.group_sections
    assert "door" in panel.group_detail_frames
    assert "door" in panel.group_detail_buttons
    assert "door" not in panel.visible_vars
    assert "door" not in panel.formed_vars
    assert "door" not in panel.blank_vars
    assert "door" not in panel.corner_vars

    assert panel.box_body_piece_host is not None
    assert tuple(panel.formed_vars) == tuple(panel.visible_vars)
    assert tuple(panel.blank_vars) == tuple(panel.visible_vars)
    assert tuple(panel.corner_vars) == tuple(panel.visible_vars)


def test_t2_registry_dict_identity_survives_rebuild(tk_root):
    _, panel = _make_panel(tk_root)
    panel.render(_model())

    identities = {
        "visible_vars": panel.visible_vars,
        "formed_vars": panel.formed_vars,
        "blank_vars": panel.blank_vars,
        "corner_vars": panel.corner_vars,
        "checkbuttons": panel.checkbuttons,
        "sections": panel.sections,
        "detail_frames": panel.detail_frames,
        "detail_buttons": panel.detail_buttons,
        "group_sections": panel.group_sections,
        "group_detail_frames": panel.group_detail_frames,
        "group_detail_buttons": panel.group_detail_buttons,
    }

    panel.visible_vars["door_c1_r2"].set(True)
    panel.formed_vars["head"].set("成形尺寸：保留")
    panel.set_part_details_open("head", True)
    panel.set_group_open("door", True)

    panel.render(_model())

    for name, before in identities.items():
        assert getattr(panel, name) is before, f"{name} dict identity changed"

    assert bool(panel.visible_vars["door_c1_r2"].get()) is True
    assert panel.formed_vars["head"].get() == "成形尺寸：保留"
    assert panel.detail_frames["head"].winfo_manager()
    assert panel.group_detail_frames["door"].winfo_manager()


def test_t2_legacy_aliases_can_point_to_long_lived_registries(tk_root):
    _, panel = _make_panel(tk_root)
    panel.render(_model())

    legacy_visible = panel.visible_vars
    legacy_details = panel.detail_frames
    legacy_groups = panel.group_detail_frames

    panel.render(
        AssemblyPresentationModel(
            entries=(
                AssemblyPresentationRow(
                    part_key="box_body",
                    label="箱身",
                    visible_seed=True,
                    has_piece_host=True,
                ),
                AssemblyPresentationRow(
                    part_key="tail",
                    label="封尾",
                    visible_seed=True,
                ),
            )
        )
    )

    assert legacy_visible is panel.visible_vars
    assert legacy_details is panel.detail_frames
    assert legacy_groups is panel.group_detail_frames
    assert tuple(legacy_visible) == ("box_body", "tail")
    assert "door_c1_r1" not in legacy_visible
    assert "door" not in legacy_groups


@pytest.mark.parametrize(
    ("delta", "num", "expected"),
    [
        (120, 0, -1),
        (-120, 0, 1),
        (0, 4, -1),
        (0, 5, 1),
        ("bad", 0, None),
        (0, "bad", None),
        (0, 0, None),
    ],
)
def test_t2_scroll_direction_and_malformed_event_safety(
    tk_root, monkeypatch, delta, num, expected
):
    _, panel = _make_panel(tk_root)
    calls = []
    monkeypatch.setattr(panel.canvas, "yview_scroll", lambda steps, units: calls.append((steps, units)))
    event = type("Event", (), {"delta": delta, "num": num})()

    assert panel.scroll(event) == "break"
    if expected is None:
        assert calls == []
    else:
        assert calls == [(expected, "units")]


def test_t2_recursive_wheel_binding_covers_base_rows_and_group_children(tk_root):
    _, panel = _make_panel(tk_root)
    panel.render(_model())

    widgets = [
        panel.canvas,
        panel.content,
        panel.sections["box_body"],
        panel.sections["door_c1_r1"],
        panel.sections["door_c1_r2"],
        panel.sections["head"],
        panel.group_sections["door"],
    ]
    for widget in widgets:
        assert widget.bind("<MouseWheel>")
        assert widget.bind("<Button-4>")
        assert widget.bind("<Button-5>")


def test_t2_visibility_command_routes_only_through_explicit_action(tk_root):
    calls = []
    _, panel = _make_panel(tk_root, on_visibility_changed=lambda: calls.append("changed"))
    panel.render(_model())

    panel.checkbuttons["head"].invoke()
    assert calls == ["changed"]


def test_t2_collapse_is_presentation_only_and_updates_stash(tk_root):
    _, panel = _make_panel(tk_root)
    panel.render(_model())

    visible_before = bool(panel.visible_vars["head"].get())
    assert panel.set_part_details_open("head", True) is True
    assert panel.detail_open_stash["head"] is True
    assert panel.detail_frames["head"].winfo_manager()

    assert panel.set_part_details_open("head", False) is False
    assert panel.detail_open_stash["head"] is False
    assert not panel.detail_frames["head"].winfo_manager()
    assert bool(panel.visible_vars["head"].get()) is visible_before

    assert panel.set_group_open("door", True) is True
    assert panel.group_open_stash["door"] is True
    assert panel.group_detail_frames["door"].winfo_manager()
    assert "door" not in panel.visible_vars


def test_t2_module_has_no_bridge_app_display_mode_or_manufacturing_authority():
    m = _module()
    source = inspect.getsource(m)
    lower = source.lower()

    assert "fold_designer_bridge" not in source
    assert "designer_workspace" not in source
    assert "_phase6_3d_display_mode" not in source
    assert "display_mode" not in source
    assert "resolve_geometry(" not in source
    assert "manufacturing_api" not in source
    assert "project_controller" not in source
    assert "assembly_box_body_piece_visible_vars" not in source
    assert "project_box_body_piece_rows" not in source
