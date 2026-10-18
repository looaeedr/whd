"""#1901: both Receiving settings entries must use the original hole editor."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def _inner_buttons(host):
    pending = [host]
    result = []
    while pending:
        item = pending.pop()
        if isinstance(item, ttk.Button) and item.cget("text") == "編輯":
            result.append(item)
        pending.extend(item.winfo_children())
    return result


def test_single_inner_edit_button_calls_existing_physical_editor_port():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    calls = []
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "quantity"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            dialog_kind="single",
            get_single_size_quantity=lambda: {
                "width": 800, "height": 1600, "depth": 350,
                "count": 1, "total_count": 1, "version_count": 1,
            },
            edit_single_inner_door=lambda: calls.append("original-editor"),
        )
        root.update()
        selected = win._receiving_multi_setting_list
        selected.selection_set(1)
        selected.event_generate("<<ListboxSelect>>")
        root.update()
        buttons = _inner_buttons(win._receiving_multi_settings_host)
        assert len(buttons) == 1
        buttons[0].invoke()
        assert calls == ["original-editor"]
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_multi_inner_edit_passes_candidate_identity_without_applying():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    calls = []
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=lambda _set: {
                "row": lambda: {"bays": [{"stable_id": "bay1"}]},
                "select": lambda _bay: None,
            },
            get_inner_candidate_ports=lambda: {
                "versions": lambda _role: [{"id": "inner-door-v1"}],
                "edit": lambda *_args: (_ for _ in ()).throw(
                    AssertionError("must reuse original Hole Editor port")
                ),
                "apply": lambda *_args: calls.append(("apply",)),
            },
            edit_multi_inner_door=lambda version, _saved: calls.append(("edit", version)),
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        selector = win._receiving_multi_candidate_combos["inner-door"]
        selector.set("版本一")
        selector.event_generate("<<ComboboxSelected>>")
        root.update()
        buttons = _inner_buttons(win._receiving_multi_settings_host)
        assert len(buttons) == 1
        buttons[0].invoke()
        assert calls == [("edit", "inner-door-v1")]
        win._receiving_multi_close()
    finally:
        root.destroy()
