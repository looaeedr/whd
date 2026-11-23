import pytest
from copy import deepcopy
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project
from gui_modules.application.endcap_live_v_check_consumer import ATTR, KEY, capture_current, replay_current


def choose(app):
    app.workspace_controller.set_active_part("head")
    app.manual_corner_pair_same["head"]["bottom"] = False
    app.manual_active_corner_var.set("bottom_left")


@pytest.mark.parametrize("axis",("x","y"))
def test_actual_native_head_live_check_project_save_reopen(tmp_path,monkeypatch,axis):
    import tkinter as tk
    from gui import BoxCalculatorGUI
    from tkinter import messagebox
    replies=[]
    monkeypatch.setattr(messagebox,"showinfo",lambda title,msg: replies.append(("info",msg)))
    monkeypatch.setattr(messagebox,"showerror",lambda title,msg: replies.append(("error",msg)))
    r=tk.Tk(); r.withdraw()
    try:
        a=BoxCalculatorGUI(r)
        a.baseline_var.set("自訂")
        choose(a)
        a.v_miter_gui_check_corners={"head":{"bottom_left":"V_MITER_CHECK"}}
        a.v_miter_gui_first_bend_axes={"head":{"bottom_left":axis}}
        a.v_miter_capture_live_source_button.invoke()
        assert replies[-1][0]=="info",replies
        rec=getattr(a,ATTR)["head"]["bottom_left"]
        assert rec["first_bend_axis"]==axis
        old=a._compose_phase6_project_snapshot_from_main_gui()
        assert old[KEY]["head"]["bottom_left"]==rec
        p=tmp_path/"new.p6fold"
        write_project(p,{"schema":PROJECT_SCHEMA_V1,"snapshot":old})
        snap=read_project(p)["snapshot"]
        assert snap[KEY]["head"]["bottom_left"]==rec
        r2=tk.Tk();r2.withdraw()
        try:
            fresh=BoxCalculatorGUI(r2)
            fresh._apply_phase6_project_snapshot(snap)
            choose(fresh)
            model=fresh._make_original_fold_designer_snapshot()
            fresh.v_miter_check_source_button.invoke()
            view = fresh._endcap_live_saved_check_window
            assert view.winfo_exists()
            assert "已保存試算／非加工" in view.title()
            assert view._saved_endcap_check_2d_canvas.find_all()
            assert all(view._saved_endcap_check_3d_triangles)
            v=replay_current(fresh,model)
            assert view._saved_endcap_check_replay == v
            assert v.manufacturing_status.endswith("UNCERTIFIED")
            assert {x.layer for x in v.full_sheet_check_scene.primitives}<={"CHECK","DATUM"}
            assert fresh._compose_phase6_project_snapshot_from_main_gui()[KEY]==old[KEY]
            bad=deepcopy(snap); bad[KEY]["head"]["bottom_left"]["source_fold_sha256"]="0"*64
            fresh._apply_phase6_project_snapshot(bad)
            assert not view.winfo_exists()
            choose(fresh)
            fresh.v_miter_check_source_button.invoke()
            assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
            assert replies[-1][0]=="error" and "V_MITER_LIVE_SOURCE_CHANGED" in replies[-1][1]
            with pytest.raises(ValueError,match="V_MITER_LIVE_SOURCE_CHANGED"):
                replay_current(fresh,fresh._make_original_fold_designer_snapshot())
            legacy=deepcopy(snap); legacy.pop(KEY)
            fresh._apply_phase6_project_snapshot(legacy)
            choose(fresh)
            assert replay_current(fresh,fresh._make_original_fold_designer_snapshot()) is None
            assert KEY not in fresh._compose_phase6_project_snapshot_from_main_gui()
        finally:r2.destroy()
    finally:r.destroy()
