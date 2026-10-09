"""Custom physical identity stays in the shared top-level workspace."""
from copy import deepcopy
import pytest
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_workspace_controller import Phase6WorkspaceController
from phase6_part_navigation import operator_part_label, project_hierarchy
import phase6_project_file as project

@pytest.mark.parametrize("family", ["金庫型", "受電箱", "分電箱", "自由箱型"])
def test_custom_parts_roundtrip_identity_metadata_and_allocator(tmp_path, family):
    ws = Phase6DesignerWorkspace.from_snapshot({"model":family})
    a = ws.add_custom_part(display_name="加強板", fold_axis="X", transverse_length=123.456)
    b = ws.add_custom_part(display_name="加強板", fold_axis="Y", transverse_length=321, per_box_count=2)
    assert a != b
    ws.update_custom_part(a, display_name="改名板")
    assert ws.custom_part(a)["physical_id"] == a
    assert ws.custom_part(a)["per_box_count"] == 1
    rows = project_hierarchy(ws.available_parts)
    assert all(row.parent_key is None and row.depth == 0 for row in rows if row.part_key in (a,b))
    assert operator_part_label(a, snapshot=ws.snapshot()) == "改名板"
    path = project.write_project(tmp_path/"自訂.p6fold", {"schema":project.PROJECT_SCHEMA,"snapshot":{"model":family,"workspace":ws.snapshot()}})
    loaded = project.read_project(path)["snapshot"]
    restored = Phase6DesignerWorkspace.from_snapshot(loaded)
    assert restored.custom_part(a) == ws.custom_part(a)
    assert restored.custom_part(b)["per_box_count"] == 2
    main = Phase6WorkspaceController()
    main.commit_workspace(restored.snapshot())
    assert main.workspace_snapshot()["custom_parts"] == ws.snapshot()["custom_parts"]
    assert restored.remove_part(a)
    assert restored.remove_part(b)
    empty = restored.snapshot()
    restored = Phase6DesignerWorkspace.from_snapshot({"model":family,"workspace":empty})
    c = restored.add_custom_part(display_name="新板",fold_axis="X",transverse_length=50)
    assert c not in (a,b)
    assert a not in restored.available_parts and b not in restored.available_parts
    main.clear_authoritative_workspace()
    assert "custom_parts" not in main.workspace_snapshot()

@pytest.mark.parametrize("field,value", [
    ("display_name"," "),("fold_axis","XY"),("fold_axis","Z"),
    ("transverse_length",0),("transverse_length",-1),("transverse_length","nan"),
    ("transverse_length","inf"),("transverse_length",True),
    ("per_box_count",0),("per_box_count",-1),("per_box_count",1.5),
    ("per_box_count",True),("per_box_count","2.0"),("per_box_count","abc")])
def test_invalid_custom_input_is_atomic(field,value):
    ws=Phase6DesignerWorkspace.from_snapshot({})
    key=ws.add_custom_part(display_name="板",fold_axis="X",transverse_length=100)
    before=deepcopy(ws.snapshot())
    ws.mark_clean()
    with pytest.raises(ValueError):
        ws.update_custom_part(key, **{field:value})
    assert ws.snapshot() == before
    assert not ws.dirty
    args=dict(display_name="另一板",fold_axis="Y",transverse_length=80,per_box_count=1)
    args[field]=value
    with pytest.raises(ValueError):
        ws.add_custom_part(**args)
    assert ws.snapshot() == before

def test_snapshots_are_defensive_and_custom_profiles_are_not_invented():
    ws=Phase6DesignerWorkspace.from_snapshot({})
    key=ws.add_custom_part(display_name="板",fold_axis="X",transverse_length=100)
    item=ws.custom_part(key); item["per_box_count"]=999
    assert ws.custom_part(key)["per_box_count"] == 1
    assert ws.profiles_for(key) is None
    snap=ws.export_shared_snapshot(live_active_profiles={"X":[{"len":999}]})
    assert key not in snap["part_profiles"]
    assert snap["custom_parts"]["items"][key]["fold_preset"] == "OUTSIDE_17_100"

