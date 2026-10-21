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
        assert identity not in _canonical_part_keys(designer)

        payload=build_scene_payload_for_app(designer,identity)
        material=designer._scene_query_callback(identity,payload)
        assert material.scene is not None
        assert material.material.area > 0
        assert material.unfolded_topology.piece_id==identity
        assert material.metadata["nfb_deferred_manufacturing_role"]=="PAD"
        assert material.metadata["manufacturing_ready"] is False
        assert len(material.fold_guides)==2
        print("PAD_REAL_TK_OPERATOR_2D",identity,
              material.unfolded_topology.width,
              material.unfolded_topology.height,
              len(material.fold_guides),flush=True)
    finally:
        root.destroy()
