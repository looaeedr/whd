# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import inspect
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
from phase6_assembly_presentation import (
    AssemblyPresentationModel,
    AssemblyPresentationRow,
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


def _panel(root):
    panel = Phase6AssemblyPanel(
        root,
        actions=AssemblyPanelActions(on_visibility_changed=lambda: None),
    )
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
                    part_key="head",
                    label="封頭",
                    visible_seed=True,
                ),
            )
        )
    )
    return panel


def _piece(role, formed, blank, corner, *, key=""):
    return SimpleNamespace(
        role=role,
        key=key,
        formed_outer_dimensions=formed,
        material_dimensions=blank,
        render_data=SimpleNamespace(corner=corner),
    )


def _render_data(*pieces):
    return SimpleNamespace(pieces=tuple(pieces))


def _refresh(panel, render_data):
    method = getattr(panel, "refresh_box_body_piece_info", None)
    assert callable(method), (
        "T3 requirement RED: Phase6AssemblyPanel.refresh_box_body_piece_info is missing"
    )
    return method(
        render_data,
        label_for=lambda key: f"L:{key}",
        number_text=lambda value: f"N{float(value):g}",
        corner_text_for_render_data=lambda data: f"截角尺寸：{data.corner}",
    )


def _function_source(path: str, name: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = text.splitlines()
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"missing function: {name}")


def test_t3_panel_owns_late_piece_registries_and_render_time_order(tk_root):
    panel = _panel(tk_root)
    rows = _refresh(
        panel,
        _render_data(
            _piece("left_side", (101, 201), (111, 211), "A"),
            _piece("back", (301, 401), (311, 411), "B"),
            _piece("right_side", (501, 601), (511, 611), "C"),
        ),
    )

    assert tuple(row.part_key for row in rows) == (
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
    )
    assert tuple(panel.box_piece_visible_vars) == tuple(row.part_key for row in rows)
    assert tuple(panel.box_piece_sections) == tuple(panel.box_piece_visible_vars)
    assert tuple(panel.box_piece_formed_vars) == tuple(panel.box_piece_visible_vars)
    assert tuple(panel.box_piece_blank_vars) == tuple(panel.box_piece_visible_vars)
    assert tuple(panel.box_piece_corner_vars) == tuple(panel.box_piece_visible_vars)
    assert all(bool(var.get()) for var in panel.box_piece_visible_vars.values())


def test_t3_same_keys_refresh_text_without_row_rebuild(tk_root):
    panel = _panel(tk_root)
    first = _render_data(
        _piece("left_side", (101, 201), (111, 211), "A"),
        _piece("back", (301, 401), (311, 411), "B"),
    )
    _refresh(panel, first)
    before_sections = dict(panel.box_piece_sections)

    second = _render_data(
        _piece("left_side", (102, 202), (112, 212), "A2"),
        _piece("back", (302, 402), (312, 412), "B2"),
    )
    _refresh(panel, second)

    assert panel.box_piece_sections == before_sections
    for key, widget in before_sections.items():
        assert panel.box_piece_sections[key] is widget

    assert panel.box_piece_formed_vars["box_body:left_side"].get() == (
        "成形尺寸：N102 × N202 mm"
    )
    assert panel.box_piece_blank_vars["box_body:left_side"].get() == (
        "展開料：N112 × N212 mm"
    )
    assert panel.box_piece_corner_vars["box_body:left_side"].get() == "截角尺寸：A2"


def test_t3_number_and_corner_formatters_are_narrow_injected_seams(tk_root):
    panel = _panel(tk_root)
    number_calls = []
    corner_calls = []

    method = getattr(panel, "refresh_box_body_piece_info", None)
    assert callable(method), (
        "T3 requirement RED: Phase6AssemblyPanel.refresh_box_body_piece_info is missing"
    )
    method(
        _render_data(_piece("back", (10.5, 20.25), (30.5, 40.25), "C1")),
        label_for=str,
        number_text=lambda value: number_calls.append(float(value)) or f"F{value}",
        corner_text_for_render_data=lambda data: corner_calls.append(data) or f"C:{data.corner}",
    )

    assert number_calls == [10.5, 20.25, 30.5, 40.25]
    assert len(corner_calls) == 1
    assert panel.box_piece_formed_vars["box_body:back"].get() == (
        "成形尺寸：F10.5 × F20.25 mm"
    )
    assert panel.box_piece_blank_vars["box_body:back"].get() == (
        "展開料：F30.5 × F40.25 mm"
    )
    assert panel.box_piece_corner_vars["box_body:back"].get() == "C:C1"


def test_t3_missing_projected_role_uses_exact_corner_fallback(tk_root):
    panel = _panel(tk_root)
    _refresh(
        panel,
        _render_data(
            _piece(
                "",
                (10, 20),
                (30, 40),
                "must-not-be-used",
                key="box_body:legacy_piece",
            )
        ),
    )
    assert panel.box_piece_corner_vars["box_body:legacy_piece"].get() == "截角尺寸：無"


def test_t3_nonempty_piece_projection_rewrites_logical_box_body_summary(tk_root):
    panel = _panel(tk_root)
    _refresh(
        panel,
        _render_data(_piece("back", (10, 20), (30, 40), "C")),
    )
    assert panel.formed_vars["box_body"].get() == "成形尺寸：見下方各片"
    assert panel.blank_vars["box_body"].get() == "展開料：見下方各片"
    assert panel.corner_vars["box_body"].get() == "截角尺寸：見下方各片"


