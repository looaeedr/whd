from __future__ import annotations
import os
import pytest


def test_receiving_family_defaults_are_800_1600_350():
    from ae_engine.cabinet_types.receiving import apply_family_defaults
    result = apply_family_defaults({"model":"金庫型", "w":400, "h":600, "d":250, "t":2})
    assert result["model"] == "受電箱"
    assert (result["w"], result["h"], result["d"]) == (800.0, 1600.0, 350.0)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_live_switch_to_receiving_rebases_whd_with_string_ui_setting_in_snapshot():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        d = app.open_original_fold_designer(); root.update_idletasks(); root.update()
        # ui_text_size is a string setting carried by the same family snapshot.
        # It must not abort the W/H/D transaction half-way through.
        bridge._phase6_apply_setting_updates(d, {"ui_text_size": "medium"}, notify=False)
        d._phase6_input_snapshot["ui_text_size"] = "medium"
        d.baseline_model_var.set("受電箱"); root.update_idletasks(); root.update()

        expected = {"w": 800.0, "h": 1600.0, "d": 350.0}
        assert {k: float(d._phase6_input_snapshot[k]) for k in expected} == expected
        assert {k: float(d._settings_values[k]) for k in expected} == expected
        assert {k: float(d.left_global_vars[k].get()) for k in expected} == expected
        assert (float(d.v_w.get()), float(d.v_h.get()), float(d.v_d.get())) == (800.0, 1600.0, 350.0)
        assert (float(app.w_var.get()), float(app.h_var.get()), float(app.d_var.get())) == (800.0, 1600.0, 350.0)
    finally:
        try:
            if app.fold_designer_window is not None: app.fold_designer_window.destroy()
        except Exception: pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_live_switch_to_receiving_applies_whd_without_standalone_wrap_toggle():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part

    root=tk.Tk(); root.withdraw(); app=gui.BoxCalculatorGUI(root)
    try:
        d=app.open_original_fold_designer(); root.update_idletasks(); root.update()
        d.baseline_model_var.set("受電箱"); root.update_idletasks(); root.update()
        assert {k:d.left_global_vars[k].get() for k in ("w","h","d")} == {"w":"800","h":"1600","d":"350"}
        assert {k:float(d._phase6_input_snapshot[k]) for k in ("w","h","d")} == {"w":800.0,"h":1600.0,"d":350.0}

        # 2026-09-03 contract: fresh receiving directly owns the formal
        # 包覆貼外 preset. BOTTOM is fixed WRAP; no standalone enable toggle.
        assert d._phase6_input_snapshot["assembly_type"] == "WRAP_OVERLAY"
        assert d.assembly_type_var.get() == "包覆貼外"
        assert edge_relation_for_part(d._phase6_input_snapshot, "head", "BOTTOM") is AssemblyJointRelation.WRAP
        assert edge_relation_for_part(d._phase6_input_snapshot, "tail", "BOTTOM") is AssemblyJointRelation.WRAP
        d.activate_part("head"); root.update_idletasks(); root.update()
        assert getattr(d, "bottom_wrap_persistent_cell", None) is None
        assert getattr(d, "bottom_wrap_persistent_checkbutton", None) is None

        # Unlocking parameters may expose WRAP reserve values, never another enable switch.
        bridge._phase6_toggle_parameter_panel(d); root.update_idletasks(); root.update()
        assert d.bottom_wrap_widget is not None
        assert d.bottom_wrap_widget.winfo_manager() == "grid"
        assert d.bottom_wrap_enabled_var is None
        texts = [str(child.cget("text")) for child in d.bottom_wrap_widget.winfo_children() if "text" in child.keys()]
        assert not any("啟用" in text or "WRAP" == text.strip() for text in texts)
    finally:
        try:
            if app.fold_designer_window is not None: app.fold_designer_window.destroy()
        except Exception: pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_endcap_switching_does_not_accumulate_thickness_or_blank_size():
    import tkinter as tk
    import gui
    root=tk.Tk(); root.withdraw(); app=gui.BoxCalculatorGUI(root)
    try:
        d=app.open_original_fold_designer(); root.update_idletasks(); root.update()
        d.baseline_model_var.set("受電箱"); root.update_idletasks(); root.update()
        d.activate_part("head"); root.update_idletasks(); root.update()
        expected_d=float(d._settings_values["d"])
        expected_head=d.unfolded_size_var.get()
        seen=[]
        for key in ("tail","head")*5:
            d.activate_part(key); root.update_idletasks(); root.update()
            seen.append((key,float(d._settings_values["d"]),d.unfolded_size_var.get()))
        assert expected_d == 350.0
        assert all(item[1] == expected_d for item in seen)
        head_texts=[text for key,_d,text in seen if key=="head"]
        assert head_texts and all(text == expected_head for text in head_texts)
    finally:
        try:
            if app.fold_designer_window is not None: app.fold_designer_window.destroy()
        except Exception: pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_assembly_input_area_uses_all_remaining_left_space():
    import tkinter as tk
    import gui
    root=tk.Tk(); root.withdraw(); app=gui.BoxCalculatorGUI(root)
    try:
        d=app.open_original_fold_designer(); root.update_idletasks(); root.update()
        assert d.part_var.get() == "組合體"
        info=d.assembly_parts_panel.pack_info()
        assert info.get("fill") == "both"
        assert int(info.get("expand", 0)) == 1
        assert int(float(d.assembly_parts_canvas.cget("height"))) <= 1
        assert d.fold_editor_host.winfo_manager() == ""
    finally:
        try:
            if app.fold_designer_window is not None: app.fold_designer_window.destroy()
        except Exception: pass
        root.destroy()

@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_assembly_mode_has_no_separate_labeled_flag_frame():
    import tkinter as tk
    from tkinter import ttk
    import gui
    root=tk.Tk(); root.withdraw(); app=gui.BoxCalculatorGUI(root)
    try:
        d=app.open_original_fold_designer(); root.update_idletasks(); root.update()
        assert d.part_var.get() == "組合體"
        # 組合體內容直接使用左側剩餘空間，不再用帶標題的 LabelFrame 切出一塊「旗標/框」。
        assert isinstance(d.assembly_parts_panel, ttk.Frame)
        assert not isinstance(d.assembly_parts_panel, ttk.LabelFrame)
        assert d.assembly_parts_panel.pack_info().get("fill") == "both"
        assert int(d.assembly_parts_panel.pack_info().get("expand", 0)) == 1
    finally:
        try:
            if app.fold_designer_window is not None: app.fold_designer_window.destroy()
        except Exception: pass
        root.destroy()