def test_real_designer_add_rename_save_reload_keeps_top_level_custom(tmp_path,monkeypatch):
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    import gui
    from gui_modules.application.fold_designer_manufacturing_projection import _fold_designer_part_spec_from_payload
    errors=[]
    monkeypatch.setattr(messagebox,"showerror",lambda *a,**kw:errors.append(a))
    root=tk.Tk();root.withdraw()
    try:
        main=gui.BoxCalculatorGUI(root)
        app=main.open_original_fold_designer()
        initial=deepcopy(app.designer_workspace.snapshot())
        win=app.add_part("__custom__")
        win.destroy()
        assert app.designer_workspace.snapshot()==initial
        win=app.add_part("__custom__")
        form=win._custom_form
        values=form._custom_values
        values["display_name"].set("加強板")
        values["fold_axis"].set("Y")
        values["transverse_length"].set("345.678")
        values["per_box_count"].set("0")
        assert form._custom_apply() is None
        assert app.designer_workspace.snapshot()==initial
        values["per_box_count"].set("1")
        key=form._custom_apply()
        assert app.designer_workspace.active_part==key
        assert app.structure_tree.parent("part:"+key)==""
        assert app.structure_tree.item("part:"+key,"text")=="加強板"
        assert app.renderer.canvas.get_tk_widget().winfo_manager()==""
        editor=app._custom_part_editor
        editor._custom_values["display_name"].set("改名加強板")
        editor._custom_values["per_box_count"].set("2")
        assert editor._custom_apply()
        root.update_idletasks()
        assert app.structure_tree.item("part:"+key,"text")=="改名加強板"
        assert app.designer_workspace.custom_part(key)["per_box_count"]==2
        assert app.designer_workspace.profiles_for(key) is None
        with pytest.raises(ValueError,match="正式 Fold"):
            _fold_designer_part_spec_from_payload(main,key,{"w":400,"h":600,"d":200,"t":2,"model":"金庫型"})
        path=tmp_path/"custom-real.p6fold"
        monkeypatch.setattr(filedialog,"asksaveasfilename",lambda **kw:str(path))
        assert app.save_project_file_as()
        loaded=project.read_project(path)["snapshot"]
        reloaded=Phase6DesignerWorkspace.from_snapshot(loaded)
        assert reloaded.custom_part(key)==app.designer_workspace.custom_part(key)
        assert key in reloaded.available_parts
        assert key not in loaded.get("part_profiles",{})
        assert main.workspace_controller.workspace_snapshot()["custom_parts"]==reloaded.snapshot()["custom_parts"]
        second_root=tk.Tk();second_root.withdraw()
        try:
            second=gui.BoxCalculatorGUI(second_root)
            second._apply_phase6_project_snapshot(loaded)
            second_app=second.open_original_fold_designer()
            assert second_app.designer_workspace.custom_part(key)==reloaded.custom_part(key)
            assert second_app.designer_workspace.profiles_for(key) is None
            second_app.activate_part(key)
            assert second_app.structure_tree.parent("part:"+key)==""
            assert second_app._custom_part_editor._custom_values["per_box_count"].get()=="2"
        finally:
            second_root.destroy()
        app.activate_part("box_body")
        assert app._custom_part_editor is None
        assert app.renderer.canvas.get_tk_widget().winfo_manager()
        app.activate_part(key)
        assert app.remove_part(key)
        assert app.designer_workspace.custom_part(key) is None
        assert app.designer_workspace.active_part == "box_body"
        assert app._custom_part_editor is None
    finally:
        root.destroy()

def test_project_workspace_export_preserves_deleted_id_history():
    from phase6_project_controller import Phase6ProjectController
    ws=Phase6DesignerWorkspace.from_snapshot({})
    key=ws.add_custom_part(display_name="板",fold_axis="X",transverse_length=100)
    ws.remove_part(key)
    exported=Phase6ProjectController.build_workspace_export(
        owner_workspace=ws.export_shared_snapshot(),box_body_profile=[],structure_state={})
    assert exported["custom_parts"]["items"] == {}
    restored=Phase6DesignerWorkspace.from_snapshot({"workspace":exported})
    assert restored.add_custom_part(display_name="新板",fold_axis="Y",transverse_length=90) != key
