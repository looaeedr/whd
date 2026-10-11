"""#1640: 2D highlight authority supports zero Bays without a hidden apply target."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_hole_candidates import create_candidate, candidates_for
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_last_highlight_can_be_cleared_and_candidate_apply_is_noop():
    root = tk.Tk()
    root.withdraw()
    library, version = create_candidate(None, "head", [{"tag": "sample"}])
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    actions = []

    def source():
        return {
            "versions": lambda role: candidates_for(library, role),
            "apply": lambda role, version_id, set_index, bays:
                actions.append((role, version_id, set_index, tuple(bays))),
            "edit": lambda *_args: None,
        }

    def settings_ports(_set_index):
        return {
            "row": lambda: layout["sets"][0],
            "select": lambda _bay_index: None,
            "change": lambda *_args: None,
        }

    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_candidate_ports=source,
            get_settings_ports=settings_ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        canvas = win._receiving_multi_canvas
        assert win._receiving_multi_applied["selected_bays"] == (0,)

        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[0]
        cx, cy = int((x0+x1)/2), int((y0+y1)/2)
        canvas.event_generate("<Button-1>", x=cx, y=cy)
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == ()
        assert canvas._receiving_selected_bays == frozenset()

        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        choose = win._receiving_multi_candidate_combos["head"]
        choose.set("版本一")
        choose.event_generate("<<ComboboxSelected>>")
        root.update()
        row = win._receiving_multi_settings_host.winfo_children()[0]
        button = next(c for c in row.winfo_children()
                      if isinstance(c, ttk.Button) and c.cget("text") == "套用")
        button.invoke()
        assert actions == []  # No implicit Bay0 on an empty highlight.
        assert win._receiving_multi_applied["selected_bays"] == ()

        canvas.event_generate("<Button-1>", x=cx, y=cy)
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0,)
        row = win._receiving_multi_settings_host.winfo_children()[0]
        button = next(c for c in row.winfo_children()
                      if isinstance(c, ttk.Button) and c.cget("text") == "套用")
        button.invoke()
        assert actions == [("head", version, 0, (0,))]
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_empty_highlights_cannot_fall_back_to_current_bay_in_legacy_ports():
    from gui_modules.application import fold_designer_composition_receiving as comp
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
    from ae_engine.receiving_shared_settings import setting_value

    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    host = SimpleNamespace(receiving_adapter=lambda _namespace: adapter)
    ports = comp.receiving_settings_ports(host, "test", 0)
    initial_layout = adapter.layout
    assert ports["change"]("inner_door_layers", 2, ()) is False
    assert ports["holes"]("head", ()) is False
    assert adapter.layout == initial_layout
    assert setting_value(adapter.layout["sets"][0], 0, "inner_door_layers") == 1
