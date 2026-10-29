# -*- coding: utf-8 -*-
"""Real Tk receiving PAD 2D navigator UAT (isolated sanitized project).

Exercises original button callbacks and actual physical source; no manual
BasePlate injection, no guessed WORLD-X and no manufacturing release.
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

from tests.test_issue1503_saved_project_gui_red import (
    FIXTURE, _pump, _walk, _buttons,
)


def _choose_pair(root, state):
    row=state["rows"][0]
    while row["assigned"].size():
        row["assigned"].selection_clear(0,tk.END)
        row["assigned"].selection_set(0)
        remove=_buttons(row["section"],"－移除")
        assert len(remove)==1
        remove[0].invoke()
        _pump(root)
    for name in ("3P400SN","100HN-s"):
        options=row["available"]
        names=[str(options.get(i)) for i in range(options.size())]
        assert name in names, ("NFB_SELECTED_SOURCE_CSV_MISSING",name,names)
        index=names.index(name)
        options.selection_clear(0,tk.END)
        options.selection_set(index)
        options.activate(index)
        plus=_buttons(row["section"],"＋加入")
        assert len(plus)==1
        plus[0].invoke()
        _pump(root)
    assert tuple(row["assigned"].get(0,tk.END))==("3P400SN","100HN-s")


def test_real_tk_normal_confirm_populates_clickable_pad_2d_unfolded_sheet(tmp_path):
    import gui
    import fold_designer_bridge as bridge
    from unittest.mock import patch
    from phase6_manufacturing_adapter import build_scene_payload_for_app, _canonical_part_keys
    from phase6_part_navigation import operator_part_selector_keys,operator_part_label

    root=tk.Tk()
    root.withdraw()
    try:
        app=gui.BoxCalculatorGUI(root)
        project=tmp_path/"isolated-nfb-pad-2d.p6fold"
        project.write_bytes(Path(FIXTURE).read_bytes())
        designer=app.load_phase6_project(project,open_designer=True)
        _pump(root)
        assert not designer._phase6_input_snapshot.get("receiving_base_plate")

        settings=bridge._phase6_open_receiving_single_settings(designer)
        _pump(root)
        select=settings._receiving_multi_setting_list
        select.selection_clear(0,tk.END)
        select.selection_set(1)
        select.event_generate("<<ListboxSelect>>")
        _pump(root)
        edit=_buttons(settings._receiving_multi_settings_host,"編輯")
        assert len(edit)==1
        edit[0].invoke()
        _pump(root)

        editor=app.last_unified_hole_editor
        editor._receiving_config_tabs.select(1)
        _pump(root)
        frame=next(w for w in _walk(editor)
                   if hasattr(w,"_receiving_inner_switch_state") and w.winfo_exists())
        _choose_pair(root,frame._receiving_inner_switch_state)
        _buttons(frame,"確定")[0].invoke()
        _pump(root)
        assert len(editor._receiving_pending_features())==2
        _buttons(editor,"確定全部")[0].invoke()
        _pump(root)
        snap=designer._phase6_input_snapshot
        assert snap["nfb_config_submitted"] is True
        from ae_engine.receiving_base_plate_config import receiving_base_plate_values
        assert receiving_base_plate_values(snap)["receiving_bend_pattern"]=="LEFT_FLAT_SIDE"

        assembly=bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        assert len(assembly.formed_nfb_pad_skins)==1
        pads=tuple(key for key in designer.designer_workspace.available_parts
                   if key.startswith("nfb_pad:"))
        assert len(pads)==1, ("PAD_NATIVE_2D_NAV_NOT_PUBLISHED",pads)
        identity=pads[0]
        assert identity in operator_part_selector_keys(
            designer.designer_workspace.available_parts)
        assert "墊高片" in operator_part_label(identity,snapshot=snap)

        # Native GUI acceptance must exercise the ORIGINAL Tk operator menu,
        # not merely the workspace identity/adapter's programmatic 2D scene.
        # The old GUI failed here even while assembly and 2D render probes
        # passed: it never refreshed this Tk menu after NFB Confirm All.
        menu = designer.part_choice_menu
        matches = [
            (i, str(menu.entrycget(i, "label")))
            for i in range(menu.index("end") + 1)
            if "墊高片" in str(menu.entrycget(i, "label"))
        ]
        assert len(matches) == 1, ("PAD_NATIVE_TK_MENU_NOT_REFRESHED", matches)
        index, label = matches[0]
        menu.invoke(index)
        _pump(root)
        assert designer.designer_workspace.active_part == identity
        assert designer.part_var.get() == label
        assert designer._phase6_3d_display_mode == "single"

        # Reproduce a transient stale workspace feature stash: canonical
        # committed snapshot + assembly have a genuine PAD, but the old
        # workspace-first navigation erased its 2D entry on a resync.
        # A confirmed submitted root must outrank old editor features.
        assert snap["part_features"]
        stale_features = {
            key: [] for key in snap["part_features"]
            if str(key).startswith("inner_door:")
        }
        assert stale_features
        with patch.object(
            designer.designer_workspace,"part_features_snapshot",
            return_value=stale_features,
        ):
            bridge._phase6_sync_authoritative_derived_parts(designer)
        assert identity in designer.designer_workspace.available_parts, (
            "PAD_ASSEMBLY_VISIBLE_BUT_2D_PART_SELECTOR_MISSING", identity
        )
        assert identity in operator_part_selector_keys(
            designer.designer_workspace.available_parts)
        assert identity not in _canonical_part_keys(designer)

        payload=build_scene_payload_for_app(designer,identity)
        material=designer._scene_query_callback(identity,payload)
        assert material.scene is not None
        assert material.material.area > 0
        assert material.unfolded_topology.piece_id==identity
        assert material.metadata["nfb_deferred_manufacturing_role"]=="PAD"
        assert material.metadata["manufacturing_ready"] is False
        assert len(material.fold_guides)==2
        # Real native Tk 2D CUTTING/HOLE/BEND drawing; do not accept only an
        # invisible PartRenderData or a manually invented illustration.
        from PIL import ImageGrab
        import numpy as np
        from gui import render_drawing_scene, _phase6_2d_material_viewport
        canvas_window = tk.Toplevel(root)
        canvas_window.geometry("900x720+25+25")
        canvas_window.lift()
        display = tk.Canvas(canvas_window,width=880,height=690,bg="#182030")
        display.pack(fill=tk.BOTH,expand=True)
        _pump(root)
        bounds = material.material.bounds
        transform,*_ = _phase6_2d_material_viewport(
            bounds,display.winfo_width(),display.winfo_height(),
            top_gutter=24,right_gutter=24,bottom_gutter=24,left_gutter=24,
        )
        def grab():
            x,y=display.winfo_rootx(),display.winfo_rooty()
            w,h=display.winfo_width(),display.winfo_height()
            return np.asarray(ImageGrab.grab(bbox=(x,y,x+w,y+h)).convert("RGB")).copy()
        before=grab()
        render_drawing_scene(display,material.scene,transform,
                             skip_layers=("CHECK","STOCK"))
        _pump(root)
        items=tuple(display.find_all())
        polygons=[i for i in items if display.type(i)=="polygon"]
        screw_holes=[i for i in items if display.type(i)=="oval"]
        blue_bends=[i for i in items if display.type(i)=="line"
                    and display.itemcget(i,"fill")=="#0a84ff"]
        assert (len(polygons),len(screw_holes),len(blue_bends))==(1,4,2)
        after=grab()
        delta=np.max(np.abs(after.astype("int16")-before.astype("int16")),axis=2)
        changed=int(np.count_nonzero(delta>32))
        assert changed>1000, ("PAD_TK_2D_DRAWN_BUT_NOT_VISIBLE",changed)
        from PIL import Image
        output=Path("pad-native-tk-2D.png")
        Image.fromarray(after).save(output)
        canvas_window.destroy()
        print("PAD_REAL_TK_OPERATOR_2D",identity,
              material.unfolded_topology.width,
              material.unfolded_topology.height,
              "real_shapes",len(polygons),len(screw_holes),len(blue_bends),
              "pixel_delta",changed,flush=True)

        # Same REAL Tk shell's dedicated Part-only manufacturing button:
        # set operator-supplied material/process/count explicitly. This must
        # call the live PAD+actual Base assembly and emit verified Q3 DXF,
        # not reuse the old preview-only PDF or an unscoped export.
        from unittest.mock import patch
        import json
        assert app.btn_export_pad_base.winfo_exists()
        with (
            patch("tkinter.simpledialog.askstring",side_effect=("SPCC","LASER")),
            patch("tkinter.simpledialog.askinteger",return_value=3),
            patch("tkinter.filedialog.askdirectory",return_value=str(tmp_path)),
            patch("tkinter.messagebox.showerror",
                  side_effect=AssertionError("PAD_NATIVE_TK_EXPORT_REJECTED")),
            patch("tkinter.messagebox.showinfo") as info,
        ):
            app.btn_export_pad_base.invoke()
        _pump(root)
        packages=tuple(tmp_path.glob("*__PAD_BASE_PAIR_CHECK_Q"))
        assert len(packages)==1,("PAD_NATIVE_TK_NO_PAIRED_EXPORT",packages)
        manifest=json.loads((packages[0]/
            "PAD_BASE_PAIR_PART_ONLY_CHECK_Q_RECEIPT.json").read_text(encoding="utf-8"))
        assert manifest["pad_total"]==3
        assert manifest["base_total"]==3
        assert len(tuple(packages[0].glob("*.dxf")))==2
        assert info.called
        print("PAD_REAL_TK_BUTTON_PART_ONLY_Q_DXF_PASS",
              manifest["pad_total"],manifest["base_total"],flush=True)

        # Full native Save As -> load saved project -> rebuild the 2D owner.
        # A derived PAD must follow the authoritative saved NFB config and
        # real committed editor features, not an ephemeral in-memory list.
        from unittest.mock import patch
        saved_path = tmp_path / "pad-native-save-reopen.p6fold"
        with patch("tkinter.filedialog.asksaveasfilename",
                   return_value=str(saved_path)):
            saved = designer.save_project_file_as()
        assert saved and saved_path.exists(), "PAD_NATIVE_SAVE_AS_FAILED"
        reloaded = app.load_phase6_project(saved_path, open_designer=True)
        _pump(root)
        reloaded_parts=tuple(key for key in reloaded.designer_workspace.available_parts
                             if key.startswith("nfb_pad:"))
        assert reloaded_parts == (identity,), (
            "PAD_NATIVE_SAVED_2D_NAVIGATION_MISSING",reloaded_parts
        )
        # Reload must also rebuild the actual operator-facing Tk menu; a
        # saved authoritative Part identity alone is not a clickable sheet.
        saved_menu = reloaded.part_choice_menu
        saved_pad_entries = [
            i for i in range(saved_menu.index("end") + 1)
            if "墊高片" in str(saved_menu.entrycget(i, "label"))
        ]
        assert len(saved_pad_entries) == 1, (
            "PAD_NATIVE_SAVED_TK_MENU_NOT_REFRESHED", saved_pad_entries
        )
        saved_menu.invoke(saved_pad_entries[0])
        _pump(root)
        assert reloaded.designer_workspace.active_part == identity
        restored=bridge._phase6_final_scene_adapter(
            reloaded).query_assembly_render_data()
        assert len(restored.formed_nfb_pad_skins)==1
        redrawn=reloaded._scene_query_callback(
            identity,build_scene_payload_for_app(reloaded,identity))
        assert redrawn.material.equals(material.material)
        assert redrawn.unfolded_topology==material.unfolded_topology
        assert redrawn.metadata["manufacturing_ready"] is False
        print("PAD_REAL_TK_SAVED_REOPEN_SOURCE_PASS",
              saved_path.name,identity,flush=True)
    finally:
        root.destroy()
