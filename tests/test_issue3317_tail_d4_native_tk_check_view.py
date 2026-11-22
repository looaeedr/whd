# -*- coding: utf-8 -*-
"""#3317 actual WHD Tk Ø4 CHECK window: Factory body/real Tail/true world.

This is a CHECK view from WHD Engine, never a fabrication drawing or a
substitute for unperformed AutoCAD/physical-BoxBody acceptance.
"""
import base64
from io import BytesIO
import os
import tkinter as tk

import pytest

import gui
from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import triangle_bounds


def test_actual_whd_gui_d4_check_window_four_factory_holes_and_native_world(
    record_property,
):
    if os.name!="nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk/Xvfb GUI")
    root=tk.Tk()
    root.withdraw()
    designer=None
    win=None
    try:
        main=gui.BoxCalculatorGUI(root)
        main.baseline_var.set("金庫型")
        main.w_var.set("620")
        main.h_var.set("600")
        main.d_var.set("185")
        if hasattr(main,"t_var"):
            main.t_var.set("2")
        main._apply_existing_parts_from_fold_workspace(
            ["box_body","head","tail"],
        )
        designer=main.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        designer.activate_part("tail")
        # REAL native Fold Editor; do not alter a test-created FinalScene.
        editor=designer.bend_ui
        editor.nb.select(editor.tabs.index("Y"))
        root.update_idletasks()
        root.update()
        editor.on_tab(None)
        editor.render()
        rows=editor.get_active_dict()["Y"]
        bottom_idx=next(i for i,seg in enumerate(rows)
                        if seg.get("phase6_key")=="ybottom1")
        candidate=[dict(seg) for seg in rows]
        candidate[bottom_idx]["len"]=48.
        displayed=api.project_operator_fold_editor_display_rows(
            candidate,getattr(designer.state,"phase6_thickness",2.),
        )
        editor.controls[bottom_idx]["len"].set(
            str(displayed[bottom_idx]["len"])
        )
        editor.save()
        designer._save_current_part(notify=False)
        root.update_idletasks()
        root.update()
        page=designer.settings_panel.render_context("tail")
        state=page["extension_state"]
        assert state["tail_lower_v_choice_widget"].winfo_exists()
        button=state.get("tail_d4_check_widget")
        assert button is not None and button.winfo_exists()
        before=dict(designer._phase6_input_snapshot)
        button.invoke()
        root.update_idletasks()
        root.update()
        matches=[
            w for w in designer.root.winfo_children()
            if isinstance(w,tk.Toplevel) and "CHECK_NOT_CNC" in w.title()
        ]
        assert len(matches)==1, (
            "D4_NATIVE_GUI_CHECK_VIEW_NOT_SHOWN",
            designer.settings_status_var.get(),
        )
        win=matches[0]
        flat=win._tail_d4_check_flat
        check=win._tail_d4_check_shell
        body=win._tail_d4_check_body_world
        placed=win._tail_d4_check_placed_world
        assert flat.source_spec.width==620
        assert flat.source_spec.depth==185
        assert flat.source_spec.thickness==2
        assert len([p for p in flat.result_scene.primitives
                    if p.layer=="CUTTING"])==5  # outer+four real Factory
        assert len([p for p in flat.result_scene.primitives
                    if p.layer=="BEND"])==5
        assert not any(getattr(p,"semantic_id",None)==
                       "USER_ADDED_CHECK_CUTTING"
                       for p in flat.result_scene.primitives)
        assert len(placed)==len(check.shell_faces)
        assert triangle_bounds(body)[1][0]==pytest.approx(-298.,abs=1e-7)
        assert designer._phase6_input_snapshot==before
        figure=win._tail_d4_check_figure
        assert len(figure.axes)==5
        section=figure.axes[2]
        assert section.lines, "native upper two folds source section missing"
        assert figure.axes[3].collections and figure.axes[4].collections
        assert any(
            "CHECK_NOT_CNC" in str(t.get_text())
            for t in figure.texts
        )
        root.update_idletasks()
        root.update()

        # The screenshot is captured from the real live Tk window. On a
        # runner without ImageGrab support use the same Figure embedded in
        # the Tk canvas and label that fallback precisely.
        raw=BytesIO()
        capture_type="REAL_TK_WINDOW"
        try:
            from PIL import ImageGrab
            x=win.winfo_rootx();y=win.winfo_rooty()
            w=win.winfo_width();h=win.winfo_height()
            if w<600 or h<350:
                raise RuntimeError("Tk CHECK window was not fully mapped")
            ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(raw,format="PNG")
        except (ImportError,RuntimeError,OSError):
            capture_type="TK_CANVAS_FIGURE_ONLY"
            figure.savefig(raw,format="png",dpi=85)
        record_property(
            "ISSUE3317_REAL_D4_NATIVE_TK_CAPTURE",
            capture_type+":"+base64.b64encode(raw.getvalue()).decode("ascii"),
        )
        assert len(raw.getvalue())>3000
    finally:
        if win is not None:
            try:win.destroy()
            except tk.TclError:pass
        if designer is not None:
            try:designer.root.destroy()
            except tk.TclError:pass
        root.destroy()
