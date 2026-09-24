# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import inspect
import re
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
from phase6_assembly_presentation import (
    AssemblyPresentationModel,
    AssemblyPresentationRow,
)
from phase6_final_scene_view import Phase6FinalSceneViewAdapter


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


def _panel(root, calls=None):
    calls = calls if calls is not None else []
    panel = Phase6AssemblyPanel(
        root,
        actions=AssemblyPanelActions(
            on_visibility_changed=lambda: calls.append("changed")
        ),
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
                AssemblyPresentationRow(
                    part_key="tail",
                    label="封尾",
                    visible_seed=True,
                ),
            )
        )
    )
    return panel


def _require_t4_methods(panel):
    names = (
        "set_corner_texts",
        "set_part_text",
        "resolve_visibility",
        "visibility_var",
        "notify_visibility_changed",
    )
    for name in names:
        assert callable(getattr(panel, name, None)), (
            "T4 requirement RED: Phase6AssemblyPanel Final Scene/visibility ports are missing"
        )


def _piece(role, formed=(100, 200), blank=(110, 210), corner="C"):
    return SimpleNamespace(
        role=role,
        formed_outer_dimensions=formed,
        material_dimensions=blank,
        render_data=SimpleNamespace(corner=corner),
    )


def _part(key, pieces=()):
    return SimpleNamespace(
        part_key=key,
        render_data=SimpleNamespace(pieces=tuple(pieces)),
    )


def _refresh_pieces(panel, pieces):
    return panel.refresh_box_body_piece_info(
        SimpleNamespace(pieces=tuple(pieces)),
        label_for=str,
        number_text=lambda value: str(value),
        corner_text_for_render_data=lambda data: f"截角尺寸：{data.corner}",
    )


def _function_source(path: str, name: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"missing function: {name}")


def test_t4_panel_owns_final_scene_text_and_visibility_ports(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)


def test_t4_corner_and_part_text_sink_parity_is_lossy_and_read_only(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)

    panel.set_corner_texts({"head": 123, "missing": "drop"})
    assert panel.corner_vars["head"].get() == "123"

    panel.set_part_text("formed", "head", "formed-1")
    assert panel.formed_vars["head"].get() == "formed-1"

    panel.set_part_text("blank", "head", "blank-1")
    assert panel.blank_vars["head"].get() == "blank-1"

    # Preserve legacy sink behavior: anything except exact "formed" targets
    # the blank map. Final Scene producers are separately locked to formed/blank.
    panel.set_part_text("unknown", "head", "blank-via-legacy-fallback")
    assert panel.blank_vars["head"].get() == "blank-via-legacy-fallback"

    # Missing targets silently drop.
    panel.set_corner_texts({"does-not-exist": "x"})
    panel.set_part_text("formed", "does-not-exist", "x")
    panel.set_part_text("blank", "does-not-exist", "x")


def test_t4_top_level_all_hidden_falls_back_to_box_body_and_writes_var(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)
    for var in panel.visible_vars.values():
        var.set(False)

    visible, pieces = panel.resolve_visibility(
        (
            _part("head"),
            _part("box_body"),
            _part("tail"),
        )
    )
    assert visible == ("box_body",)
    assert pieces is None
    assert bool(panel.visible_vars["box_body"].get()) is True


def test_t4_top_level_fallback_uses_first_part_when_box_body_absent(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)
    panel.visible_vars["head"].set(False)
    panel.visible_vars["tail"].set(False)

    visible, pieces = panel.resolve_visibility((_part("tail"), _part("head")))
    assert visible == ("tail",)
    assert pieces is None
    assert bool(panel.visible_vars["tail"].get()) is True


