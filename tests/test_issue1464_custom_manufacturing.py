"""Real standalone custom folds share manufacturing, mesh and DXF truth."""
from copy import deepcopy
from dataclasses import replace
from math import nan, inf
import pytest
import ezdxf
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_custom_fold_profiles import build_custom_part_profiles, custom_part_spec
from phase6_fold_profiles import engine_segment_length_to_ui, ui_angle_to_engine
from ae_engine.contracts import CustomFoldPartSpec
from ae_engine.manufacturing_api import build_part_render_data, generate_part, verify_saved_part_render_data_dxf
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_final_scene_projection import _phase6_folded_mesh_from_polygon, _phase6_profile_geometry
import phase6_project_file as project

def specimen(axis="X",t=2,span=123.456):
    ws=Phase6DesignerWorkspace.from_snapshot({"model":"金庫型"})
    key=ws.add_custom_part(display_name="加強板",fold_axis=axis,transverse_length=span,per_box_count=2)
    snapshot={"model":"金庫型","t":t,**ws.snapshot()}
    profiles=build_custom_part_profiles(snapshot,key)
    return ws,key,snapshot,profiles,custom_part_spec(snapshot,key,profiles=profiles)

@pytest.mark.parametrize("axis",["X","Y"])
@pytest.mark.parametrize("t",[1,2,2.5,3])
def test_outside_mapping_axis_precision_real_scene_mesh_dxf(tmp_path,axis,t):
    ws,key,snapshot,profiles,spec=specimen(axis,t)
    assert [engine_segment_length_to_ui(row) for row in profiles[axis]]==[17,100]
    assert profiles[axis][0]["angle"]==ui_angle_to_engine(90)
    assert "angle" not in profiles[axis][-1]
    assert [r.length for r in spec.fold_profile]==pytest.approx([17-t,100-t])
    assert [r.formed_length for r in spec.fold_profile]==[17,100]
    data=build_part_render_data(spec)
    assert data.metadata["outside_lengths"]==(17,100)
    assert data.metadata["assembly_placement"]=="unassigned"
    assert data.unfolded_topology.piece_id==key
    assert data.material.area==pytest.approx((117-2*t)*123.456)
    assert len(data.fold_guides)==1
    guide=data.fold_guides[0]
    assert guide.axis==axis.lower()
    assert guide.position==pytest.approx(17-t)
    assert guide.span_end-guide.span_start==pytest.approx(123.456)
    cumulative,folded=_phase6_profile_geometry(profiles[axis])
    assert cumulative==pytest.approx([0,17-t,117-2*t])
    assert abs(folded[1][0]-folded[0][0])<1e-9
    assert abs(folded[1][1]-folded[0][1])==pytest.approx(17-t)
    assert abs(folded[2][0]-folded[1][0])==pytest.approx(100-t)
    mesh=_phase6_folded_mesh_from_polygon(data.material,profiles["X"],profiles["Y"],fold_guides=data.fold_guides)
    assert len(mesh)>0
    path=tmp_path/f"{axis}-{t}.dxf"
    result=generate_part(spec,path)
    assert result.part_kind==key and not result.used_baseline
    doc=ezdxf.readfile(path)
    assert len(doc.modelspace().query('LINE[layer=="BEND"]'))==1
    assert verify_saved_part_render_data_dxf(data,path).ok

@pytest.mark.parametrize("value",[0,-1,nan,inf,17,True])
def test_invalid_thickness_rejects_before_geometry(value):
    ws,key,snapshot,profiles,spec=specimen()
    with pytest.raises(ValueError):
        build_custom_part_profiles({**snapshot,"t":value},key)

@pytest.mark.parametrize("axis",["X","Y"])
def test_anchored_feature_roundtrip_and_other_part_unchanged(tmp_path,axis):
    ws,key,snapshot,profiles,spec=specimen(axis)
    feature=CircleFeature(4,FeatureAnchor.TOP_RIGHT,Vec2(-10,-10))
    data=build_part_render_data(replace(spec,features=(feature,)))
    circles=[p for p in data.scene.primitives if type(p).__name__=="CirclePrimitive"]
    assert len(circles)==1
    maxx,maxy=data.material.bounds[2:]
    assert (circles[0].center.x,circles[0].center.y)==pytest.approx((maxx-10,maxy-10))
    before=deepcopy(profiles)
    ws.stash_profiles(key,profiles);ws.stash_features(key,[feature])
    path=project.write_project(tmp_path/"custom.p6fold",{"schema":project.PROJECT_SCHEMA,"snapshot":{"model":"金庫型","t":2,**ws.snapshot()}})
    loaded=project.read_project(path)["snapshot"]
    restored=Phase6DesignerWorkspace.from_snapshot(loaded)
    assert restored.custom_part(key)==ws.custom_part(key)
    second=custom_part_spec({**loaded,**restored.snapshot()},key,profiles=restored.profiles_for(key),features=restored.features_for(key))
    again=build_part_render_data(second)
    assert again.scene.primitives==data.scene.primitives
    assert profiles==before
    with pytest.raises(ValueError,match="outside"):
        build_part_render_data(replace(spec,features=(CircleFeature(40,FeatureAnchor.TOP_RIGHT,Vec2(0,0)),)))

