"""Bounded ordinary saved donor -> certified C, native copy transaction."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import read_project
from tests.test_issue3414_saved_c_divider_marking import actual_sources, _raw, _check_dxf
from tests.test_issue3414_saved_c_divider_source import KEY
from tests.test_issue3414_saved_c_copy_source import fingerprint, saved
from tests.test_issue3414_receiving_horizontal_divider_owner import bay, edit, remove_door_row
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm


@pytest.fixture(scope='module')
def ordinary_donors(tmp_path_factory):
    from gui import Phase6PrimaryApplication
    mp=pytest.MonkeyPatch(); errors=[]
    for name in ('showinfo','showwarning'):
        mp.setattr(messagebox,name,lambda *a,**k:None)
    mp.setattr(messagebox,'showerror',lambda *a,**k:errors.append(a))
    mp.setattr(messagebox,'askyesno',lambda *a,**k:True)
    folder=tmp_path_factory.mktemp('ordinary_donors')
    root=tk.Tk();root.geometry('1400x900+0+0')
    try:
        host=Phase6PrimaryApplication(root);app=host.fold_designer_app
        source=folder/'initial.p6fold'
        source.write_bytes((Path(__file__).parent/'fixtures'/'vault_overlay_w400_t2_fw25.p6fold').read_bytes())
        mp.setattr(filedialog,'askopenfilename',lambda **kw:str(source))
        app.project_file_menu.invoke(0);root.update()
        path=folder/'ordinary.p6fold'
        mp.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
        app.project_file_menu.invoke(2);root.update()
        assert path.is_file() and not errors,errors
        rows={}
        for key in ('door','base_plate'):
            app.activate_part(key);root.update()
            modal=host.open_part_hole_editor(key);root.update()
            callback=modal._manual_marking_place
            state=dict(zip(callback.__code__.co_freevars,(c.cell_contents for c in callback.__closure__)))['s']
            receipt=state.manual_marking_draft
            assert receipt.output_capability=='verified_normal'
            p=receipt.context.render_data.material.representative_point()
            state.manual_mark_length.set('5');state.manual_mark_angle.set('0')
            modal._manual_marking_controls[0].invoke()
            x,y=state.canvas_view.transform.world_to_canvas(Vec2(p.x,p.y))
            host.last_hole_editor_canvas.event_generate('<Button-1>',x=round(x),y=round(y));root.update()
            mark,=tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
            _actual_editor_confirm(modal);root.update()
            assert not modal.winfo_exists() and not errors,errors
            donor=folder/(key+'.p6fold')
            mp.setattr(filedialog,'asksaveasfilename',lambda **kw:str(donor))
            app.project_file_menu.invoke(2);root.update()
            ss=read_project(donor)['snapshot']
            owner=api.resolve_workspace_physical_root_owner(ss,key)
            assert owner and api.read_workspace_marking_owner_record(ss,owner)['features']==(mark,)
            rows[key]=(donor,ss,mark)
        return rows
    finally:
        root.destroy();mp.undo()


def source_args(row,key):
    path,snapshot,_=row
    return dict(source_project_path=path,source_project_sha256=fingerprint(path)[0],source_snapshot=snapshot,
                source_part_key=key,resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry)


def target_args(path,snapshot,geometry,**kw):
    return dict(target_project_path=path,target_project_sha256=fingerprint(path)[0],target_snapshot=snapshot,
                target_part_key=KEY,target_live_snapshot=snapshot,target_live_geometry=geometry,
                resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry,**kw)


def test_ordinary_to_c_engine_owner_bound(actual_sources,ordinary_donors,tmp_path):
    s,_,g=actual_sources[0]
    path=tmp_path/'target.p6fold';s=saved(path,s)
    opened=api.open_selected_ordinary_marking_modal_source(s,g,KEY)
    source=source_args(ordinary_donors['door'],'door')
    choice,=api.list_saved_endcap_marking_copy_groups(source)
    target=target_args(path,s,g,target_opened_receipt=opened)
    mark,receipt=api.verify_saved_endcap_marking_copy(source_group_id=choice,source=source,target=target)
    assert mark==ordinary_donors['door'][2] and receipt.owner_id==opened.owner_id


@pytest.mark.parametrize('source_key,label',[('door','門板'),('base_plate','底板')])
def test_native_ordinary_to_c(actual_sources,ordinary_donors,source_key,label,tmp_path,monkeypatch):
    import fold_designer_bridge as bridge
    from gui import BoxCalculatorGUI
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
    failures=[]
    for name in ('showinfo','showwarning'):
        monkeypatch.setattr(messagebox,name,lambda *a,**k:None)
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:failures.append(a))
    monkeypatch.setattr(messagebox,'askyesno',lambda *a,**k:True)
    source_path,_,source_mark=ordinary_donors[source_key]
    donor=tmp_path/'donor.p6fold';donor.write_bytes(source_path.read_bytes());original=donor.read_bytes()
    initial=tmp_path/'input.p6fold';saved(initial,actual_sources[0][0])
    root=tk.Tk();root.geometry('1400x900+0+0')
    try:
        host=BoxCalculatorGUI(root)
        def load(path):
            host.load_phase6_project(path,open_designer=True);root.update()
            assert not failures,failures
        def save(name):
            path=tmp_path/(name+'.p6fold')
            monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
            assert host.save_phase6_project_as() and path.is_file()
            return path,read_project(path)['snapshot']
        def current():
            app=host.fold_designer_app
            return current_workspace_marking_source(app,host=host),app._phase6_resolve_manufacturing_geometry()
        def export(name):
            s,g=current()
            return api.save_selected_resolved_manufacturing_dxf(s,g,{'box_body':True},tmp_path/name,read_current_owner_source=current)[KEY]
        load(initial);target_path,target_snapshot=save('target')
        before=export('plain');_check_dxf(before,2)
        old_file=fingerprint(target_path);old_dxf=fingerprint(Path(before))
        app=host.fold_designer_app
        bridge._phase6_show_corner_data(app);bridge._phase6_select_corner_data_part(app,KEY);root.update()
        canvas=app.corner_data_canvas
        for tick in (1000,1050):
            canvas.event_generate('<ButtonPress-1>',x=80,y=100,time=tick)
            canvas.event_generate('<ButtonRelease-1>',x=80,y=100,time=tick)
        root.update();assert not failures,failures
        modal=host.last_unified_hole_editor
        hole_window=modal
        hole_window._saved_c_marking_open_button.invoke();root.update()
        modal=host.last_unified_hole_editor
        assert not failures, failures
        assert modal is not hole_window and not hole_window.winfo_exists()
        callback=modal._manual_marking_place
        state=dict(zip(callback.__code__.co_freevars,(c.cell_contents for c in callback.__closure__)))['s']
        opened=state.manual_marking_draft
        assert opened.context.part_key==KEY and opened.owner_id
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(donor))
        monkeypatch.setattr(simpledialog,'askstring',lambda *a,**kw:label)
        state.manual_mark_copy_button.invoke();root.update()
        assert '點選目標' in state.manual_mark_status.cget('text'),state.manual_mark_status.cget('text')
        p=opened.context.render_data.material.representative_point()
        x,y=state.canvas_view.transform.world_to_canvas(Vec2(p.x+25,p.y))
        host.last_hole_editor_canvas.event_generate('<Button-1>',x=round(x),y=round(y));root.update()
        copied,=tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        assert copied!=source_mark and copied.source_params==source_mark.source_params
        donor.write_bytes(original+b'\n')
        _actual_editor_confirm(modal);root.update()
        assert modal.winfo_exists() and any('MANUAL_COPY_SOURCE_SAVED_SOURCE_CHANGED' in str(e) for e in failures),failures
        assert fingerprint(target_path)==old_file and fingerprint(Path(before))==old_dxf
        failures.clear();donor.write_bytes(original)
        target_bytes=target_path.read_bytes();target_path.write_bytes(target_bytes+b'\n');drift=fingerprint(target_path)
        _actual_editor_confirm(modal);root.update()
        assert modal.winfo_exists() and any('MANUAL_COPY_TARGET_SAVED_SOURCE_CHANGED' in str(e) for e in failures),failures
        assert fingerprint(target_path)==drift and fingerprint(Path(before))==old_dxf
        assert api.read_workspace_marking_owner_record(current()[0],opened.owner_id) is None
        failures.clear();target_path.write_bytes(target_bytes)
        _actual_editor_confirm(modal);root.update()
        assert not modal.winfo_exists() and not failures,failures
        path,final=save('copied');load(path)
        assert api.resolve_saved_c_marking_owner(final,KEY)==opened.owner_id
        assert api.read_workspace_marking_owner_record(final,opened.owner_id)['features']==(copied,)
        after=export('copied_dxf');_check_dxf(after,3)
        single=tmp_path/'selected_c.dxf'
        assert api.save_confirmed_workspace_owner_marking_dxf(KEY,single,read_current=current)
        _check_dxf(single,3)
        assert _raw(single,{'CUTTING','BEND','MARKING'})==_raw(after,{'CUTTING','BEND','MARKING'})
        assert _raw(before,{'CUTTING','BEND'})==_raw(after,{'CUTTING','BEND'})
        assert _raw(before,{'MARKING'})==_raw(after,{'MARKING'})[:2]
        assert fingerprint(Path(before))==old_dxf
        print(f'{source_key} -> C native copy/Confirm/Save/Open; 7/3/2 -> 7/3/3; late source/target changes rejected; old DXF {old_dxf}',flush=True)
    finally:
        root.destroy()


def test_c_destination_replacement_and_scope(actual_sources,ordinary_donors,tmp_path):
    from ae_engine.receiving_horizontal_divider_owner import OCCUPANCY
    s,_,g=actual_sources[0]
    path=tmp_path/'target.p6fold';s=saved(path,s)
    opened=api.open_selected_ordinary_marking_modal_source(s,g,KEY)
    source=source_args(ordinary_donors['door'],'door')
    choice,=api.list_saved_endcap_marking_copy_groups(source)
    def verify(target, donor=source):
        return api.verify_saved_endcap_marking_copy(source_group_id=choice,source=donor,target=target)
    target=target_args(path,s,g,target_opened_receipt=opened)
    before=api.save_selected_resolved_manufacturing_dxf(s,g,{'box_body':True},tmp_path/'before')[KEY]
    old_dxf=fingerprint(Path(before));old_project=fingerprint(path)
    for invalid in ({**source,'source_part_key':'head'}, {**source,'source_version_id':'quantity-v1'}):
        with pytest.raises(ValueError,match='MANUAL_COPY_C_ORDINARY_SOURCE_REQUIRED'):
            verify(target,invalid)
    from ae_engine.receiving_quantity_versions import QuantityModel
    versioned=deepcopy(source['source_snapshot'])
    model=QuantityModel.from_payload(versioned['quantity']);model.add_version()
    versioned['quantity']=model.snapshot()
    vp=tmp_path/'versioned.p6fold';versioned=saved(vp,versioned)
    with pytest.raises(ValueError,match='MANUAL_COPY_C_ORDINARY_SOURCE_REQUIRED'):
        verify(target,source_args((vp,versioned,None),'door'))
    with pytest.raises(ValueError,match='MANUAL_COPY_QUANTITY_VERSION_UNAVAILABLE'):
        verify({**target,'target_version_id':'quantity-v1'})
    with pytest.raises(ValueError,match='MANUAL_COPY_EXPLICIT_ORDINARY_TARGET_REQUIRED'):
        verify({**target,'target_part_key':KEY.replace('HORIZONTAL','VERTICAL')})
    with pytest.raises(ValueError,match='MANUAL_COPY_TARGET_EDITOR_SESSION_STALE'):
        verify({**target,'target_opened_receipt':None})
    with pytest.raises(ValueError,match='C_DIVIDER_SAVED_SOURCE_MISMATCH'):
        verify({**target,'target_live_geometry':actual_sources[1][2]})
    with pytest.raises(api.ManualCopyPlacementRejected):
        api.place_saved_endcap_marking_copy(source_group_id=choice,source=source,target=target,
            target_features=(),target_position=Vec2(-100000,-100000))
    legacy=deepcopy(s);bay(legacy).pop(OCCUPANCY)
    legacy_path=tmp_path/'legacy.p6fold';legacy=saved(legacy_path,legacy)
    with pytest.raises(ValueError):
        verify(target_args(legacy_path,legacy,g,target_opened_receipt=opened))
    multi=deepcopy(s)
    multi['receiving_layout']=api.resize_receiving_operator_topology_with_removed_ids(
        multi['receiving_layout'],set_index=0,bay_count=2)[0]
    multi_path=tmp_path/'multi.p6fold';multi=saved(multi_path,multi)
    with pytest.raises(ValueError):
        verify(target_args(multi_path,multi,g,target_opened_receipt=opened))
    assert fingerprint(path)==old_project and fingerprint(Path(before))==old_dxf
    original_door=deepcopy(bay(s)['door_state'])
    deleted=edit(s,remove_door_row(original_door))
    rebuilt=edit(deleted,original_door)
    rebuilt=api.project_receiving_bay_legacy_aliases(rebuilt,set_index=0,bay_index=0)
    # Replace actual bytes at the same path and rebind the saved snapshot.
    rebuilt=saved(path,rebuilt)
    _,rg=api.resolve_saved_receiving_c_divider_source(rebuilt,KEY)
    fresh=api.open_selected_ordinary_marking_modal_source(rebuilt,rg,KEY)
    assert fresh.owner_id!=opened.owner_id and fresh.source_sha256==opened.source_sha256
    rebound=target_args(path,rebuilt,rg,target_opened_receipt=opened)
    replacement_bytes=fingerprint(path)
    with pytest.raises(ValueError,match='MANUAL_COPY_TARGET_EDITOR_SESSION_STALE'):
        verify(rebound)
    assert verify({**rebound,'target_opened_receipt':fresh})[1].owner_id==fresh.owner_id
    assert fingerprint(path)==replacement_bytes and fingerprint(Path(before))==old_dxf
    print('C old receipt rejected on same-path same-seal new occupant; new receipt works; old DXF unchanged',flush=True)