def test_t4_box_piece_visibility_tristate_and_fallback_writeback(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)
    pieces = (_piece("left_side"), _piece("back"))
    _refresh_pieces(panel, pieces)

    panel.visible_vars["head"].set(False)
    panel.visible_vars["tail"].set(False)
    panel.visible_vars["box_body"].set(True)

    # Non-empty tuple.
    panel.box_piece_visible_vars["box_body:left_side"].set(False)
    panel.box_piece_visible_vars["box_body:back"].set(True)
    visible, piece_keys = panel.resolve_visibility((_part("box_body", pieces),))
    assert visible == ("box_body",)
    assert piece_keys == ("box_body:back",)

    # Explicit none visible is repaired only when BoxBody is the sole visible
    # top-level part; first piece is written back True.
    for var in panel.box_piece_visible_vars.values():
        var.set(False)
    visible, piece_keys = panel.resolve_visibility((_part("box_body", pieces),))
    assert visible == ("box_body",)
    assert piece_keys == ("box_body:left_side",)
    assert bool(panel.box_piece_visible_vars["box_body:left_side"].get()) is True

    # Logical BoxBody hidden => explicit empty tuple.
    panel.visible_vars["box_body"].set(False)
    panel.visible_vars["head"].set(True)
    visible, piece_keys = panel.resolve_visibility(
        (_part("box_body", pieces), _part("head"))
    )
    assert visible == ("head",)
    assert piece_keys == ()

    # No physical piece keys => None.
    panel.visible_vars["box_body"].set(True)
    panel.visible_vars["head"].set(False)
    visible, piece_keys = panel.resolve_visibility((_part("box_body", ()),))
    assert visible == ("box_body",)
    assert piece_keys is None


def test_t4_registry_empty_piece_vars_default_visible_without_second_store(tk_root):
    panel = _panel(tk_root)
    _require_t4_methods(panel)
    pieces = (_piece("left_side"), _piece("back"))

    # Before first render-time piece refresh, the registry is empty. Legacy
    # visibility semantics default missing piece vars to visible.
    assert panel.box_piece_visible_vars == {}
    visible, piece_keys = panel.resolve_visibility((_part("box_body", pieces),))
    assert visible == ("box_body",)
    assert piece_keys == ("box_body:left_side", "box_body:back")


class _TreeClick:
    def __init__(self, iid):
        self.iid = iid

    def identify_column(self, _x):
        return "#1"

    def identify_row(self, _y):
        return self.iid


def test_t4_structure_tree_empty_piece_registry_displays_visible_and_click_is_noop(
    tk_root, monkeypatch
):
    calls = []
    panel = _panel(tk_root, calls)
    _require_t4_methods(panel)

    fake = SimpleNamespace(
        _phase6_assembly_panel_owner=panel,
        structure_tree=_TreeClick("part:box_body:left_side"),
        _phase6_3d_display_mode="assembly",
        do_update=lambda: calls.append("direct-update"),
    )
    assert bridge._phase6_structure_tree_visibility_var(
        fake, "box_body:left_side"
    ) is None

    refresh_source = _function_source(
        "fold_designer_bridge.py", "_phase6_refresh_structure_tree"
    )
    assert "visible = True if visible_var is None" in refresh_source
    assert '"顯示" if visible else "隱藏"' in refresh_source

    monkeypatch.setattr(bridge, "_phase6_refresh_structure_tree", lambda _self: ())
    event = SimpleNamespace(x=1, y=1)
    assert bridge._phase6_on_structure_tree_click(fake, event) == "break"
    assert calls == []


def test_t4_structure_tree_repopulated_piece_toggle_uses_exact_panel_var_and_action(
    tk_root, monkeypatch
):
    calls = []
    panel = _panel(tk_root, calls)
    _require_t4_methods(panel)
    _refresh_pieces(panel, (_piece("left_side"), _piece("back")))

    shared = panel.box_piece_visible_vars["box_body:left_side"]
    assert bool(shared.get()) is True

    refreshes = []
    fake = SimpleNamespace(
        _phase6_assembly_panel_owner=panel,
        structure_tree=_TreeClick("part:box_body:left_side"),
        _phase6_3d_display_mode="assembly",
        do_update=lambda: calls.append("direct-update"),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_structure_tree",
        lambda _self: refreshes.append("tree"),
    )

    assert bridge._phase6_structure_tree_visibility_var(
        fake, "box_body:left_side"
    ) is shared
    assert bridge._phase6_on_structure_tree_click(
        fake, SimpleNamespace(x=1, y=1)
    ) == "break"

    assert bool(shared.get()) is False
    assert calls == ["changed"]
    assert refreshes == ["tree"]