def test_no_unknown_key_fallback_no_guessed_assembly_and_real_resolver():
    from phase6_manufacturing_contracts import ManufacturingResolveRequest,ManufacturingPartInput
    from phase6_manufacturing_service import resolve
    ws,key,snapshot,profiles,spec=specimen()
    data=build_part_render_data(spec)
    request=ManufacturingResolveRequest(input_snapshot=snapshot,settings={"t":2},
        canonical_part_keys=(key,),parts=(ManufacturingPartInput(part_key=key,
        render_data=data,part_spec=spec,x_profile=profiles["X"],y_profile=profiles["Y"]),))
    result=resolve(request)
    part=result.geometry.part(key)
    assert part.placement=="standalone"
    assert part.render_data is data
    assert ws.assembly_placements_snapshot()=={}
    from phase6_final_scene_projection import make_assembly_scene_render_data
    assert make_assembly_scene_render_data(assembly_parts=(part,)).assembly_parts==()
    from ae_engine.manufacturing_api import _resolved_physical_render_parts
    assert tuple(_resolved_physical_render_parts(result.geometry))[0][0]==key
    with pytest.raises(ValueError,match="metadata"):
        custom_part_spec({"t":2},key)
    with pytest.raises(ValueError):
        custom_part_spec(snapshot,key,profiles={"X":[{"len":25},{"len":100}],"Y":[]})

def test_real_gui_custom_manufacturing_editor_reload(tmp_path,monkeypatch):
    import tkinter as tk
    import tkinter.filedialog as fd
    import tkinter.messagebox as mb
    import gui
    import fold_designer_bridge as bridge
    errors=[]
    monkeypatch.setattr(mb,"showerror",lambda *a,**kw:errors.append(a))
    root=tk.Tk();root.withdraw()
    try:
        main=gui.BoxCalculatorGUI(root);app=main.open_original_fold_designer()
        ws=app.designer_workspace
        before=deepcopy(app._phase6_box_whd)
        a=ws.add_custom_part(display_name="X板",fold_axis="X",transverse_length=234.567,per_box_count=2)
        b=ws.add_custom_part(display_name="Y板",fold_axis="Y",transverse_length=345.678)
        for key in (a,b):
            app.activate_part(key)
            assert app.renderer.canvas.get_tk_widget().winfo_manager()
            assert app._custom_part_editor._custom_open_holes
            from phase6_manufacturing_adapter import build_scene_payload_for_app
            payload=build_scene_payload_for_app(app,key)
            data=main._query_fold_designer_render_data(key,payload)
            out=tmp_path/(key.replace(":","-")+".dxf")
            spec,ctx=main._fold_designer_part_spec_from_payload(key,payload)
            main._export_authoritative_part(spec,out,ctx)
            assert verify_saved_part_render_data_dxf(data,out).ok
            assert data.metadata["stable_id"]==key
            assert len(app._phase6_last_cutting_mesh)>0
        assert app._phase6_box_whd==before
        root.update()
        main._phase6_update_scheduler.flush_now()
        app._phase6_update_scheduler.flush_now()
        root.update()
        import time,json
        import phase6_manufacturing_service as service
        counts={"manufacturing":0,"build":0,"read":0,"render":0}
        receipts=[]
        def count(name,original):
            def wrapped(*args,**kw):
                counts[name]+=1
                return original(*args,**kw)
            return wrapped
        from ae_engine import manufacturing_api
        monkeypatch.setattr(manufacturing_api,"build_part_render_data",count("build",manufacturing_api.build_part_render_data))
        monkeypatch.setattr(service,"resolve",count("manufacturing",service.resolve))
        monkeypatch.setattr(ezdxf,"readfile",count("read",ezdxf.readfile))
        monkeypatch.setattr(app.renderer,"render",count("render",app.renderer.render))
        for field,value,geometry in (("display_name","Y改名",False),("per_box_count","2",False),
                                     ("transverse_length","456.789",True),("fold_axis","X",True),
                                     ("fold_axis","Y",True)):
            base=dict(counts);calc=app._phase6_update_scheduler._metrics["calculation_flushes"]
            started=time.perf_counter()
            app._custom_part_editor._custom_values[field].set(value)
            assert app._custom_part_editor._custom_apply()
            root.update()
            receipt={k:counts[k]-base[k] for k in counts}
            receipt.update(calculation=app._phase6_update_scheduler._metrics["calculation_flushes"]-calc,
                           field=field,wall=time.perf_counter()-started)
            assert receipt["read"]==0,receipt
            assert receipt["build"]<=1 and receipt["manufacturing"]<=1 and receipt["render"]<=1 and receipt["calculation"]<=1,receipt
            if not geometry:
                assert receipt["build"]==receipt["manufacturing"]==receipt["render"]==receipt["calculation"]==0,receipt
            assert main.workspace_controller.workspace_snapshot()["custom_parts"]["items"][b]["display_name"]==ws.custom_part(b)["display_name"]
            receipts.append(receipt)
        from pathlib import Path
        evidence=Path("work")
        if evidence.exists():
            (evidence/"1464-gui-stress.json").write_text(json.dumps(receipts,indent=2))
        spec,ctx=main._fold_designer_part_spec_from_payload(b,build_scene_payload_for_app(app,b))
        assert spec.fold_axis=="Y" and spec.transverse_length==456.789
        current_data=main._query_fold_designer_render_data(b,build_scene_payload_for_app(app,b))
        assert current_data.material.area==pytest.approx(113*456.789)
        assert app._phase6_box_whd==before
        app._custom_part_editor._custom_values["per_box_count"].set("2")
        assert app._custom_part_editor._custom_apply()
        editor=app._custom_part_editor._custom_open_holes()
        assert editor is not None and editor.winfo_exists()
        editor.destroy()
        path=tmp_path/"real-custom.p6fold";monkeypatch.setattr(fd,"asksaveasfilename",lambda **kw:str(path))
        assert app.save_project_file_as()
        loaded=project.read_project(path)["snapshot"]
        restored=Phase6DesignerWorkspace.from_snapshot(loaded)
        assert restored.custom_part(a)["per_box_count"]==2
        assert restored.custom_part(b)["per_box_count"]==2
        for key in (a,b):
            spec=custom_part_spec({**loaded,**restored.snapshot()},key,profiles=restored.profiles_for(key))
            assert build_part_render_data(spec).metadata["stable_id"]==key
        assert not errors,errors
    finally:
        root.destroy()

