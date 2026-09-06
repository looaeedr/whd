from __future__ import annotations

import os
import re

import pytest


pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)


def _pump(root):
    root.update_idletasks()
    root.update()


def test_receiving_materializes_exactly_one_base_plate_per_door_cell():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root)

        designer = app.open_original_fold_designer()
        _pump(root)

        doors = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if re.fullmatch(r"door_c\d+_r\d+", str(key))
        ))
        assert len(doors) >= 2, f"Receiving Door topology precondition missing: {doors!r}"

        expected = tuple(sorted(
            key.replace("door_", "base_plate_", 1)
            for key in doors
        ))
        actual = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if str(key) == "base_plate"
            or re.fullmatch(r"base_plate_c\d+_r\d+", str(key))
        ))

        assert actual == expected, (
            "Receiving contract is one Door : one Base Plate; "
            f"expected {expected!r}, got {actual!r}"
        )
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