def test_t4_panel_visibility_action_has_no_display_mode_read(tk_root):
    calls = []
    panel = _panel(tk_root, calls)
    _require_t4_methods(panel)

    panel.notify_visibility_changed()
    assert calls == ["changed"]

    panel_source = inspect.getsource(__import__("phase6_assembly_panel"))
    assert "_phase6_3d_display_mode" not in panel_source
    assert "display_mode" not in panel_source

    target = _function_source(
        "fold_designer_bridge.py",
        "_phase6_on_assembly_part_visibility_changed",
    )
    assert "_phase6_3d_display_mode" in target
    assert '== "assembly"' in target
    assert "self.do_update()" in target


def test_t4_final_scene_query_order_and_text_producer_kinds_remain_exact():
    source = inspect.getsource(
        Phase6FinalSceneViewAdapter.query_assembly_render_data
    )

    resolve_i = source.index("dependencies.resolve_geometry()")
    publish_i = source.index("dependencies.publish_live_state(force=True)")
    parts_i = source.index("parts = tuple(")
    corner_i = source.index("dependencies.assembly_corner_text_sink(corner_texts)")
    formed_i = source.index("dependencies.assembly_part_text_sink(")
    blank_i = source.index(
        "dependencies.assembly_part_text_sink(", formed_i + 1
    )
    piece_i = source.index("refresh_box_body(part.render_data)")
    visibility_i = source.index("dependencies.assembly_visibility(parts)")
    build_i = source.index("return self.make_assembly_scene_render_data(")

    assert (
        resolve_i
        < publish_i
        < parts_i
        < corner_i
        < formed_i
        < blank_i
        < piece_i
        < visibility_i
        < build_i
    )
    assert re.findall(
        r'assembly_part_text_sink\(\s*"([^"]+)"',
        source,
    ) == ["formed", "blank"]



def test_t4_bridge_final_scene_wrappers_are_thin_panel_delegates():
    corner = _function_source("phase6_assembly_panel.py", "set_corner_texts")
    part = _function_source("phase6_assembly_panel.py", "set_part_text")
    visibility = _function_source("phase6_assembly_panel.py", "resolve_visibility")
    tree_var = _function_source(
        "fold_designer_bridge.py",
        "_phase6_structure_tree_visibility_var",
    )
    tree_set = _function_source(
        "fold_designer_bridge.py",
        "_phase6_set_structure_tree_visibility",
    )

    assert "corner_vars" in corner
    assert "formed_vars" in part and "blank_vars" in part
    assert "_resolve_visibility_with_vars" in visibility
    assert ".visibility_var(" in tree_var
    assert ".notify_visibility_changed(" in tree_set

    bridge = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    for retired in (
        "_phase6_final_scene_corner_text_sink",
        "_phase6_final_scene_part_text_sink",
        "_phase6_final_scene_visibility",
    ):
        assert f"def {retired}(" not in bridge

def test_t4_final_scene_adapter_keeps_all_four_presentation_ports_wired():
    # Phase 4 T1 (#479) moved application wiring ownership into the existing
    # Phase6FoldDesignerComposition root. The presentation-port contract still
    # exists; only the source owner changed from bridge inline construction.
    source = Path(
        "gui_modules/application/fold_designer_adapter.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "final_scene_ports"
    )
    method_source = ast.get_source_segment(source, method) or ""
    assert "assembly_corner_text_sink=" in method_source
    assert "assembly_part_text_sink=" in method_source
    assert "refresh_box_body_piece_info=" in method_source
    assert "assembly_visibility=" in method_source
