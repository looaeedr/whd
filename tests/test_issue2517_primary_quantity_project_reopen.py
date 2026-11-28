from collections import Counter
from pathlib import Path
import hashlib
import tkinter as tk
import ezdxf
import pytest
from ae_engine import QuantityModel, manufacturing_api as api
from ae_engine.composed_panel_dxf import _actual_signature
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, Vec2
from gui import Phase6PrimaryApplication
from gui_modules.project import export_actions as gui
from phase6_manufacturing_adapter import build_manufacturing_request, build_scene_payload_for_app, operator_finished_dimensions_for_app
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
import fold_designer_bridge as bridge
from gui_modules.application import fold_designer_composition_receiving as receiving
from gui_modules import project_actions

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests'/'fixtures'

def full_sig(doc, stock=True):
    return tuple(sorted(repr(_actual_signature(e)) for e in doc.modelspace() if stock or e.dxf.layer!='STOCK'))

def docs(folder, flag):
    rows={}
    for path in sorted(folder.glob('*.dxf')):
        doc=ezdxf.readfile(path)
        assert doc.units==4 and not doc.audit().errors
        layers=Counter(e.dxf.layer for e in doc.modelspace())
        assert set(layers)<={'STOCK','CUTTING','BEND','MARKING','BLIND_HOLE','CHECK'}
        assert layers['CUTTING'] and layers['BEND']
        circles=tuple(sorted((e.dxf.layer,round(e.dxf.radius,6)) for e in doc.modelspace().query('CIRCLE')))
        stock=list(doc.modelspace().query('LWPOLYLINE[layer=="STOCK"]'))
        for e in stock:
            pts=list(e.get_points('xy')); assert len(pts)==5 and tuple(pts[0])==tuple(pts[-1]); assert len(set(map(tuple,pts)))==4
        rows[path.name]=(full_sig(doc),full_sig(doc,False),dict(layers),circles)
    assert len(rows)==4,rows.keys()
    return rows

def req(app):
    return build_manufacturing_request(app,scene_payload_builder=lambda k:build_scene_payload_for_app(app,k),render_data_provider=app._scene_query_callback,part_spec_provider=app._part_spec_query_callback,finished_dimensions_provider=lambda k=None:operator_finished_dimensions_for_app(app,k))

