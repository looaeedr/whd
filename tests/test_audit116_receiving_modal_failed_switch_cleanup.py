# -*- coding: utf-8 -*-
"""#116 Windows Tk regression: rejected mode change must not trap a modal."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="native Receiving modal regression needs Windows Tk or Xvfb",
)


@pytest.mark.parametrize(
    ("source_mode", "kind", "requested_mode", "rejection"),
    (
        ("set_bay", "single", "quantity", "refused"),
        ("quantity", "multi", "set_bay", "refused"),
        ("quantity", "multi", "set_bay", "exception"),
    ),
)
def test_rejected_receiving_mode_switch_leaves_no_uninitialized_modal(
    source_mode, kind, requested_mode, rejection,
):
    """A refused source transition must not create an uncloseable Tk window."""
    import tkinter as tk

    from gui_modules.application.receiving_multi_settings_window import (
        open_multi_settings,
    )

    root = tk.Tk()
    root.withdraw()
    snapshot = {"active_mode": source_mode}
    calls = []

    def switch_mode(target):
        calls.append(target)
        if rejection == "exception":
            raise ValueError("current Receiving source cannot switch")
        return False

    try:
        with pytest.raises(ValueError, match=(
            "current Receiving source cannot switch"
            if rejection == "exception" else "無法切換設定模式"
        )):
            open_multi_settings(
                root,
                get_snapshot=lambda: dict(snapshot),
                get_switch=lambda: None,
                switch_mode=switch_mode,
                resize_connections=lambda *_args: None,
                dialog_kind=kind,
            )
        assert calls == [requested_mode]
        assert snapshot == {"active_mode": source_mode}
        # Updates exercise pending geometry/Map callbacks: there must be no
        # orphan modal, active Tk grab, or free-variable close() exception.
        root.update_idletasks()
        root.update()
        assert root.winfo_children() == []
        assert getattr(root, "_receiving_multi_settings_window", None) is None
        assert root.grab_current() is None
    finally:
        root.destroy()