def test_t3_piece_visibility_stash_survives_panel_rebuild_before_next_render(tk_root):
    panel = _panel(tk_root)
    data = _render_data(
        _piece("left_side", (10, 20), (30, 40), "L"),
        _piece("back", (50, 60), (70, 80), "B"),
    )
    _refresh(panel, data)
    panel.box_piece_visible_vars["box_body:back"].set(False)
    panel.set_box_piece_details_open("box_body:back", True)

    visible_dict = panel.box_piece_visible_vars
    detail_dict = panel.box_piece_detail_frames

    panel.render(
        AssemblyPresentationModel(
            entries=(
                AssemblyPresentationRow(
                    part_key="box_body",
                    label="箱身",
                    visible_seed=True,
                    has_piece_host=True,
                ),
            )
        )
    )
    assert panel.box_piece_visible_vars is visible_dict
    assert panel.box_piece_detail_frames is detail_dict
    assert tuple(panel.box_piece_visible_vars) == ()

    _refresh(panel, data)
    assert bool(panel.box_piece_visible_vars["box_body:back"].get()) is False
    assert panel.box_piece_detail_frames["box_body:back"].winfo_manager() == "pack"


def test_t3_piece_registry_identity_survives_piece_topology_change(tk_root):
    panel = _panel(tk_root)
    _refresh(panel, _render_data(_piece("back", (1, 2), (3, 4), "A")))
    refs = {
        "box_piece_visible_vars": panel.box_piece_visible_vars,
        "box_piece_sections": panel.box_piece_sections,
        "box_piece_detail_frames": panel.box_piece_detail_frames,
        "box_piece_formed_vars": panel.box_piece_formed_vars,
        "box_piece_blank_vars": panel.box_piece_blank_vars,
        "box_piece_corner_vars": panel.box_piece_corner_vars,
    }

    _refresh(
        panel,
        _render_data(
            _piece("left_side", (5, 6), (7, 8), "B"),
            _piece("right_side", (9, 10), (11, 12), "C"),
        ),
    )
    for name, ref in refs.items():
        assert getattr(panel, name) is ref


def test_t3_late_piece_rows_have_recursive_wheel_binding(tk_root):
    panel = _panel(tk_root)
    _refresh(panel, _render_data(_piece("back", (1, 2), (3, 4), "A")))
    key = "box_body:back"
    widgets = [
        panel.box_piece_sections[key],
        panel.box_piece_checkbuttons[key],
        panel.box_piece_detail_buttons[key],
        panel.box_piece_detail_frames[key],
    ]
    for widget in widgets:
        assert widget.bind("<MouseWheel>")
        assert widget.bind("<Button-4>")
        assert widget.bind("<Button-5>")


def test_t3_piece_collapse_is_presentation_only(tk_root):
    panel = _panel(tk_root)
    _refresh(panel, _render_data(_piece("back", (1, 2), (3, 4), "A")))
    key = "box_body:back"
    visible = panel.box_piece_visible_vars[key]
    before = bool(visible.get())

    assert panel.set_box_piece_details_open(key, True) is True
    assert panel.box_piece_detail_frames[key].winfo_manager() == "pack"
    assert bool(visible.get()) is before
    assert panel.set_box_piece_details_open(key, False) is False
    assert panel.box_piece_detail_frames[key].winfo_manager() == ""
    assert bool(visible.get()) is before


def test_t3_panel_source_uses_pure_projection_without_dm7_or_settings_import():
    source = inspect.getsource(__import__("phase6_assembly_panel"))
    assert "project_box_body_piece_rows" in source
    assert 'getattr(render_data, "pieces"' in source
    assert "phase6_part_navigation" not in source
    assert "phase6_settings_panel" not in source
    assert "setting_number_text" not in source
    assert "fold_designer_bridge" not in source



def test_t3_bridge_piece_refresh_is_thin_delegate_with_existing_formatters():
    source = _function_source(
        "phase6_assembly_panel.py",
        "refresh_box_body_piece_info",
    )
    assert "label_for" in source
    assert "number_text" in source
    assert "corner_text_for_render_data" in source
    bridge = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "def _phase6_refresh_box_body_piece_info_rows(" not in bridge

def test_t3_bridge_legacy_piece_aliases_point_to_panel_registries():
    source = _function_source(
        "fold_designer_bridge.py",
        "_phase6_install_assembly_panel_aliases",
    )
    expected = {
        "assembly_box_body_piece_labels": "box_piece_labels",
        "assembly_box_body_piece_sections": "box_piece_sections",
        "assembly_box_body_piece_visible_vars": "box_piece_visible_vars",
        "assembly_box_body_piece_checkbuttons": "box_piece_checkbuttons",
        "assembly_box_body_piece_detail_frames": "box_piece_detail_frames",
        "assembly_box_body_piece_detail_buttons": "box_piece_detail_buttons",
        "assembly_box_body_piece_formed_vars": "box_piece_formed_vars",
        "assembly_box_body_piece_blank_vars": "box_piece_blank_vars",
        "assembly_box_body_piece_corner_vars": "box_piece_corner_vars",
    }
    for legacy, owner in expected.items():
        assert f"self.{legacy} = owner.{owner}" in source


def test_t3_final_scene_callback_timing_remains_render_time_box_body_only():
    source = _function_source(
        "phase6_final_scene_view.py",
        "query_assembly_render_data",
    )
    assert 'if part.part_key == "box_body" and callable(refresh_box_body):' in source
    assert "refresh_box_body(part.render_data)" in source
