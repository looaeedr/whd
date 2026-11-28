"""Only an explicitly selected, byte/owner-bound saved C can donate ordinary ink."""
from copy import deepcopy
from hashlib import sha256
from collections import Counter
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.operator_root_marking_store import apply_workspace_owner_marking_commit
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3414_saved_c_divider_marking import actual_sources, _raw
from tests.test_issue3414_saved_c_divider_source import KEY
from tests.test_issue3414_receiving_horizontal_divider_owner import bay, edit, remove_door_row
from pathlib import Path
from tests.test_issue3415_primary_marking_menu_roundtrip import _actual_editor_confirm
from gui_modules.project.export_actions import export_selected_dxf


def saved(path, snapshot):
    write_project(path, {'schema': PROJECT_SCHEMA, 'snapshot': snapshot})
    return read_project(path)['snapshot']


def bind(path, snapshot=None):
    return dict(source_project_path=path, source_project_sha256=sha256(path.read_bytes()).hexdigest(),
                source_snapshot=read_project(path)['snapshot'] if snapshot is None else snapshot,
                source_part_key=KEY, resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry)


def confirm_source(snapshot, marks):
    _, g = api.resolve_saved_receiving_c_divider_source(snapshot, KEY)
    receipt = api.open_selected_ordinary_marking_modal_source(snapshot, g, KEY)
    draft = api.open_workspace_owner_marking_draft(snapshot, receipt)
    update = api.prepare_workspace_owner_marking_commit(snapshot, draft, receipt, marks)
    return {**snapshot, api.ROOT_MARKING_STORE_KEY: apply_workspace_owner_marking_commit(snapshot, update, receipt)}


@pytest.fixture(scope='module')
def donor(actual_sources, tmp_path_factory):
    s, _, g = actual_sources[0]
    receipt = api.open_selected_ordinary_marking_modal_source(s, g, KEY)
    p = receipt.context.render_data.material.representative_point()
    line = api.create_physical_sheet_mark(receipt, (), tool='line', midpoint=Vec2(p.x,p.y),length=5,angle_deg=0)
    group = api.create_physical_sheet_mark(receipt, (line,), tool='l', center=Vec2(p.x+15,p.y),arm_x=4,arm_y=6)
    path = tmp_path_factory.mktemp('c_donor')/'donor.p6fold'
    source = saved(path, confirm_source(s, (line,group)))
    return path, source, (line,group)


def test_public_c_source_lists_only_manual_marks(donor):
    path, source, marks = donor
    candidates = api.list_saved_endcap_marking_copy_candidates(bind(path))
    assert len(candidates)==2
    assert {r[1] for r in candidates}=={'line','l'}
    owner, g = api.resolve_saved_receiving_c_divider_source(source,KEY)
    receipt = api.open_selected_ordinary_marking_modal_source(source,g,KEY)
    assert receipt.owner_id == owner.owner_id
    assert Counter(p.layer for p in receipt.context.render_data.scene.primitives)=={'CUTTING':7,'BEND':3,'MARKING':2}
    assert api.open_workspace_owner_marking_draft(source,receipt).saved_marks==marks
    print('saved C donor 2 original joint marks excluded; only two authored choices',candidates)


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