@pytest.mark.parametrize('fixture',['vault_overlay_w400_t2_fw25.p6fold','issue1503_legacy_receiving_without_nfb_base.p6fold'])
def test_primary_quantity_save_reopen_export(fixture,tmp_path,monkeypatch):
    errors=[]; infos=[]
    monkeypatch.setattr(gui.messagebox,'showerror',lambda *a,**kw:errors.append(a))
    monkeypatch.setattr(gui.messagebox,'showwarning',lambda *a,**kw:errors.append(a))
    monkeypatch.setattr(gui.messagebox,'showinfo',lambda *a,**kw:infos.append(a))
    monkeypatch.setattr(gui.messagebox,'askyesno',lambda *a,**kw:True)
    def open_root(path):
        root=tk.Tk(); host=Phase6PrimaryApplication(root); app=host.fold_designer_app
        monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **_:str(path))
        app.project_file_menu.invoke(0); root.update()
        assert not errors, errors
        assert Path(host.project_controller.project_path)==path
        assert host.fold_designer_app is app
        current=host.fold_designer_app
        print(f"OPEN {path.name} same_designer={current is app} mode={current.designer_workspace.active_mode} stock={current.output_draw_stock_var.get()} versions={current.designer_workspace.quantity_model.snapshot() if current.designer_workspace.quantity_model else None}",flush=True)
        return root,host,current
    root,host,app=open_root(FIXTURES/fixture)
    try:
        if app.designer_workspace.active_mode!='quantity':
            assert receiving._switch_mode(bridge._phase6_composition(app),vars(bridge),'quantity'),errors
            root.update()
        assert app.designer_workspace.active_mode=='quantity'
        controls=app.receiving_mode_controls.quantity_editor
        model=app.designer_workspace.quantity_model
        first=model.selected_version_id
        controls.count_var.set('2'); assert controls.commit_count()
        controls.add(); second=model.selected_version_id
        controls.count_var.set('3'); assert controls.commit_count()
        assert first!=second
        # Open real modeless editor; use its captured detached features and normal commit.
        captured=[]; original=host._open_unified_hole_editor
        def capture(*a,**kw):
            captured.append((a,kw));return original(*a,**kw)
        monkeypatch.setattr(host,'_open_unified_hole_editor',capture)
        for vid,role,diam,x in ((first,'head',8,10),(first,'tail',10,-12),(second,'head',12,20),(second,'tail',14,-22)):
            controls.ports['select'](vid)
            controls.ports['holes'](role);root.update()
            kw=captured[-1][1]
            kw['feature_list_override'][:]=[CircleFeature(diameter=diam,anchor=FeatureAnchor.PANEL_CENTER,offset=Vec2(x,0))]
            kw['sync_callback']();root.update()
        controls.ports['select'](second);root.update()
        for child in root.winfo_children():
            if isinstance(child,tk.Toplevel) and child is not app.root:child.destroy()
        saved=tmp_path/'versions.p6fold'
        if not app.output_draw_stock_var.get():app.output_draw_stock_check.invoke()
        root.update()
        monkeypatch.setattr(gui.filedialog,'asksaveasfilename',lambda **_:str(saved))
        app.project_file_menu.invoke(2);root.update()
        assert saved.is_file() and not errors,errors
        actual_saved=read_project(saved)['snapshot']
        original_versions=model.snapshot()
        assert actual_saved["settings"]["draw_stock"] is True
        assert actual_saved['quantity']==original_versions
        print(f'{fixture} saved quantities={[(v["version_id"],v["piece_count"]) for v in original_versions["versions"]]} saved stock={actual_saved.get("settings",{}).get("draw_stock")} path={saved}',flush=True)
    finally:root.destroy()
    # fresh Primary root, no bound callback reuse
    root,host,app=open_root(saved)
    try:
        assert app.designer_workspace.quantity_model.snapshot()==original_versions
        assert app.output_draw_stock_var.get() is True
        assert host.settings_service.snapshot()["draw_stock"] is True
        assert app.receiving_mode_controls.quantity_editor.versions.selection() == (original_versions["selected_version_id"],)
        saved_sha = hashlib.sha256(saved.read_bytes()).hexdigest()
        for name,flag in app.output_export_vars.items():flag.set(name in {'head','tail'})
        reference=None
        audit={}
        for idx,flag in enumerate((True,False)):
            if bool(app.output_draw_stock_var.get())!=flag:app.output_draw_stock_check.invoke()
            root.update();host._flush_phase6_authoritative_state()
            target=tmp_path/f'gui-{idx}';target.mkdir()
            monkeypatch.setattr(gui.filedialog,'askdirectory',lambda **_:str(target))
            app.output_export_button.invoke();root.update();assert not errors,errors
            actual=docs(target,flag)
            # Distinct version and role circles must survive grouping and reload.
            assert Counter(r for row in actual.values() for l,r in row[3] if l=='CUTTING') >= Counter([4.,5.,6.,7.])
            r=req(app); snapshot=app._phase6_input_snapshot; ws=app.designer_workspace.snapshot()
            versions=api.build_operator_quantity_manufacturing_requests(r,ws)
            assert [(v,c) for v,c,_ in versions]==[(first,2),(second,3)]
            for vid,count,version in versions:
                for part in version.parts:
                    if part.part_key not in ('head','tail'):continue
                    print(f'{fixture} arm={idx} {vid} Q={count} {part.part_key} family={part.part_spec.model_name} relief={len(part.part_spec.resolved_assembly_relief_cuts)} features={part.part_spec.holes}',flush=True)
            direct=tmp_path/f'engine-{idx}';direct.mkdir()
            flags=gui._selected_export_flags(host,host._phase6_current_existing_parts(),host._has_any_indicator_box())
            api.stage_quantity_operator_export(r,ws,flags,direct,operator_snapshot=snapshot)
            engine=docs(direct,flag)
            assert sorted(v[0] for v in actual.values())==sorted(v[0] for v in engine.values())
            shape=sorted(v[1] for v in actual.values())
            if reference is not None:assert reference==shape
            reference=shape
            audit[str(idx)]={n:{'layers':v[2],'circles':v[3],'nonstock_sha256':hashlib.sha256(repr(v[1]).encode()).hexdigest()} for n,v in actual.items()}
            print(f'{fixture} arm={idx} stock={flag} GUI+Engine identical {audit[str(idx)]}',flush=True)
        assert hashlib.sha256(saved.read_bytes()).hexdigest() == saved_sha
        # Negative: public Quantity export rejects request/source mismatch and leaves existing files intact.
        dst=tmp_path/'gui-1';before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.iterdir()}
        import copy
        drift=copy.deepcopy(snapshot);drift['quantity']['versions'][0]['piece_count']+=1
        with pytest.raises(ValueError,match='QUANTITY_OPERATOR_EXPORT_REQUEST_SOURCE_MISMATCH'):
            api.stage_quantity_operator_export(r,ws,flags,dst,operator_snapshot=drift)
        assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.iterdir()}==before
        print(f'{fixture} version drift refused; {len(before)} existing SHA256 unchanged',flush=True)
    finally:root.destroy()

