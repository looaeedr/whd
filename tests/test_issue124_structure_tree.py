from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


def _rows(parts):
    fn = getattr(bridge, "_phase6_structure_tree_rows", None)
    assert callable(fn), "#124 requires one authoritative Structure Tree projection"
    return fn(parts)


class _FakeStructureTree:
    def __init__(self):
        self.nodes = {}
        self.children = {"": []}
        self.selected = ()
        self.idle_callbacks = []

    def get_children(self, parent=""):
        return tuple(self.children.get(parent, ()))

    def delete(self, *iids):
        for iid in iids:
            self.nodes.pop(iid, None)
        self.children = {"": []}
        self.selected = ()

    def insert(self, parent, _index, *, iid, text, values, open=False, tags=()):
        self.nodes[iid] = {
            "parent": parent,
            "text": text,
            "values": values,
            "open": open,
            "tags": tags,
        }
        self.children.setdefault(parent, []).append(iid)
        self.children.setdefault(iid, [])
        return iid

    def exists(self, iid):
        return iid in self.nodes

    def selection_set(self, iid):
        self.selected = (iid,)

    def selection(self):
        return self.selected

    def focus(self, _iid):
        return None

    def see(self, _iid):
        return None

    def after_idle(self, callback):
        self.idle_callbacks.append(callback)
        return "idle#1"


def _open_receiving_designer():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    root.update_idletasks(); root.update()
    designer = app.open_original_fold_designer()
    root.update_idletasks(); root.update()
    return tk, root, app, designer


def _destroy_designer(tk, root, designer):
    try:
        designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def _structure_tree(designer):
    tree = getattr(designer, "structure_tree", None)
    assert tree is not None, "#124 requires a visible Structure Tree"
    return tree


def _pump_tk(root, cycles=3):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def test_receiving_box_body_projects_one_parent_with_authoritative_children():
    rows = _rows((
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "head",
        "tail",
    ))

    assert rows == (
        ("box_body", None),
        ("box_body:left_side", "box_body"),
        ("box_body:back", "box_body"),
        ("box_body:right_side", "box_body"),
        ("head", None),
        ("tail", None),
    )


def test_single_piece_box_body_never_invents_children():
    assert _rows(("box_body", "head")) == (
        ("box_body", None),
        ("head", None),
    )


def test_orphan_physical_children_remain_exact_top_level_authority():
    assert _rows(("box_body:back", "head")) == (
        ("box_body:back", None),
        ("head", None),
    )