@pytest.mark.parametrize('target_key,kind', [('door','l'),('base_plate','line')])
def test_c_saved_source_native_ordinary_copy_and_reopen(donor, target_key, kind, tmp_path, monkeypatch):
    from gui import Phase6PrimaryApplication
    from gui_modules.application.physical_part_hole_editor import current_workspace_marking_source
    from phase6_manufacturing_adapter import build_scene_payload_for_app

    donor_path, donor_snapshot, marks = donor
    source_path = tmp_path/'saved_donor.p6fold'
    source_path.write_bytes(donor_path.read_bytes())
    original_source = source_path.read_bytes()
    source = bind(source_path)
    choices = api.list_saved_endcap_marking_copy_candidates(source)
    choice = next(row for row in choices if row[1]==kind)
    source_mark = marks[0 if kind=='line' else 1]
    target_input = tmp_path/'initial.p6fold'
    target_input.write_bytes((Path(__file__).parent/'fixtures'/'vault_overlay_w400_t2_fw25.p6fold').read_bytes())
    failures=[]
    monkeypatch.setattr(messagebox,'showerror',lambda title,text,**kw:failures.append((title,text)))
    monkeypatch.setattr(messagebox,'showinfo',lambda *a,**k:None)
    root=tk.Tk(); root.geometry('1400x900+0+0')
    try:
        host=Phase6PrimaryApplication(root);app=host.fold_designer_app;menu=app.project_file_menu
        def load(path):
            monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(path))
            menu.invoke(0);root.update()
            assert host.project_controller.project_path==str(path) and not failures,failures
        def save(name):
            path=tmp_path/(name+'.p6fold')
            monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
            menu.invoke(2);root.update()
            assert path.is_file() and not failures,failures
            return path,read_project(path)['snapshot']
        def export(name):
            folder=tmp_path/name;folder.mkdir()
            for role in ('z','head','tail','door','base_plate','ib','ib_door'):
                getattr(host,f'export_{role}_var').set(role==target_key)
            monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(folder))
            export_selected_dxf(host);root.update()
            assert not failures,failures
            path,=folder.glob('*.dxf')
            doc=ezdxf.readfile(path)
            assert doc.header['$INSUNITS']==4 and not doc.audit().errors
            return path
        def live():
            return current_workspace_marking_source(app)
        load(target_input)
        target_path,target_snapshot=save('target')
        before=export('before')
        old_file=fingerprint(target_path); old_dxf=fingerprint(before)
        app.activate_part(target_key);root.update()
        modal=host.open_part_hole_editor(target_key);root.update()
        callback=modal._manual_marking_place
        state=dict(zip(callback.__code__.co_freevars,(c.cell_contents for c in callback.__closure__)))['s']
        opened=state.manual_marking_draft
        assert opened.output_capability=='verified_normal'
        geometry=api.selected_normal_marking_inventory(target_key,host._query_fold_designer_render_data(target_key,build_scene_payload_for_app(app,target_key)))
        target=dict(target_snapshot=target_snapshot,target_project_path=target_path,
                    target_project_sha256=old_file[0],target_part_key=target_key,
                    resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry,
                    target_live_snapshot=live(),target_live_geometry=geometry)
        def verify(source=source,key=choice[0],destination=target):
            return api.verify_saved_endcap_marking_copy(source_group_id=key,source=source,target=destination)
        chosen, current=verify()
        assert chosen==source_mark and current.source_sha256==opened.source_sha256
        # Normal source never consumes an arbitrary render callback for C.
        def forbidden(*args):
            raise AssertionError('caller render must not be used for saved C')
        assert verify(source={**source,'resolve_saved_geometry':forbidden})[0]==source_mark
        before_live=deepcopy(live())
        with pytest.raises(api.ManualCopyPlacementRejected):
            api.place_saved_endcap_marking_copy(source_group_id=choice[0],source=source,target=target,
                target_features=tuple(state.live_context.feature_list),target_position=Vec2(-100000,-100000))
        assert live()==before_live
        # Do not admit a different destination kind or quantity-version path.
        for forbidden_target in ({**target,'target_part_key':KEY}, {**target,'target_part_key':'head'},
                                 {**target,'target_version_id':'quantity-v1'}):
            with pytest.raises(ValueError,match='MANUAL_COPY_C_ORDINARY_TARGET_REQUIRED'):
                verify(destination=forbidden_target)
        if kind=='l':
            # Delete/recreate through the actual Bay owner transaction, not by
            # inventing a UUID. Explicitly confirm identical literal ink on the
            # new occupant, so rejection cannot be explained by missing ink.
            original_door=deepcopy(bay(donor_snapshot)['door_state'])
            removed=edit(donor_snapshot,remove_door_row(original_door))
            removed=api.project_receiving_bay_legacy_aliases(removed,set_index=0,bay_index=0)
            deleted_path=tmp_path/'deleted.p6fold';saved(deleted_path,removed)
            with pytest.raises(ValueError):
                api.list_saved_endcap_marking_copy_candidates(bind(deleted_path))
            recreated=edit(removed,original_door)
            recreated=api.project_receiving_bay_legacy_aliases(recreated,set_index=0,bay_index=0)
            rebuilt_path=tmp_path/'rebuilt.p6fold'; rebuilt=saved(rebuilt_path,recreated)
            assert api.resolve_saved_c_marking_owner(rebuilt,KEY)!=api.resolve_saved_c_marking_owner(donor_snapshot,KEY)
            with pytest.raises(ValueError,match='MANUAL_COPY_SOURCE_GROUP_MISSING'):
                api.list_saved_endcap_marking_copy_candidates(bind(rebuilt_path))
            rebuilt=saved(rebuilt_path,confirm_source(rebuilt,marks))
            original_receipt=api.open_selected_ordinary_marking_modal_source(donor_snapshot,api.resolve_saved_receiving_c_divider_source(donor_snapshot,KEY)[1],KEY)
            fresh_receipt=api.open_selected_ordinary_marking_modal_source(rebuilt,api.resolve_saved_receiving_c_divider_source(rebuilt,KEY)[1],KEY)
            assert original_receipt.source_sha256==fresh_receipt.source_sha256
            # Even when caller refreshes digest and snapshot for a different
            # owner, the previous picker selection cannot be replayed.
            new_binding=bind(rebuilt_path)
            with pytest.raises(ValueError,match='MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS'):
                verify(source=new_binding)
            assert {r[0] for r in choices}.isdisjoint(r[0] for r in api.list_saved_endcap_marking_copy_candidates(new_binding))
            source_path.write_bytes(rebuilt_path.read_bytes())
            rebound=bind(source_path)
            with pytest.raises(ValueError,match='MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS'):
                verify(source=rebound)
            new_key=next(r[0] for r in api.list_saved_endcap_marking_copy_candidates(rebound) if r[1]==kind)
            assert verify(source=rebound,key=new_key)[0]==source_mark
            source_path.write_bytes(original_source)
            # File selection itself is bound too, including an unchanged Save As.
            alias=tmp_path/'alias.p6fold';alias.write_bytes(original_source)
            assert api.resolve_saved_c_marking_owner(read_project(alias)['snapshot'],KEY)==original_receipt.owner_id
            with pytest.raises(ValueError,match='MANUAL_COPY_SOURCE_GROUP_AMBIGUOUS'):
                verify(source=bind(alias))
            # Wrong saved snapshot claim against the genuine file bytes.
            with pytest.raises(ValueError,match='MANUAL_COPY_SOURCE_SAVED_SNAPSHOT_MISMATCH'):
                verify(source={**source,'source_snapshot':rebuilt})
            assert live()==before_live and fingerprint(target_path)==old_file and fingerprint(before)==old_dxf
            print('deleted C rejected; identical stock/ink on replacement owner at same path rejects old selection; new selection works; Save As requires new selection; target bytes and mtime unchanged')
        # Existing GUI source picker, canvas placement and Confirm transaction.
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(source_path))
        monkeypatch.setattr(simpledialog,'askstring',lambda *a,**kw:'C 水平中隔')
        monkeypatch.setattr(simpledialog,'askinteger',lambda *a,**kw:choices.index(choice)+1)
        state.manual_mark_copy_button.invoke();root.update()
        assert '點選目標' in state.manual_mark_status.cget('text'),state.manual_mark_status.cget('text')
        point=opened.context.render_data.material.representative_point()
        x,y=state.canvas_view.transform.world_to_canvas(Vec2(point.x+25,point.y))
        host.last_hole_editor_canvas.event_generate('<Button-1>',x=round(x),y=round(y));root.update()
        copied,=tuple(f for f in state.live_context.feature_list if api.is_manual_mark(f))
        assert copied!=source_mark
        if kind=='l':
            assert api.group_parameters(copied)['group_id']!=api.group_parameters(source_mark)['group_id']
            assert {k:v for k,v in api.group_parameters(copied).items() if k!='group_id'}=={k:v for k,v in api.group_parameters(source_mark).items() if k!='group_id'}
        else:
            assert copied.source_params==source_mark.source_params
        # A file change after placement must stop real Confirm, not only pick.
        source_path.write_bytes(original_source+b'\n')
        _actual_editor_confirm(modal);root.update()
        assert modal.winfo_exists() and any('MANUAL_COPY_SOURCE_SAVED_SOURCE_CHANGED' in text for _,text in failures),failures
        assert fingerprint(target_path)==old_file and fingerprint(before)==old_dxf
        assert api.resolve_workspace_physical_root_owner(live(),target_key)==opened.owner_id
        assert live()==before_live
        print('native Confirm rejects file drift after placement; target ledger/project/DXF unchanged',target_key)
        failures.clear();source_path.write_bytes(original_source)
        _actual_editor_confirm(modal);root.update()
        assert not modal.winfo_exists() and not failures,failures
        final_path,final=save('copied')
        load(final_path)
        owner=api.resolve_workspace_physical_root_owner(final,target_key)
        assert owner and owner!=api.resolve_saved_c_marking_owner(donor_snapshot,KEY)
        assert api.read_workspace_marking_owner_record(final,owner)['features']==(copied,)
        assert set(final[api.ROOT_MARKING_STORE_KEY]['records'])=={owner}
        after=export('after')
        assert _raw(before,{'CUTTING','BEND','BLIND_HOLE'})==_raw(after,{'CUTTING','BEND','BLIND_HOLE'})
        original_ink=_raw(before,{'MARKING'}); copied_ink=_raw(after,{'MARKING'})
        assert copied_ink[:len(original_ink)]==original_ink
        assert len(copied_ink)-len(original_ink)==len(copied.layered_profiles)
        assert source_path.read_bytes()==original_source and donor_path.read_bytes()==original_source
        assert fingerprint(before)==old_dxf and fingerprint(target_path)==old_file
        print('native C ->',target_key,kind,'confirmed Save/Open, formal DXF stock unchanged, added manual entities',len(copied_ink)-len(original_ink))
    finally:
        root.destroy()