@pytest.mark.parametrize('fixture',['vault_overlay_w400_t2_fw25.p6fold','issue1503_legacy_receiving_without_nfb_base.p6fold'])
def test_primary_reopen_replaces_old_quantity_and_stock(fixture,tmp_path,monkeypatch):
    """Alternate real saved files on one Primary: absent/empty, one, two versions."""
    errors=[]
    monkeypatch.setattr(gui.messagebox,'showerror',lambda *a,**kw:errors.append(a))
    monkeypatch.setattr(gui.messagebox,'showwarning',lambda *a,**kw:errors.append(a))
    monkeypatch.setattr(gui.messagebox,'showinfo',lambda *a,**kw:None)
    monkeypatch.setattr(gui.messagebox,'askyesno',lambda *a,**kw:True)
    root=tk.Tk();host=Phase6PrimaryApplication(root);app=host.fold_designer_app
    owner=app.designer_workspace
    def open_file(path):
        monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **_:str(path))
        app.project_file_menu.invoke(0);root.update()
        assert not errors,errors
        assert Path(host.project_controller.project_path)==path
        assert host.fold_designer_app is app and app.designer_workspace is owner
    def save_file(name):
        path=tmp_path/name
        monkeypatch.setattr(gui.filedialog,'asksaveasfilename',lambda **_:str(path))
        app.project_file_menu.invoke(2);root.update()
        assert not errors and path.is_file(),errors
        return path,read_project(path)['snapshot']
    def flag(value):
        if app.output_draw_stock_var.get()!=value:
            app.output_draw_stock_check.invoke()
        root.update();host._flush_phase6_authoritative_state()
        assert app.output_draw_stock_var.get()==value
    def verify(snapshot):
        expected=snapshot.get('quantity')
        assert owner.active_mode==snapshot['active_mode']
        assert (owner.quantity_model.snapshot() if owner.quantity_model else None)==expected
        assert app._settings_values['draw_stock']==snapshot['settings']['draw_stock']
        assert host.settings_service.snapshot()['draw_stock']==snapshot['settings']['draw_stock']
        assert app.output_draw_stock_var.get()==snapshot['settings']['draw_stock']
        if expected:
            assert app.receiving_mode_controls.quantity_editor.versions.selection()==(expected['selected_version_id'],)
    try:
        open_file(FIXTURES/fixture)
        flag(False)
        empty,empty_snapshot=save_file('empty.p6fold')
        if owner.active_mode!='quantity':
            assert receiving._switch_mode(bridge._phase6_composition(app),vars(bridge),'quantity'),errors
            root.update()
        controls=app.receiving_mode_controls.quantity_editor
        controls.count_var.set('4');assert controls.commit_count()
        single,single_snapshot=save_file('single.p6fold')
        controls.add();controls.count_var.set('3');assert controls.commit_count()
        flag(True)
        multi,multi_snapshot=save_file('multi.p6fold')
        paths=[empty,single,multi]
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        for path,snapshot in ((empty,empty_snapshot),(multi,multi_snapshot),(single,single_snapshot),(multi,multi_snapshot)):
            open_file(path);verify(snapshot)
        # A malformed next file cannot replace the active owner or existing file.
        bad=tmp_path/'invalid.p6fold';bad.write_text('{')
        monkeypatch.setattr(gui.filedialog,'askopenfilename',lambda **_:str(bad))
        app.project_file_menu.invoke(0);root.update()
        assert errors and Path(host.project_controller.project_path)==multi
        verify(multi_snapshot)
        assert hashes=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        print(f'{fixture}: empty/one/multi + reverse flags + malformed Open preserve owner and files',flush=True)
    finally:root.destroy()


def test_primary_main_host_open_syncs_existing_root_quantity_and_stock(tmp_path,monkeypatch):
    """The Main-host helper syncs an open Primary root without reopening it."""
    errors=[]
    monkeypatch.setattr(project_actions.messagebox,'showerror',lambda *a,**kw:errors.append(a))
    root=tk.Tk();host=Phase6PrimaryApplication(root);app=host.fold_designer_app
    owner=app.designer_workspace
    try:
        # Leave a distinct, dirty multi-version Quantity and STOCK state in
        # the already-running root Designer.
        if owner.active_mode!='quantity':
            assert receiving._switch_mode(bridge._phase6_composition(app),vars(bridge),'quantity'),errors
            root.update()
        controls=app.receiving_mode_controls.quantity_editor
        controls.count_var.set('2');assert controls.commit_count()
        controls.add();controls.count_var.set('3');assert controls.commit_count()
        if app.output_draw_stock_var.get():app.output_draw_stock_check.invoke()
        root.update()
        stale=owner.quantity_model.snapshot()

        # Open a saved Quantity project with different versions and Settings
        # through the existing Main-host helper used with Primary already open.
        incoming=read_project(FIXTURES/'vault_overlay_w400_t2_fw25.p6fold')['snapshot']
        incoming['active_mode']='quantity'
        incoming['quantity']=QuantityModel().snapshot()
        incoming['settings']['draw_stock']=True
        target=write_project(tmp_path/'main-host-open.p6fold',{
            'schema':PROJECT_SCHEMA,'snapshot':incoming,
        })
        assert incoming['quantity']!=stale
        monkeypatch.setattr(project_actions.filedialog,'askopenfilename',lambda **_:str(target))
        result=host.open_phase6_project()
        root.update()

        assert result==str(target) and not errors,errors
        assert host.fold_designer_app is app and app.designer_workspace is owner
        assert owner.quantity_model.snapshot()==incoming['quantity']
        assert app.output_draw_stock_var.get() is True
        assert host.settings_service.snapshot()['draw_stock'] is True
    finally:
        root.destroy()
