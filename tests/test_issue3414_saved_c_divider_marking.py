"""Bounded saved C-divider manual ink: original stock, persistent owner and normal DXF."""
from copy import deepcopy
from hashlib import sha256
from collections import Counter
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.receiving_horizontal_divider_owner import OCCUPANCY
from tests.test_issue3414_saved_c_divider_source import KEY, actual_sources as primary_source_fixture
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


@pytest.fixture(scope="module")
def actual_sources(tmp_path_factory):
    # Close the source-generation Primary before a second native app claims Tk grab.
    generator = primary_source_fixture.__wrapped__(tmp_path_factory)
    try:
        return next(generator)
    finally:
        generator.close()


def test_c_common_modal_accepts_current_saved_owner(actual_sources):
    snapshot, _, geometry = actual_sources[0]
    owner = api.require_saved_receiving_c_divider_source(snapshot, geometry, KEY)
    receipt = api.open_selected_ordinary_marking_modal_source(snapshot, geometry, KEY)
    assert receipt.owner_id == owner.owner_id
    assert receipt.output_capability == 'verified_normal'
    assert not api.open_workspace_owner_marking_draft(snapshot, receipt).saved_marks


def _mark(receipt):
    p = receipt.context.render_data.material.representative_point()
    return api.create_physical_sheet_mark(receipt, (), tool='line', midpoint=Vec2(p.x,p.y), length=5, angle_deg=0)


def _saved_marked(snapshot, geometry, path):
    from ae_engine.operator_root_marking_store import apply_workspace_owner_marking_commit
    receipt = api.open_selected_ordinary_marking_modal_source(snapshot, geometry, KEY)
    draft = api.open_workspace_owner_marking_draft(snapshot, receipt)
    mark = _mark(receipt)
    update = api.prepare_workspace_owner_marking_commit(snapshot, draft, receipt, (mark,))
    source = deepcopy(snapshot)
    source[api.ROOT_MARKING_STORE_KEY] = apply_workspace_owner_marking_commit(snapshot, update, receipt)
    write_project(path, {'schema':PROJECT_SCHEMA, 'snapshot':source})
    return read_project(path)['snapshot'], receipt, draft, update, mark


def _check_dxf(path, expected):
    doc = ezdxf.readfile(path)
    assert doc.header['$INSUNITS'] == 4 and not doc.audit().errors
    assert Counter(e.dxf.layer for e in doc.modelspace()) == {'CUTTING':7,'BEND':3,'MARKING':expected}


def _raw(path, layers):
    from tests.test_issue3414_box_body_piece_marking_export import _raw as read
    return read(path,layers)


