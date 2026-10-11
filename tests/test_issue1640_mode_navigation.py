"""#1640: parent/child switching and Set/Bay↔Quantity must not trap Tk grabs."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_mode_toggle_and_manager_stay_operable_without_forced_window_exit():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    mode = {"current": "set_bay"}
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
        assert win.grab_current() is win
        buttons = {
            b.cget("text"): b for b in
            win._receiving_multi_mode_controls.winfo_children()
            if isinstance(b, ttk.Radiobutton)
        }
        assert set(buttons) == {"套／連", "數量"}
        buttons["數量"].invoke()
        root.update()
        assert mode["current"] == "quantity"
        assert win._receiving_multi_applied["mode"] == "quantity"
        buttons["數量"].invoke()
        root.update()
        assert switched == ["quantity"]  # no redundant repeated change
        buttons["套／連"].invoke()
        root.update()
        assert mode["current"] == "set_bay"
        assert switched == ["quantity", "set_bay"]
        assert win.winfo_exists()
        assert win._receiving_multi_left_scroll.winfo_exists()
        assert win._receiving_multi_function_scroll.winfo_exists()
        assert win.grab_current() is win  # Mode switches cannot unlock the parent.
        win._receiving_multi_close()
        root.update()
        assert root.grab_current() is None
    finally:
        root.destroy()
