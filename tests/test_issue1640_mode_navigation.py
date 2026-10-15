"""#1640: parent/child switching and Set/Bay↔Quantity must not trap Tk grabs."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_mode_toggle_and_manager_stay_operable_without_forced_window_exit():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    mode = {"current": "quantity"}  # old projects can still restore here
    switched = []
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": mode["current"]},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda target: (
                switched.append(target) or mode.__setitem__("current", target) or True
            ),
            resize_connections=lambda *_args: False,
            get_candidate_ports=lambda: {
                "versions": lambda _role: (),
                "edit": lambda *_args: None,
            },
        )
        root.update()
        assert win.title() == "多連設定"
        assert win.grab_current() is win
        assert switched == ["set_bay"]  # remove obsolete main Quantity path
        assert mode["current"] == "set_bay"
        assert win._receiving_multi_applied["mode"] == "set_bay"
        assert not [
            item for item in win._receiving_multi_mode_controls.winfo_children()
            if isinstance(item, ttk.Radiobutton)
        ]
        assert win._receiving_multi_left_scroll.winfo_exists()
        assert win._receiving_multi_function_scroll.winfo_exists()
        assert win.grab_current() is win
        win._receiving_multi_close()
        root.update()
        assert root.grab_current() is None

        single = open_multi_settings(
            root, dialog_kind="single",
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
        )
        root.update()
        assert single.title() == "單只設定"
        assert single._receiving_multi_applied["mode"] == "quantity"
        assert not any(button.winfo_ismapped() for button in single._receiving_multi_set_buttons)
        single._receiving_multi_close()
    finally:
        root.destroy()
