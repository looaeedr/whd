"""GUI contract: only explicitly requested multi-settings elements are visible."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

from ae_engine.receiving_quantity_box import normalize_common_box, project_common_box
from gui_modules.application.receiving_multi_settings_window import (
    default_preview_dimensions, display_dimension, open_multi_settings,
    paint_connected_bays, extract_original_door_marks,
)
from phase6_assembly_panel import Phase6AssemblyPanel, AssemblyPanelActions


def test_family_dimensions_without_initialization_dialog():
    box = normalize_common_box(None)
    assert (box["w"], box["h"], box["d"]) == (800, 1600, 350)
    sample = project_common_box({"active_mode": "quantity"})
    assert (sample["w"], sample["h"]) == (800, 1600)
    with pytest.raises(ValueError):
        normalize_common_box("not-a-box")
    assert default_preview_dimensions({"active_mode": "quantity"}) == (800, 1600, 350)
    assert display_dimension(800.0) == "800"
    assert display_dimension(800.5) == "800.5"


def test_sketch_uses_only_identified_original_door_marks():
    from ae_engine.sheetmetal_drawing import DrawingScene

    drawing = DrawingScene()
    assert extract_original_door_marks(None) == {"nameplate": (), "handle": ()}
    drawing.add_polyline(((0, 0), (100, 0), (100, 200), (0, 200)),
                         layer="CUTTING", closed=True)
    drawing.add_polyline(((10, 70), (14, 70), (14, 110), (10, 110)),
                         layer="CUTTING", closed=True)
    drawing.add_circle((50, 175), 1.6, layer="CUTTING",
                       source_type="nameplate_mount",
                       source_id="door:nameplate_mount:1")
    drawing.add_circle((91, 40), 4, layer="CUTTING")
    marks = extract_original_door_marks(drawing)
    assert len(marks["handle"]) == 4
    assert marks["handle"][0] == (0.1, 0.65)
    assert marks["nameplate"] == ((0.5, 0.125, 0.016, 0.008),)
    drawing.add_polyline(((20, 40), (25, 40), (25, 60), (20, 60)),
                         layer="CUTTING", closed=True)
    assert extract_original_door_marks(drawing)["handle"] == ()


def test_modal_connection_resize_skips_hidden_global_panel_until_exit():
    from gui_modules.application.fold_designer_composition_receiving import resize_receiving_bays

    class FakeSwitch:
        def resize_connections(self, index, delta):
            calls.append(("resize", index, delta))
            return True

    class FakeComposition:
        def receiving_switch_adapter(self, namespace):
            assert namespace == "receiving"
            return switch

        def mark_receiving_switch_layout_dirty(self, namespace, adapter):
            assert namespace == "receiving" and adapter is switch
            calls.append(("dirty",))

        def refresh_receiving_set_bay_control(self, namespace):
            assert namespace == "receiving"
            calls.append(("hidden-refresh",))

    calls = []
    switch = FakeSwitch()
    composition = FakeComposition()
    assert resize_receiving_bays(composition, "receiving", 0, 1,
                                refresh_controls=False)
    assert calls == [("resize", 0, 1), ("dirty",)]
    calls.clear()
    # Other callers still refresh the original panel by default.
    assert resize_receiving_bays(composition, "receiving", 0, 1)
    assert calls == [("resize", 0, 1), ("dirty",), ("hidden-refresh",)]


def test_modal_resize_public_composition_forwards_refresh_controls():
    """GUI calls the public composition method, not the helper directly."""
    from gui_modules.application.fold_designer_adapter import Phase6FoldDesignerComposition

    calls = []

    class FakeSwitch:
        def resize_connections(self, index, delta):
            calls.append(("resize", index, delta))
            return True

    class FakeComposition:
        def receiving_switch_adapter(self, namespace):
            assert namespace == "receiving"
            return switch

        def mark_receiving_switch_layout_dirty(self, namespace, adapter):
            assert namespace == "receiving" and adapter is switch
            calls.append(("dirty",))

        def refresh_receiving_set_bay_control(self, namespace):
            assert namespace == "receiving"
            calls.append(("hidden-refresh",))

    switch = FakeSwitch()
    composition = FakeComposition()
    # Both buttons pass refresh_controls=False through the public facade.
    for delta in (1, -1):
        assert Phase6FoldDesignerComposition.resize_receiving_bays(
            composition, "receiving", 0, delta, refresh_controls=False
        )
    assert calls == [
        ("resize", 0, 1), ("dirty",),
        ("resize", 0, -1), ("dirty",),
    ]
    calls.clear()
    # Existing callers still refresh the hidden controls by default.
    assert Phase6FoldDesignerComposition.resize_receiving_bays(
        composition, "receiving", 0, 1
    )
    assert calls == [
        ("resize", 0, 1), ("dirty",), ("hidden-refresh",)
    ]


def test_assembly_button_is_hidden_until_receiving_assembly():
    root = tk.Tk()
    root.withdraw()
    calls = []
    try:
        owner = Phase6AssemblyPanel(
            root, actions=AssemblyPanelActions(
                on_visibility_changed=lambda: None,
                on_multi_settings=lambda: calls.append(1),
            ),
        )
        owner.host.pack()
        assert not owner.multi_settings_entry.winfo_manager()
        owner.set_multi_settings_visible(True)
        root.update_idletasks()
        assert owner.multi_settings_entry.winfo_manager()
        owner.multi_settings_button.invoke()
        assert calls == [1]
        owner.set_multi_settings_visible(False)
        assert not owner.multi_settings_entry.winfo_manager()
    finally:
        root.destroy()


def _visible_texts(widget):
    result = []
    for child in widget.winfo_children():
        try:
            # Tk accepts abbreviated option names: Combobox cget("text")
            # can resolve to its textvariable (PY_VAR...), not visible text.
            if child.winfo_ismapped() and "text" in child.keys():
                text = child.cget("text")
                if text:
                    result.append(str(text))
        except tk.TclError:
            pass
        result.extend(_visible_texts(child))
    return tuple(result)


def first_row_width_fits(win):
    win.update_idletasks()
    row = win._receiving_multi_rows_host.winfo_children()[0]
    viewport = win._receiving_multi_left_scroll._receiving_scroll_viewport
    return row.winfo_reqwidth() <= viewport.winfo_width()


def test_modal_fullscreen_strict_controls_apply_and_highlight():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    counts = [1]
    mode = {"value": "set_bay"}
    selected = []
    selected_settings = []
    resized = []
    brand_calls = []
    deferred_refresh = []
    brand_commit = []

    def resize(index, delta):
        resized.append((index, delta))
        counts[index] = max(1, counts[index] + delta)
        return True

    def switch(target):
        mode["value"] = target
        return True

    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: SimpleNamespace(
                connection_counts=lambda: tuple(counts)),
            switch_mode=switch, resize_connections=resize,
            select_bay=lambda set_index, bay_index: selected.append(
                (set_index, bay_index)),
            on_setting_selected=lambda set_index, bay_index, kind:
                selected_settings.append((set_index, bay_index, kind)),
            get_brand=lambda: "士林",
            set_brand=lambda brand: brand_calls.append(brand) or True,
            on_close=lambda: deferred_refresh.append(tuple(counts)),
            on_brand_close=lambda: brand_commit.append(brand_calls[-1]),
        )
        root.update()
        brand_picker = win._receiving_multi_brand_selector
        assert tuple(brand_picker.cget("values")) == (
            "士林", "東元", "三菱", "伍菱", "順山"
        )
        assert win._receiving_multi_brand_var.get() == "士林"
        win._receiving_multi_brand_var.set("東元")
        brand_picker.event_generate("<<ComboboxSelected>>")
        root.update()
        assert brand_calls == ["東元"]
        assert brand_commit == []  # no synchronous 3D/geometry redraw
        assert brand_picker.master.master is win._receiving_multi_mode_controls.master
        assert win.title() == "多只設定"
        assert win.grab_current() is win
        assert win.winfo_width() >= win.winfo_screenwidth() - 2
        assert win.winfo_height() >= win.winfo_screenheight() - 2
        assert win._receiving_multi_mode_var.get() == "set_bay"
        texts = _visible_texts(win)
        assert set(texts) == {"NFB", "套／連", "數量", "－套", "＋套", "第1套", "－連", "1", "＋連", "套用"}
        assert not hasattr(win, "_receiving_multi_preview")
        assert not hasattr(win, "_receiving_multi_notebook")
        canvas = win._receiving_multi_canvas
        rows_host = win._receiving_multi_rows_host
        mode_row = win._receiving_multi_mode_controls
        setting_list = win._receiving_multi_setting_list
        controls_column = rows_host.master
        # Two columns: Set/Bay stays LEFT; category/function selection is
        # RIGHT TOP, and a separate diagram container occupies RIGHT BOTTOM.
        left = win._receiving_multi_left_host
        right = win._receiving_multi_right_host
        function = win._receiving_multi_function_host
        diagram = win._receiving_multi_diagram_host
        assert left.master is win._receiving_multi_left_scroll._receiving_scroll_content
        assert right.master is win
        assert win._receiving_multi_left_scroll.grid_info()["column"] == 0
        assert right.grid_info()["column"] == 1
        assert mode_row.master.master is left
        assert controls_column.master is left
        assert function.master is win._receiving_multi_function_scroll._receiving_scroll_content
        assert win._receiving_multi_function_scroll.grid_info()["row"] == 0
        assert diagram.master is right and diagram.grid_info()["row"] == 1
        assert canvas.master is diagram and canvas.grid_info()["row"] == 0
        assert win._receiving_multi_settings_host.master is function
        assert abs(controls_column.winfo_rootx() - mode_row.winfo_rootx()) <= 2
        set_buttons = win._receiving_multi_set_buttons
        assert [w.cget("text") for w in set_buttons] == ["－套", "＋套"]
        vertical_gap = controls_column.winfo_rooty() - (
            set_buttons[0].master.winfo_rooty() + set_buttons[0].master.winfo_height()
        )
        assert 0 <= vertical_gap <= 32
        assert isinstance(setting_list, tk.Listbox)
        assert setting_list.master is function
        assert setting_list.grid_info()["row"] == 0
        assert setting_list.grid_info()["column"] == 0
        assert win._receiving_multi_settings_host.grid_info()["column"] == 1
        assert setting_list.winfo_ismapped()
        assert tuple(setting_list.get(0, tk.END)) == ("封頭尾", "內門")
        assert setting_list.curselection() == ()
        assert len(canvas._receiving_bay_hitboxes) == 1
        assert win._receiving_multi_applied["set_index"] is None
        assert win._receiving_multi_applied["selected"] is None
        # Selecting existing settings forwards to the ORIGINAL per-bay
        # domain keys without opening another window or changing geometry.
        toplevels_before = len(root.winfo_children())
        setting_list.selection_set(0)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings == [(0, 0, "head_features")]
        setting_list.selection_clear(0, tk.END)
        setting_list.selection_set(1)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings[-1] == (0, 0, "inner_door_layers")
        assert len(root.winfo_children()) == toplevels_before
        assert len(canvas._receiving_bay_hitboxes) == 1

        def current_row():
            return rows_host.winfo_children()[0].winfo_children()

        def current_buttons():
            return [w for w in current_row() if isinstance(w, ttk.Button)]

        def displayed_count():
            labels = [w.cget("text") for w in current_row()
                      if isinstance(w, ttk.Label)]
            return labels[1]

        assert [w.cget("text") for w in current_row()] == [
            "第1套", "－連", "1", "＋連", "套用"]
        assert all(int(w.cget("width")) <= 4 for w in current_buttons())
        assert first_row_width_fits(win)

        minus, plus, apply = current_buttons()
        first_row = rows_host.winfo_children()[0]
        first_count = current_row()[2]
        plus.invoke()
        # First click must not destroy the invoking Tk button or recreate
        # its row, which previously caused a stalled callback/blank view.
        assert rows_host.winfo_children()[0] is first_row
        assert current_buttons() == [minus, plus, apply]
        assert current_row()[2] is first_count
        assert plus.winfo_exists()
        assert displayed_count() == "2"
        assert deferred_refresh == []  # no expensive hidden control rebuild
        plus.invoke()
        assert rows_host.winfo_children()[0] is first_row
        assert displayed_count() == "3"
        assert counts == [3]
        assert len(canvas._receiving_bay_hitboxes) == 1  # apply controls the sketch
        assert win._receiving_multi_apply(0) is True
        assert len(canvas._receiving_bay_hitboxes) == 3
        assert selected == [(0, 0)]
        assert win._receiving_multi_applied["selected"] == 0
        assert setting_list.curselection() == ()
        hits = canvas._receiving_bay_hitboxes
        assert hits[0][2] == hits[1][0] == hits[0][2]
        assert hits[1][2] == hits[2][0]

        x0, y0, x1, y1 = hits[2]
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert selected[-1] == (0, 2)
        assert win._receiving_multi_applied["selected"] == 2
        assert canvas._receiving_selected_bay == 2
        assert canvas._receiving_selected_bays == frozenset({0, 2})
        setting_list.selection_set(0)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings[-1] == (0, 2, "head_features")
        x0, y0, x1, y1 = hits[1]
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert selected_settings[-1] == (0, 1, "head_features")
        assert canvas._receiving_selected_bays == frozenset({0, 1, 2})
        assert canvas._receiving_selected_bay == 1
        # Repeated click toggles this highlight; the active editor moves to
        # a retained selected Bay rather than clearing selection.
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert canvas._receiving_selected_bays == frozenset({0, 2})
        assert win._receiving_multi_applied["selected"] == 0

        minus, plus, apply = current_buttons()
        minus.invoke()
        assert counts == [2]
        assert displayed_count() == "2"
        assert len(canvas._receiving_bay_hitboxes) == 3
        apply.invoke()
        assert len(canvas._receiving_bay_hitboxes) == 2
        assert win._receiving_multi_applied["selected"] == 0
        assert canvas._receiving_selected_bays == frozenset({0})

        # Two choices are mutually exclusive; no quantity-version table or
        # common-box affordance is exposed until explicitly requested.
        choices = [w for w in win._receiving_multi_mode_controls.winfo_children()
                   if isinstance(w, ttk.Radiobutton)]
        assert len(choices) == 2
        choices[1].invoke()
        root.update()
        assert mode["value"] == "quantity"
        assert not win._receiving_multi_rows_host.winfo_children()
        assert setting_list.winfo_ismapped()
        assert tuple(setting_list.get(0, tk.END)) == ("封頭尾",)
        assert len(canvas._receiving_bay_hitboxes) == 1
        assert set(_visible_texts(win)) == {"NFB", "套／連", "數量"}
        choices[0].invoke()
        root.update()
        assert mode["value"] == "set_bay"
        assert "第1套" in _visible_texts(win)
        assert setting_list.winfo_ismapped()
        assert tuple(setting_list.get(0, tk.END)) == ("封頭尾", "內門")
        assert open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: None, switch_mode=switch,
            resize_connections=resize,
        ) is win
        win._receiving_multi_close()
        root.update()
        assert root.grab_current() is None
        assert deferred_refresh == [(2,)]
        assert brand_commit == ["東元"]
    finally:
        root.destroy()


def test_multi_settings_does_not_expose_postponed_version_ui():
    from phase6_quantity_model import QuantityModel

    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    mode = {"value": "set_bay"}
    model = QuantityModel()
    original = model.snapshot()
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda target: mode.__setitem__("value", target) or True,
            resize_connections=lambda *_args: True,
            get_settings_ports=lambda _set: {
                "select": lambda _bay: None,
                "holes": lambda _role, _bays: None,
            },
        )
        root.update()
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        panel = win._receiving_multi_settings_host
        assert not any("版本" in label for label in _visible_texts(panel))
        assert not any(isinstance(child, ttk.Treeview)
                       for child in panel.winfo_children())
        # Switching to 數量 must not silently add an unfinished version UI.
        choices = [w for w in win._receiving_multi_mode_controls.winfo_children()
                   if isinstance(w, ttk.Radiobutton)]
        choices[1].invoke()
        root.update()
        assert mode["value"] == "quantity"
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        assert not panel.winfo_children()
        assert model.snapshot() == original
        choices[0].invoke()
        root.update()
        assert mode["value"] == "set_bay"
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_compact_candidates_and_set_controls_use_original_combobox():
    from ae_engine.receiving_hole_candidates import (
        create_candidate, duplicate_candidate, delete_candidate,
        candidates_for,
    )

    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    counts = [2]
    library = {"value": None}
    calls = []

    def candidate_ports():
        def editor(role, version_id, on_saved):
            calls.append(("edit", role, version_id))
            if version_id is None:
                library["value"], created = create_candidate(
                    library["value"], role, [{"unit": role}]
                )
                on_saved(created)
            else:
                on_saved(version_id)

        def copier(role, version_id, destination):
            library["value"], created = duplicate_candidate(
                library["value"], role, version_id, destination
            )
            return created

        def delete(role, version_id):
            library["value"] = delete_candidate(library["value"], role, version_id)

        return {
            "versions": lambda role: candidates_for(library["value"], role),
            "edit": editor,
            "copy": copier,
            "delete": delete,
            "apply": lambda role, version_id, set_index, targets:
                calls.append(("apply", role, version_id, set_index, targets)),
        }

    def resize_sets(delta):
        if delta == 1:
            counts.append(1)
        elif len(counts) > 1:
            counts.pop()
        else:
            return False
        return True

    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: tuple(counts)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            resize_sets=resize_sets, get_candidate_ports=candidate_ports,
            get_settings_ports=lambda _set: {"select": lambda _bay: None},
        )
        root.update()
        minus_set, plus_set = win._receiving_multi_set_buttons
        assert (minus_set.cget("text"), plus_set.cget("text")) == ("－套", "＋套")
        plus_set.invoke()
        root.update()
        assert counts == [2, 1]
        rows = win._receiving_multi_rows_host.winfo_children()
        assert len(rows) == 2
        assert [w.cget("text") for w in rows[0].winfo_children()] == [
            "第1套", "－連", "2", "＋連", "套用"
        ]
        minus_set.invoke()
        root.update()
        assert counts == [2]
        assert len(win._receiving_multi_rows_host.winfo_children()) == 1

        win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        host = win._receiving_multi_settings_host
        assert "版本管理" in _visible_texts(host)
        assert len([t for t in _visible_texts(host) if t == "編輯"]) == 2
        assert "複製為新版本" not in _visible_texts(host)
        combo = win._receiving_multi_candidate_combos["head"]
        assert isinstance(combo, ttk.Combobox)
        assert str(combo.cget("state")) == "readonly"
        assert tuple(combo.cget("values")) == ("即時",)
        head_row = host.winfo_children()[0]
        head_edit = [w for w in head_row.winfo_children()
                     if isinstance(w, ttk.Button) and w.cget("text") == "編輯"][0]
        head_edit.invoke()
        root.update()
        assert calls[0] == ("edit", "head", None)
        combo = win._receiving_multi_candidate_combos["head"]
        assert tuple(combo.cget("values")) == ("即時", "版本一")
        assert combo.get() == "即時"  # A live save must not lock subsequent edits to v1.
        # Apply still requires an explicit version selection; highlight ownership
        # must not be inferred from the live draft.
        combo.set("版本一")
        combo.event_generate("<<ComboboxSelected>>")
        root.update()
        head_row = host.winfo_children()[0]
        apply = [w for w in head_row.winfo_children()
                 if isinstance(w, ttk.Button) and w.cget("text") == "套用"][0]
        apply.invoke()
        assert ("apply", "head", "head-v1", 0, (0,)) in calls

        manager = [w for w in host.winfo_children()
                   if isinstance(w, ttk.Button) and w.cget("text") == "版本管理"][0]
        manager.invoke()
        root.update()
        child = win._receiving_multi_manager_window["win"]
        assert child is not None and child.winfo_exists()
        assert child.master is win
        assert child.title() == "版本管理"
        assert child.grab_current() is child  # Child owns the grab; main stays blocked.
        assert win._receiving_multi_canvas.master is win._receiving_multi_diagram_host
        assert "複製為新版本" not in _visible_texts(host)
        assert "複製為新版本" in _visible_texts(child)
        assert "複製到封尾" in _visible_texts(child)
        assert "刪除目前版本" in _visible_texts(child)
        manage_buttons = child._receiving_manager_buttons
        duplicate = [w for w in manage_buttons
                     if w.cget("text") == "複製為新版本"][0]
        duplicate.invoke()
        root.update()
        assert len(candidates_for(library["value"], "head")) == 2
        combo = win._receiving_multi_candidate_combos["head"]
        assert combo.get() == "版本二"
        manage_buttons = child._receiving_manager_buttons
        to_other = [w for w in manage_buttons
                    if w.cget("text") == "複製到封尾"][0]
        to_other.invoke()
        root.update()
        assert len(candidates_for(library["value"], "tail")) == 1
        assert win._receiving_multi_candidate_combos["tail"].get() == "版本一"
        assert len(candidates_for(library["value"], "head")) == 2
        # Re-clicking the entry raises the SAME manager, not a duplicate.
        new_host = win._receiving_multi_settings_host
        reopen = [w for w in new_host.winfo_children()
                  if isinstance(w, ttk.Button) and w.cget("text") == "版本管理"][0]
        reopen.invoke()
        root.update()
        assert win._receiving_multi_manager_window["win"] is child
        assert len([w for w in win.winfo_children() if isinstance(w, tk.Toplevel)]) == 1
        win._receiving_multi_close_manager()
        root.update()
        assert not child.winfo_exists()
        assert win.grab_current() is win
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_sketch_multi_highlights_drive_existing_endcap_edits_without_link_buttons():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    calls = []
    bay_ids = ("a", "b", "c")
    row = {"bays": [{"stable_id": sid} for sid in bay_ids]}
    def ports(_set_index):
        return {
            "row": lambda: row,
            "select": lambda bay: calls.append(("select", bay)),
            "holes": lambda role, targets: calls.append(("edit", role, targets)),
            "share": lambda kind, targets: calls.append(("share", kind, targets)),
            "unlink": lambda kind: calls.append(("unlink", kind)),
        }
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (3,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: True,
            get_settings_ports=ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        canvas = win._receiving_multi_canvas
        hits = canvas._receiving_bay_hitboxes
        for bay in (1, 2):
            x0, y0, x1, y1 = hits[bay]
            canvas.event_generate("<Button-1>", x=int((x0 + x1)/2),
                                  y=int((y0 + y1)/2))
            root.update()
        assert canvas._receiving_selected_bays == frozenset({0, 1, 2})
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        panel = win._receiving_multi_settings_host
        labels = _visible_texts(panel)
        assert "連動目標" not in labels
        assert "編輯／套用" not in labels
        assert "連動選取的連" not in labels
        assert "解除本連連動" not in labels
        assert labels.count("編輯") == 2
        assert all(not isinstance(widget, ttk.Checkbutton)
                   for frame in panel.winfo_children()
                   for widget in frame.winfo_children())
        first = panel.winfo_children()[0]
        edits = [child for child in first.winfo_children()
                 if isinstance(child, ttk.Button) and child.cget("text") == "編輯"]
        assert len(edits) == 1
        edits[0].invoke()
        assert ("edit", "head", (0, 1, 2)) in calls
        assert not any(item[0] in {"share", "unlink"} for item in calls)
        win._receiving_multi_close()
    finally:
        root.destroy()



def test_last_highlight_can_be_cleared_without_implicit_reselection():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        canvas = win._receiving_multi_canvas
        assert canvas._receiving_selected_bays == frozenset({0})
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[0]
        canvas.event_generate("<Button-1>", x=int((x0+x1)/2),
                              y=int((y0+y1)/2))
        root.update()
        assert canvas._receiving_selected_bays == frozenset()
        assert win._receiving_multi_applied["selected_bays"] == ()
        assert win._receiving_multi_applied["selected"] is None
        assert win.grab_current() is win
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_inner_door_version_applies_to_both_highlighted_bays():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    recorded = []
    row = {"bays": [{"stable_id": "a"}, {"stable_id": "b"}]}
    library = {
        "versions": lambda role: [{"id": "inner-door-v1"}],
        "edit": lambda *_args: None,
        "apply": lambda role, version_id, set_index, targets:
            recorded.append((role, version_id, set_index, targets)),
    }
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=lambda _si: {
                "row": lambda: row, "select": lambda _bay: None,
            },
            get_inner_candidate_ports=lambda: library,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        canvas = win._receiving_multi_canvas
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[1]
        canvas.event_generate("<Button-1>", x=int((x0+x1)/2),
                              y=int((y0+y1)/2))
        root.update()
        assert canvas._receiving_selected_bays == frozenset({0, 1})

        listing = win._receiving_multi_setting_list
        listing.selection_set(1)  # 內門
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        chooser = win._receiving_multi_candidate_combos["inner-door"]
        chooser.set("版本一")
        chooser.event_generate("<<ComboboxSelected>>")
        root.update()
        host = win._receiving_multi_settings_host
        buttons = [widget for frame in host.winfo_children()
                   for widget in frame.winfo_children()
                   if isinstance(widget, ttk.Button)
                   and widget.cget("text") == "套用"]
        assert len(buttons) == 1
        buttons[0].invoke()
        assert recorded == [("inner-door", "inner-door-v1", 0, (0, 1))]
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_two_doors_in_every_touching_bay_and_one_selection():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=500, height=300)
        assert paint_connected_bays(canvas, 4, selected=2) == 4
        assert len(canvas._receiving_bay_hitboxes) == 4
        assert canvas._receiving_selected_bay == 2
        bounds = canvas._receiving_bay_hitboxes
        assert all(bounds[i][2] == bounds[i+1][0] for i in range(3))
        # 4 pieces per bay: body, upper door, lower door, door divider.
        assert len(canvas.find_all()) == 16
        body = canvas.find_all()[8]
        assert canvas.itemcget(body, "outline") == "#42bdf4"
    finally:
        root.destroy()
