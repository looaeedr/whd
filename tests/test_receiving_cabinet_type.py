# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import pytest


def test_receiving_cabinet_is_registered_as_peer_not_vault_alias():
    from ae_engine.cabinet_types import resolve_cabinet_type

    receiving = resolve_cabinet_type("受電箱")
    vault = resolve_cabinet_type("金庫型")

    assert receiving.canonical_name == "受電箱"
    assert receiving is not vault
    assert receiving.module_name.endswith(".receiving")
    assert "受電箱" not in vault.aliases


def test_receiving_cabinet_is_visible_in_the_existing_baseline_model_selector_only(monkeypatch):
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        values = tuple(app.baseline_cb.cget("values"))
        assert "受電箱" in values
        assert "自訂" in values
        assert not hasattr(app, "cabinet_type_cb")
        assert not hasattr(app, "cabinet_type_var")

        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app.baseline_var.set("受電箱")
        snapshot = app._make_original_fold_designer_snapshot()
        assert snapshot["model"] == "受電箱"
        assert "cabinet_type" not in snapshot
        assert "受電箱" in snapshot["baseline_models"]

        app.baseline_var.set("金庫型")
        app._apply_phase6_project_snapshot(snapshot)
        assert app.baseline_var.get() == "受電箱"
    finally:
        root.destroy()



def test_main_runtime_widget_tree_has_one_model_selector_and_build_marker(monkeypatch):
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui

    monkeypatch.setattr(gui.ae, "get_baseline_list", lambda: ["金庫型"])
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        root.update_idletasks()
        labels = []
        combos = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    text = str(child.cget("text"))
                except Exception:
                    text = ""
                if text:
                    labels.append(text)
                if child.winfo_class() in {"TCombobox", "Combobox"}:
                    combos.append(child)
                walk(child)

        walk(root)
        assert "盤體類型 :" not in labels
        assert labels.count("基準型號 :") == 1
        assert tuple(app.baseline_cb.cget("values")) == ("金庫型", "受電箱", "自訂")
        assert gui.PHASE6_BUILD_ID in root.title()
    finally:
        root.destroy()

def test_legacy_split_snapshot_migrates_receiving_family_into_model(monkeypatch):
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot["model"] = "金庫型"
        snapshot["cabinet_type"] = "受電箱"
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app._apply_phase6_project_snapshot(snapshot)
        assert app.baseline_var.get() == "受電箱"
    finally:
        root.destroy()


def test_receiving_is_also_visible_in_3d_existing_baseline_model_selector():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks()
        menu = designer.baseline_model_combo._phase6_menu
        values = tuple(menu.entrycget(index, "label") for index in range(menu.index("end") + 1))
        assert "受電箱" in values
        assert not hasattr(designer, "cabinet_type_var")
        assert not hasattr(designer, "cabinet_type_cb")
    finally:
        root.destroy()


def test_switching_3d_baseline_model_to_receiving_applies_receiving_family_policy():
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()

        assert designer._settings_values["w"] == 800.0
        assert designer._settings_values["h"] == 1600.0
        assert designer._settings_values["d"] == 350.0
        assert designer._settings_values["fw"] == 29.0
        assert designer._phase6_input_snapshot["assembly_type"] == "WRAP_OVERLAY"
        assert designer._settings_values["door_fold_l"] == 19.0
        assert designer._settings_values["door_fold_r"] == 19.0
        assert designer._settings_values["door_fold_t"] == 19.0
        assert designer._settings_values["door_fold_b"] == 19.0
        keys = [row.get("phase6_key") for row in designer.state.profiles_vault["箱身"]]
        assert keys == ["zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"]
        structure = designer.designer_workspace.box_body_structure_state()
        assert structure["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        assert structure["locked"] is True
    finally:
        root.destroy()
