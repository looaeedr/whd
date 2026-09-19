from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


def _menu_values(menu):
    end = menu.index("end")
    if end is None:
        return ()
    values = []
    for index in range(end + 1):
        try:
            values.append(str(menu.entrycget(index, "value")))
        except Exception:
            pass
    return tuple(values)


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def yview_scroll(self, steps, unit):
        self.calls.append((steps, unit))


def test_mousewheel_nonnumeric_event_num_is_safe_and_preserves_windows_delta_direction():
    app = SimpleNamespace(assembly_parts_canvas=_FakeCanvas())

    result = bridge._phase6_scroll_assembly_parts(
        app,
        SimpleNamespace(delta=120, num="??"),
    )

    assert result == "break"
    assert app.assembly_parts_canvas.calls == [(-1, "units")]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#374 target layout requires real Tk/Xvfb")
def test_target_main_selector_owns_assembly_parts_and_corner_data_without_old_content_switch():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app

    try:
        for _ in range(3):
            root.update_idletasks()
            root.update()

        values = _menu_values(designer.part_choice_menu)

        assert values, "main sheet selector must remain populated"
        assert values[0] == "組合體", (
            "RED: #373 main selector does not yet contain assembly + existing parts + corner data"
        )
        assert "箱身" in values
        assert values[-1] == "截角資料", (
            "RED: #373 main selector does not yet contain assembly + existing parts + corner data"
        )

        old_switch = getattr(designer, "content_switch_frame", None)
        assert old_switch is None or not old_switch.winfo_ismapped(), (
            "RED: old 輸入區/組合體/截角資料 content switch is still mapped"
        )
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