def test_c_donor_rejects_unbound_and_other_scopes(donor, tmp_path):
    from ae_engine.receiving_horizontal_divider_owner import OCCUPANCY
    from ae_engine.receiving_quantity_versions import QuantityModel
    path, source, marks = donor
    binding=bind(path)
    choice=api.list_saved_endcap_marking_copy_candidates(binding)[0][0]
    # No implicit donor selection or owner backfill for legacy or multiple Bays.
    legacy=deepcopy(source);bay(legacy).pop(OCCUPANCY)
    multi=deepcopy(source)
    multi['receiving_layout']=api.resize_receiving_operator_topology_with_removed_ids(
        multi['receiving_layout'],set_index=0,bay_count=2)[0]
    for name, snapshot in (('legacy',legacy),('multi_bay',multi)):
        other=tmp_path/(name+'.p6fold');reopened=saved(other,snapshot)
        before=fingerprint(other)
        with pytest.raises(ValueError,match='MANUAL_COPY_C_SOURCE_OWNER_UNRESOLVED'):
            api.select_saved_c_marking_copy_part(reopened)
        with pytest.raises(ValueError):
            api.list_saved_endcap_marking_copy_candidates(bind(other))
        assert fingerprint(other)==before
    with pytest.raises(ValueError,match='MANUAL_COPY_QUANTITY_VERSION_UNAVAILABLE'):
        api.list_saved_endcap_marking_copy_candidates({**binding,'source_version_id':'quantity-v1'})
    with pytest.raises(ValueError,match='MANUAL_COPY_EXPLICIT_ORDINARY_SOURCE_REQUIRED'):
        api.list_saved_endcap_marking_copy_candidates({**binding,'source_part_key':KEY.replace('HORIZONTAL','VERTICAL')})
    # Use real saved Vault stock; only an ordinary one-piece root is in scope.
    target_path=tmp_path/'ordinary.p6fold'
    target_path.write_bytes((Path(__file__).parent/'fixtures'/'vault_overlay_w400_t2_fw25.p6fold').read_bytes())
    target_snapshot=read_project(target_path)['snapshot']
    geometry=api.resolve_saved_ordinary_copy_geometry(target_snapshot,'door')
    model=QuantityModel.from_payload(target_snapshot['quantity']);model.add_version()
    versioned=saved(tmp_path/'versioned.p6fold',{**target_snapshot,'quantity':model.snapshot()})
    versioned_path=tmp_path/'versioned.p6fold'
    before=fingerprint(versioned_path)
    target=dict(target_snapshot=versioned,target_project_path=versioned_path,target_project_sha256=before[0],
                target_part_key='door',resolve_saved_geometry=api.resolve_saved_ordinary_copy_geometry,
                target_live_snapshot=versioned,target_live_geometry=geometry)
    with pytest.raises(ValueError,match='MANUAL_COPY_C_ORDINARY_TARGET_REQUIRED'):
        api.verify_saved_endcap_marking_copy(source_group_id=choice,source=binding,target=target)
    assert fingerprint(versioned_path)==before
    print('legacy unowned C, actual multi-Bay, other divider, source version and actual two-version destination rejected')