def test_unvisited_custom_request_has_real_profile_axes():
    from types import SimpleNamespace
    from phase6_manufacturing_adapter import _profile_inputs_for_part
    ws,key,snapshot,profiles,spec=specimen("Y")
    ws.active_part="box_body"
    app=SimpleNamespace(designer_workspace=ws,_phase6_input_snapshot=snapshot,_settings_values={})
    x,y=_profile_inputs_for_part(app,key)
    assert tuple(profiles["X"])==x and tuple(profiles["Y"])==y
    assert ws.profiles_for(key) is None

@pytest.mark.parametrize("mutation",["display_name","per_box_count","fold_axis","transverse_length","next_id","t","feature","presence","profile","head_feature"])
def test_custom_only_host_commit_never_accepts_cabinet_geometry_changes(mutation):
    from phase6_custom_parts import custom_part_only_change
    ws,key,snapshot,profiles,spec=specimen()
    ws.stash_profiles(key,profiles)
    source={"workspace":ws.snapshot(),"part_profiles":ws.snapshot()["part_profiles"],"t":2}
    new=deepcopy(source)
    item=new["workspace"]["custom_parts"]["items"][key]
    if mutation=="display_name": item[mutation]="改名"
    elif mutation=="per_box_count": item[mutation]=3
    elif mutation=="fold_axis": item[mutation]="Y"
    elif mutation=="transverse_length": item[mutation]=456
    elif mutation=="next_id": new["workspace"]["custom_parts"][mutation]=999
    elif mutation=="t": new["t"]=3
    elif mutation=="feature": new["workspace"]["part_features"][key]=["edited"]
    elif mutation=="profile":
        new["part_profiles"][key]["X"][0]["len"]=20
        new["workspace"]["part_profiles"][key]["X"][0]["len"]=20
    elif mutation=="head_feature": new["workspace"]["part_features"]["head"]=["edited"]
    else: new["workspace"]["existing_parts"].remove(key)
    assert custom_part_only_change(source,new)==(mutation in {"display_name","per_box_count","fold_axis","transverse_length","feature","profile"})
