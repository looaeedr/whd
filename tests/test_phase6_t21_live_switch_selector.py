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


def _selector_entries(designer):
    menu = designer.part_choice_menu
    end = menu.index("end")
    out = []
    for index in range((end if end is not None else -1) + 1):
        try:
            out.append((index, str(menu.entrycget(index, "value"))))
        except Exception:
            pass
    return tuple(out)


def _open_designer(model):
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set(model)
    _pump(root)
    designer = app.open_original_fold_designer()
    try:
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
    except Exception:
        pass
    _pump(root)
    return root, app, designer


def _close(root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def test_live_switch_vault_to_receiving_refreshes_door_and_base_selector_semantics_and_callbacks():
    root, _app, designer = _open_designer("金庫型")
    try:
        assert str(designer.baseline_model_var.get()) == "金庫型"
        designer.baseline_model_var.set("受電箱")
        _pump(root)

        parts = tuple(str(key) for key in designer.available_parts)
        expected_keys = (
            "door_c1_r1", "door_c1_r2",
            "base_plate_c1_r1", "base_plate_c1_r2",
        )
        for key in expected_keys:
            assert key in parts, f"live switch must materialize {key}; got {parts!r}"
        assert "door" not in parts
        assert "base_plate" not in parts

        entries = _selector_entries(designer)
        by_value = {value: index for index, value in entries}
        expected_labels = {
            "door_c1_r1": "上門",
            "door_c1_r2": "下門",
            "base_plate_c1_r1": "上門底板",
            "base_plate_c1_r2": "下門底板",
        }
        for stable_id, label in expected_labels.items():
            assert label in by_value, (
                f"live 金庫型→受電箱 must refresh selector label {label!r} for {stable_id}; "
                f"selector={entries!r}"
            )
            designer.part_choice_menu.invoke(by_value[label])
            _pump(root)
            assert designer.active_part_key == stable_id, (
                f"selector {label!r} did not activate {stable_id}; "
                f"active={designer.active_part_key!r}"
            )
    finally:
        _close(root, designer)


def test_live_switch_receiving_back_to_vault_removes_stale_dynamic_selector_entries():
    root, _app, designer = _open_designer("受電箱")
    try:
        designer.baseline_model_var.set("金庫型")
        _pump(root)

        parts = tuple(str(key) for key in designer.available_parts)
        assert "door" in parts
        assert "base_plate" in parts
        assert not any(re.fullmatch(r"door_c\d+_r\d+", key) for key in parts)
        assert not any(re.fullmatch(r"base_plate_c\d+_r\d+", key) for key in parts)

        values = tuple(value for _index, value in _selector_entries(designer))
        assert "門" in values
        assert "底板" in values
        for stale in ("上門", "下門", "上門底板", "下門底板"):
            assert stale not in values
        assert not any(value.startswith("door_c") or value.startswith("base_plate_c") for value in values)
    finally:
        _close(root, designer)


def test_fresh_receiving_selector_matches_live_switch_receiving_semantics():
    root, _app, designer = _open_designer("受電箱")
    try:
        values = tuple(value for _index, value in _selector_entries(designer))
        for label in ("上門", "下門", "上門底板", "下門底板"):
            assert label in values, f"fresh Receiving selector missing {label!r}: {values!r}"
    finally:
        _close(root, designer)