def _bytes(folder):
    return {p.name:(sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in folder.glob('*.dxf')}


def test_c_saved_ledger_selected_normal_export_and_atomic_drift(actual_sources, tmp_path):
    (s,_,g),(foreign,_,foreign_g) = actual_sources
    source, receipt, draft, update, mark = _saved_marked(s,g,tmp_path/'marked.p6fold')
    owner, current_g = api.resolve_saved_receiving_c_divider_source(source, KEY)
    assert owner.owner_id == receipt.owner_id
    current = api.open_selected_ordinary_marking_modal_source(source,current_g,KEY)
    assert api.open_workspace_owner_marking_draft(source,current).saved_marks == (mark,)
    assert api.project_operator_detached_root_marking_count(source)==0
    assert api.resolve_workspace_physical_root_owner(source,KEY) is None
    assert api.require_existing_normal_owner_marking_route(source, {'box_body':True}, ordinary=True)==(KEY,)
    assert api.require_existing_normal_owner_marking_route(source, {'door':True}, ordinary=True)==(KEY,)
    assert api.require_existing_normal_owner_marking_route(source, {'tail':True}, ordinary=True)==()
    mode=api.SAVED_C_PHYSICAL_EXPORT_MODE
    assert api.normalize_saved_c_selected_export_mode(source, {'box_body':True}, mode) is None
    assert api.normalize_saved_c_selected_export_mode(source, {'box_body':True}, 'ALL')=='ALL'
    with pytest.raises(ValueError,match='ROOT_MARKING_EXISTING_NORMAL_ROUTE_REQUIRED'):
        api.require_existing_normal_owner_marking_route(source, {'box_body':True}, ordinary=False)
    for value,flags in ((s,{'box_body':True}),(source,{'tail':True})):
        with pytest.raises(ValueError,match='C_DIVIDER_MARKING_SCOPE_UNSUPPORTED'):
            api.normalize_saved_c_selected_export_mode(value,flags,mode)
    # Use the actual full Primary inventory and existing normal selection route.
    flags={'box_body':True}
    before=api.save_selected_resolved_manufacturing_dxf(s,g,flags,tmp_path/'plain')
    folder=tmp_path/'marked'
    after=api.save_selected_resolved_manufacturing_dxf(source,g,flags,folder,read_current_owner_source=lambda:(source,g))
    assert set(after)==set(before) and len(after)>1
    _check_dxf(before[KEY],2); _check_dxf(after[KEY],3)
    for k in before:
        assert _raw(before[k],{'CUTTING','BEND','BLIND_HOLE'})==_raw(after[k],{'CUTTING','BEND','BLIND_HOLE'})
        base=_raw(before[k],{'MARKING'}); ink=_raw(after[k],{'MARKING'})
        assert ink[:len(base)]==base and len(ink)==len(base)+(k==KEY)
    # During actual staging, inject a different independently certified C source.
    old=_bytes(folder); changed=False
    def drift():
        nonlocal changed
        if any(folder.glob('.whd-dxf-stage-*/*.dxf')):
            changed=True
            return source,foreign_g
        return source,g
    with pytest.raises(ValueError,match='C_DIVIDER_SAVED_SOURCE_MISMATCH'):
        api.save_selected_resolved_manufacturing_dxf(source,g,flags,folder,read_current_owner_source=drift)
    assert changed and _bytes(folder)==old and not tuple(folder.glob('.whd-dxf-stage-*'))
    # Legacy unmarked stock still uses its normal route, without owner backfill.
    legacy=deepcopy(s); legacy['receiving_layout']['sets'][0]['bays'][0].pop(OCCUPANCY)
    path=write_project(tmp_path/'legacy.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':legacy})
    legacy=read_project(path)['snapshot']
    assert api.resolve_saved_c_marking_owner(legacy,KEY) is None
    with pytest.raises(ValueError,match='DURABLE_OWNER_REQUIRED'):
        api.open_selected_ordinary_marking_modal_source(legacy,g,KEY)
    plain=api.save_selected_resolved_manufacturing_dxf(legacy,g,flags,tmp_path/'legacy')
    _check_dxf(plain[KEY],2)
    assert _raw(plain[KEY],{'CUTTING','BEND','MARKING'})==_raw(before[KEY],{'CUTTING','BEND','MARKING'})
    print('normal full selected rows',len(before),'C DXF original 7/3/2 -> 7/3/3; drift during stage SHA/mtime unchanged',old,'legacy 7/3/2')


