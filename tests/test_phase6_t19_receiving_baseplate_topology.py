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



@pytest.mark.parametrize(
    "heights, expected_count",
    [
        ([1600.0], 1),
        ([500.0, 500.0, 600.0], 3),
    ],
)
def test_receiving_base_plate_count_tracks_one_and_three_door_topology(heights, expected_count):
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root)
        app.multi_door_enabled_var.set(True)
        app.set_door_layout_columns([(800.0, heights)])
        _pump(root)

        designer = app.open_original_fold_designer()
        _pump(root)

        doors = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if re.fullmatch(r"door_c\d+_r\d+", str(key))
        ))
        bases = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if re.fullmatch(r"base_plate_c\d+_r\d+", str(key))
        ))
        assert len(doors) == expected_count
        assert len(bases) == expected_count
        assert bases == tuple(
            key.replace("door_", "base_plate_", 1)
            for key in doors
        )
        assert "base_plate" not in tuple(designer.available_parts)
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



def test_receiving_dynamic_base_plates_are_real_topology_owned_workspace_parts():
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

        bases = tuple(sorted(
            str(key) for key in tuple(designer.available_parts)
            if re.fullmatch(r"base_plate_c\d+_r\d+", str(key))
        ))
        assert bases == ("base_plate_c1_r1", "base_plate_c1_r2")

        for key in bases:
            profiles = designer.designer_workspace.profiles_for(key)
            assert profiles is not None
            assert profiles.get("X") and profiles.get("Y")
            designer.activate_part(key)
            _pump(root)
            assert designer.active_part_key == key
            assert str(designer.remove_part_button.cget("state")) == "disabled"
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



def test_receiving_dynamic_base_plate_stable_id_is_accepted_by_main_render_query():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root)
        snapshot = app._make_original_fold_designer_snapshot()
        render_data = app._query_fold_designer_render_data(
            "base_plate_c1_r1",
            snapshot,
        )
        assert render_data is not None
    finally:
        try:
            root.destroy()
        except Exception:
            pass