def test_structure_tree_refresh_guard_stays_active_until_tk_idle(monkeypatch):
    """A refresh-triggered selection event must be swallowed before the guard drops."""
    fn = getattr(bridge, "_phase6_refresh_structure_tree", None)
    assert callable(fn), "#124 requires Structure Tree refresh adapter"

    tree = _FakeStructureTree()
    workspace = SimpleNamespace(
        available_parts=("box_body", "head"),
        active_part="box_body",
    )
    designer = SimpleNamespace(
        structure_tree=tree,
        designer_workspace=workspace,
        _phase6_structure_tree_guard=False,
        _phase6_input_snapshot={},
        _phase6_3d_display_mode="single",
    )
    monkeypatch.setattr(bridge, "_designer_workspace", lambda _self: workspace)
    monkeypatch.setattr(
        bridge,
        "_phase6_part_label",
        lambda key, snapshot=None: str(key),
    )

    fn(designer)

    assert designer._phase6_structure_tree_guard is True
    assert len(tree.idle_callbacks) == 1

    tree.idle_callbacks.pop()()
    assert designer._phase6_structure_tree_guard is False


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_structure_tree_is_single_visible_navigation_and_selects_exact_physical_child():
    tk, root, _app, designer = _open_receiving_designer()
    try:
        tree = _structure_tree(designer)
        assert tree.winfo_manager() != ""
        assert tree.exists("mode:assembly")
        assert tree.exists("mode:corner_data")
        assert tree.exists("part:box_body")
        assert tree.parent("part:box_body:left_side") == "part:box_body"
        assert tree.parent("part:box_body:back") == "part:box_body"
        assert tree.parent("part:box_body:right_side") == "part:box_body"
        assert designer.part_choice_button.winfo_manager() == ""
        assert designer.box_body_piece_selector.winfo_manager() == ""

        tree.selection_set("part:box_body:back")
        tree.focus("part:box_body:back")
        tree.event_generate("<<TreeviewSelect>>")
        root.update_idletasks(); root.update()

        assert designer.designer_workspace.active_part == "box_body:back"
        assert tuple(tree.selection()) == ("part:box_body:back",)
    finally:
        _destroy_designer(tk, root, designer)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_structure_tree_visibility_delegates_existing_view_state_without_deleting_part():
    tk, root, _app, designer = _open_receiving_designer()
    try:
        tree = _structure_tree(designer)
        bridge._phase6_query_assembly_render_data(designer)
        root.update_idletasks(); root.update()

        key = "box_body:back"
        assert key in designer.designer_workspace.available_parts
        assert designer.assembly_box_body_piece_visible_vars[key].get() is True

        setter = getattr(bridge, "_phase6_set_structure_tree_visibility", None)
        assert callable(setter), "#124 Structure Tree must delegate visibility to existing view state"
        setter(designer, key, False)
        root.update_idletasks(); root.update()

        assert designer.assembly_box_body_piece_visible_vars[key].get() is False
        assert key in designer.designer_workspace.available_parts
        bundle = bridge._phase6_query_assembly_render_data(designer)
        assert key not in bundle.visible_box_body_piece_keys
        assert "box_body" in bundle.visible_part_keys
        assert tree.set("part:box_body:back", "visibility") == "隱藏"
    finally:
        _destroy_designer(tk, root, designer)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_family_switch_removes_stale_receiving_children_and_restores_current_authority():
    tk, root, app, designer = _open_receiving_designer()
    try:
        tree = _structure_tree(designer)
        receiving_children = (
            "part:box_body:left_side",
            "part:box_body:back",
            "part:box_body:right_side",
        )
        assert all(tree.exists(iid) for iid in receiving_children)

        app.baseline_var.set("金庫型")
        _pump_tk(root, 4)
        assert app.baseline_var.get() == "金庫型"
        assert not any(tree.exists(iid) for iid in receiving_children)
        assert not any(
            key in designer.designer_workspace.available_parts
            for key in ("box_body:left_side", "box_body:back", "box_body:right_side")
        )

        app.baseline_var.set("受電箱")
        _pump_tk(root, 4)
        assert app.baseline_var.get() == "受電箱"
        assert all(tree.exists(iid) for iid in receiving_children)
        assert tree.parent("part:box_body:left_side") == "part:box_body"
        assert tree.parent("part:box_body:back") == "part:box_body"
        assert tree.parent("part:box_body:right_side") == "part:box_body"
    finally:
        _destroy_designer(tk, root, designer)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_structure_tree_survives_all_text_scales_resize_and_real_scroll_commands():
    from phase6_settings_center import ui_text_size_factor

    tk, root, app, designer = _open_receiving_designer()
    try:
        tree = _structure_tree(designer)
        scrollbar = getattr(designer, "structure_tree_scrollbar", None)
        assert scrollbar is not None
        assert tree.winfo_manager() != ""
        assert scrollbar.winfo_manager() != ""
        assert str(tree.cget("yscrollcommand"))
        assert str(scrollbar.cget("command"))

        for key in ("small", "medium", "large"):
            resolved = app._apply_ui_text_size_preference(
                key, persist=False, notify_designer=True
            )
            _pump_tk(root, 2)
            assert resolved == key
            assert designer._ui_text_controller.size_key == key
            assert designer.state.ui_text_scale == pytest.approx(ui_text_size_factor(key))
            assert tree.winfo_width() > 40
            assert tree.winfo_height() > 40
            assert tree.exists("part:box_body")
            assert tree.bbox("part:box_body")

        designer.root.geometry("760x420")
        _pump_tk(root, 3)
        assert tree.winfo_width() > 40
        assert tree.winfo_height() > 40
        assert tree.winfo_ismapped()
        assert scrollbar.winfo_ismapped()

        before = tuple(float(v) for v in tree.yview())
        tree.yview_scroll(1, "units")
        _pump_tk(root, 1)
        after = tuple(float(v) for v in tree.yview())
        assert len(before) == 2 and len(after) == 2
        assert 0.0 <= after[0] <= after[1] <= 1.0
    finally:
        _destroy_designer(tk, root, designer)


def test_external_text_scale_persist_false_keeps_config_bytes_and_syncs_designer():
    from pathlib import Path

    tk, root, app, designer = _open_receiving_designer()
    config_path = Path("config.ini")
    before = config_path.read_bytes()
    try:
        resolved = app._apply_ui_text_size_preference(
            "large", persist=False, notify_designer=True
        )
        _pump_tk(root, 3)
        assert resolved == "large"
        assert designer._ui_text_controller.size_key == "large"
        assert config_path.read_bytes() == before, (
            "#124 persist=False runtime text-scale sync must not write config.ini"
        )
    finally:
        _destroy_designer(tk, root, designer)