def test_c_native_select_draw_confirm_save_open_and_replacement(actual_sources,tmp_path,monkeypatch):
    import fold_designer_bridge as bridge
    from gui import BoxCalculatorGUI
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
    errors=[]
    for name in ('showinfo','showwarning'):
        monkeypatch.setattr(messagebox,name,lambda *a,**k:None)
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:errors.append(a))
    monkeypatch.setattr(messagebox,'askyesno',lambda *a,**k:True)
    source=write_project(tmp_path/'input.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':actual_sources[0][0]})
    root=tk.Tk(); root.geometry('1400x900+0+0')
    try:
        host=BoxCalculatorGUI(root)
        def load(path):
            host.load_phase6_project(path,open_designer=True); root.update()
            assert not errors,errors
        def save(name):
            path=tmp_path/(name+'.p6fold')
            monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
            assert host.save_phase6_project_as() and path.is_file()
            return path,read_project(path)['snapshot']
        def current():
            app=host.fold_designer_app
            geometry=app._phase6_resolve_manufacturing_geometry()
            return current_workspace_marking_source(app, host=host), geometry
        def export(name):
            s,g=current()
            return api.save_selected_resolved_manufacturing_dxf(s,g,{'box_body':True},tmp_path/name,read_current_owner_source=current)
        def edit(clock):
            app=host.fold_designer_app
            bridge._phase6_show_corner_data(app)
            bridge._phase6_select_corner_data_part(app,KEY)
            root.update()
            canvas=app.corner_data_canvas
            for tick in (clock,clock+50):
                canvas.event_generate('<ButtonPress-1>',x=80,y=100,time=tick)
                canvas.event_generate('<ButtonRelease-1>',x=80,y=100,time=tick)
            root.update()
            assert not errors,errors
            window=host.last_unified_hole_editor
            assert window.winfo_exists()
            place=window._manual_marking_place
            state=dict(zip(place.__code__.co_freevars,(c.cell_contents for c in place.__closure__)))['s']
            assert state.manual_marking_draft.context.part_key==KEY
            return window,state
        load(source)
        print('NATIVE loaded',flush=True)
        before=export('plain')
        print('NATIVE plain exported',flush=True)
        window,state=edit(1000)
        old=state.manual_marking_draft
        assert old.marking_only and old.owner_id
        assert Counter(p.layer for p in old.context.render_data.scene.primitives)=={'CUTTING':7,'BEND':3,'MARKING':2}
        centre=old.context.render_data.material.representative_point()
        state.manual_mark_length.set('5'); state.manual_mark_angle.set('0')
        window._manual_marking_controls[0].invoke()
        x,y=state.canvas_view.transform.world_to_canvas(Vec2(centre.x,centre.y))
        host.last_hole_editor_canvas.event_generate('<Button-1>',x=round(x),y=round(y))
        root.update()
        marks=tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        assert len(marks)==1
        _actual_editor_confirm(window);root.update()
        assert not errors,errors
        assert not window.winfo_exists()
        print('NATIVE confirmed',flush=True)
        marked_path,marked=save('marked')
        print('NATIVE saved',flush=True)
        assert api.read_workspace_marking_owner_record(marked,old.owner_id)['features']==marks
        load(marked_path)
        window,state=edit(2000)
        reopened=state.manual_marking_draft
        assert reopened.owner_id==old.owner_id
        assert tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))==marks
        _actual_editor_confirm(window); root.update()
        assert not errors,errors
        print('NATIVE reopened/confirmed',flush=True)
        after=export('marked_dxf')
        print('NATIVE marked exported',flush=True)
        _check_dxf(before[KEY],2);_check_dxf(after[KEY],3)
        assert _raw(after[KEY],{'CUTTING','BEND'})==_raw(before[KEY],{'CUTTING','BEND'})
        assert _raw(after[KEY],{'MARKING'})[:2]==_raw(before[KEY],{'MARKING'})
        # The real outer export button path, including the existing folder
        # transaction and byte-sealed publication. Grouping is never changed
        # behind the operator's back.
        from gui_modules.project.export_actions import export_selected_dxf
        host._refresh_receiving_dxf_group_preview()
        assert api.SAVED_C_PHYSICAL_EXPORT_MODE in host.receiving_dxf_group_combo.cget('values')
        host.receiving_dxf_group_mode_var.set(api.SAVED_C_PHYSICAL_EXPORT_MODE)
        for name in ('export_z_var','export_head_var','export_tail_var','export_door_var',
                     'export_base_plate_var','export_ib_var','export_ib_door_var'):
            getattr(host,name).set(name=='export_z_var')
        gui_folder=tmp_path/'gui_button_dxf';gui_folder.mkdir()
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(gui_folder))
        export_selected_dxf(host)
        assert not errors,errors
        assert len(tuple(gui_folder.glob('*.dxf')))==4
        _check_dxf(next(gui_folder.glob('*divider*.dxf')),3)
        print('real GUI export button 4 verified physical DXF',flush=True)
        alias_path,alias=save('alias')
        assert api.resolve_saved_c_marking_owner(alias,KEY)==old.owner_id
        # Real Main rapid remove / recreate of the same shape, without idle in between.
        old_snapshot,old_geometry=current()
        old_draft=api.open_workspace_owner_marking_draft(old_snapshot,reopened)
        update=api.prepare_workspace_owner_marking_commit(old_snapshot,old_draft,reopened,marks)
        host.remove_door_layout_height(0,0);host.remove_door_layout_height(0,0)
        assert tuple(host.get_door_layout_columns()[0][1])==(1600.,)
        host.door_layout_columns[0]['height_vars'][0].set('1100')
        assert host.commit_door_layout_height(0,0)
        with pytest.raises(ValueError,match='ROOT_MARKING_OWNER_STALE'):
            api.require_current_saved_c_marking_occupant(old_snapshot,host.workspace_controller.workspace_snapshot())
        rebuilt_path,rebuilt=save('rebuilt')
        assert api.resolve_saved_c_marking_owner(rebuilt,KEY)!=old.owner_id
        # Removing the grid also removes the inner-door dependency. Old
        # owner rejection must precede the missing dependency. Restore the
        # original inner-door configuration through the existing Bay API,
        # not by copying a receipt or replacing the occupant.
        load(rebuilt_path)
        s,g=current()
        with pytest.raises(ValueError,match='ROOT_MARKING_OWNER_STALE'):
            api.open_workspace_owner_marking_draft(s,reopened)
        with pytest.raises(ValueError,match='C_DIVIDER_SAVED_FRAME_DEPENDENCY_REQUIRED'):
            api.open_selected_ordinary_marking_modal_source(s,g,KEY)
        original_door=alias['receiving_layout']['sets'][0]['bays'][0]['door_state']
        rebuilt['receiving_layout']=api.update_receiving_bay(
            rebuilt['receiving_layout'],set_index=0,bay_index=0,door_state=original_door)
        rebuilt=api.project_receiving_bay_legacy_aliases(rebuilt,set_index=0,bay_index=0)
        restored_path=write_project(tmp_path/'rebuilt_with_frames.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':rebuilt})
        load(restored_path)
        s,g=current(); fresh=api.open_selected_ordinary_marking_modal_source(s,g,KEY)
        assert fresh.source_sha256==reopened.source_sha256 and fresh.owner_id!=reopened.owner_id
        with pytest.raises(ValueError,match='ROOT_MARKING_OWNER_STALE'):
            api.open_workspace_owner_marking_draft(s,reopened)
        with pytest.raises(ValueError,match='ROOT_MARKING_OWNER_STALE'):
            api.prepare_workspace_owner_marking_commit(s,old_draft,fresh,marks)
        with pytest.raises(ValueError,match='ROOT_MARKING_OWNER_STALE'):
            host.fold_designer_app.designer_workspace.commit_saved_c_divider_marking(update,read_current=lambda:(s,fresh))
        assert not api.open_workspace_owner_marking_draft(s,fresh).saved_marks
        assert api.read_workspace_marking_owner_record(s,old.owner_id)['features']==marks
        assert api.project_operator_detached_root_marking_count(s)==1
        print('native canvas line + Confirm + Save/Open/SaveAs; C original 7/3/2 -> 7/3/3; same stock new owner',old.owner_id,fresh.owner_id,'old record preserved but draft/receipt/update reject')
    finally:
        root.destroy()
