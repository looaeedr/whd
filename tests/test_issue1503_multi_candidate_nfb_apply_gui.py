# -*- coding: utf-8 -*-
"""Isolated R5-2600 localX GUI UAT for PR #1986.
Only creates in-memory Tk UI, never saves projects or touches formal X.
"""
import sys, traceback, tkinter as tk
from tkinter import ttk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def walk(root):
    pending=[root]
    while pending:
        x=pending.pop()
        yield x
        try: pending.extend(reversed(x.winfo_children()))
        except tk.TclError: pass

def buttons(root,label):
    return [w for w in walk(root) if isinstance(w,(ttk.Button,tk.Button))
            and str(w.cget('text')) == label]

def state_frame(root):
    for w in walk(root):
        if hasattr(w,'_receiving_inner_switch_state') and w.winfo_exists():
            return w, w._receiving_inner_switch_state
    raise AssertionError('NFB physical row frame not mounted')

def pump(root):
    root.update_idletasks()
    root.update()

def add(root,frame,state,layer):
    row=state['rows'][layer]
    # Fresh candidate NFB tab may now have a transient default 2P400.
    # Reuse that exact original CSV identity instead of duplicating slot 0.
    if row['assigned'].size()==1 and str(row['assigned'].get(0))=='2P400':
        return
    available=row['available']
    assert available.size() >= 1, 'missing available numeric CSV list, layer=' + str(layer)
    available.selection_clear(0,tk.END)
    choice = next((i for i in range(available.size())
                   if '2P400' in str(available.get(i))), None)
    assert choice is not None, 'complete CSV NFB 2P400 missing: ' + str(available.get(0,tk.END))
    available.selection_set(choice)
    available.activate(choice)
    plus=buttons(row['section'],'＋加入')
    assert len(plus)==1, 'plus buttons '+str(len(plus))
    plus[0].invoke()
    pump(root)
    assert row['assigned'].size() >= 1, 'NFB not added to layer '+str(layer)
    print('ADDED',layer+1,available.get(choice), 'ASSIGNED',row['assigned'].size(), flush=True)

def select_two(root,frame,state):
    radio=[x for x in walk(frame) if isinstance(x,ttk.Radiobutton)
           and str(x.cget('text'))=='2' and str(x.cget('value'))=='2']
    assert radio, 'missing 2-layer radio'
    radio[0].invoke()
    pump(root)
    assert state['layers'].get()==2
    assert state['nfb_physical_layers'].get()==2

def check_heights(state,first='330',second='830'):
    vals=tuple(round(float(v.get())) for v in state['layer_heights_mm'])
    assert vals==(int(first),int(second)), f'wrong default heights {vals}'
    print('HEIGHTS',vals, flush=True)


def test_real_multi_candidate_nfb_only_activates_after_explicit_bay_apply():
    root=None
    try:
        import gui
        import fold_designer_bridge as bridge
        root=tk.Tk()
        root.withdraw()
        box=gui.BoxCalculatorGUI(root)
        box.baseline_var.set('受電箱')
        pump(root)
        designer=box.open_original_fold_designer()
        pump(root)
        print('DESIGNER',type(designer).__name__, 'MODE', designer.designer_workspace.active_mode, flush=True)
        settings=bridge._phase6_open_receiving_multi_settings(designer)
        pump(root)
        assert settings._receiving_multi_apply(0), 'failed to select first multi Bay'
        pump(root)
        listing=settings._receiving_multi_setting_list
        listing.selection_clear(0,tk.END)
        listing.selection_set(1)
        listing.event_generate('<<ListboxSelect>>')
        pump(root)
        edit=buttons(settings._receiving_multi_settings_host,'編輯')
        assert len(edit)==1, 'missing real multi inner edit button'
        edit[0].invoke()
        pump(root)
        editor=getattr(box,'last_unified_hole_editor',None)
        assert editor is not None and editor.winfo_exists(),'native hole editor not opened'
        tabs=editor._receiving_config_tabs
        baseline_pending=tuple(editor._receiving_pending_features())
        assert len(baseline_pending)==1, 'fresh Bay must open with one current CSV hole'
        assert tabs.tab(0,'text').strip()=='開孔編輯' and tabs.tab(1,'text').strip()=='受電箱'
        print('EDITOR_TABS',tabs.tab(0,'text'),tabs.tab(1,'text'), flush=True)
        tabs.select(1)
        pump(root)
        modal,state=state_frame(editor)
        check_heights(state)
        add(root,modal,state,0)
        select_two(root,modal,state)
        add(root,modal,state,1)
        check_heights(state,'300','830')
        assert len(buttons(modal,'取消'))==1
        buttons(modal,'取消')[0].invoke()
        pump(root)
        assert tabs.index(tabs.select())==0,'cancel not returned to main'
        assert tuple(editor._receiving_pending_features())==baseline_pending, (
            'cancel must restore original one-NFB physical baseline without new holes'
        )
        assert getattr(editor,'_receiving_staged_config',None) is None, 'cancel staged NFB settings'
        print('TAB_CANCEL_ROLLBACK_PASS',flush=True)
        tabs.select(1)
        pump(root)
        modal,state=state_frame(editor)
        check_heights(state)
        add(root,modal,state,0)
        select_two(root,modal,state)
        add(root,modal,state,1)
        check_heights(state,'300','830')
        confirm=buttons(modal,'確定')
        assert len(confirm)==1,'missing tab 確定'
        confirm[0].invoke()
        pump(root)
        warning=state['warning'].get()
        assert tabs.index(tabs.select())==0,'tab 確定 did not return to main, warning='+warning
        pending=editor._receiving_pending_features()
        assert len(pending)==2,'tab 確定 did not bring 2 holes to main, '+str(len(pending))+', warning='+warning
        assert all(f.source_type=='NFB_CSV_SOURCE' for f in pending)
        staged=getattr(editor,'_receiving_staged_config',None)
        assert staged is not None and staged['layer_heights_mm']==[300,830]
        print('TAB_CONFIRM_NATIVE_HOLES_PASS',len(pending),flush=True)
        from ae_engine.cabinet_types import policy
        part=policy.derive_inner_door_panels(designer._phase6_input_snapshot)[0].stable_id
        assert len(designer.designer_workspace.features_for(part))==1, ('tab confirm must retain existing initial one-NFB physical source')
        print('NO_PREMATURE_PHYSICAL_WRITE_PASS',flush=True)
        # Native Confirm All is the transaction boundary, not this tab's 確定.
        main_confirm=buttons(editor,'確定全部')
        assert main_confirm, 'missing final native 確定全部 button'
        main_confirm[0].invoke()
        pump(root)
        assert not editor.winfo_exists(),'native editor failed to close on final commit'
        from ae_engine.receiving_inner_door_candidates import normalize_inner_candidates
        library=normalize_inner_candidates(designer._phase6_input_snapshot.get('receiving_inner_door_candidates'))
        assert len(library['versions'])==1,'multi final confirm did not create candidate version'
        version=library['versions'][0]
        config=version['config']
        assert len(config['features'][part])==2,'multi candidate missing two typed NFB holes'
        assert config['layer_heights_mm']==[300,830]
        physical=designer.designer_workspace.features_for(part)
        assert len(physical)==1, 'multi candidate unexpectedly modified existing one-NFB physical source'
        print('MULTI_CONFIRM_ALL_CANDIDATE_PASS',version['id'],len(config['features'][part]),flush=True)
        # Version X must not create a physical NFB before Apply.
        from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
        active=designer._phase6_input_snapshot['receiving_layout']
        bay=active['sets'][0]['bays'][0]
        assert bay.get('nfb_config_submitted') is True
        assert bay['nfb_config']['layer_count']==1
        adapter=ReceivingSetBayAdapter(active)
        applied=adapter.apply_inner_door_candidate_to_bays(config,0,(0,),version_id=version['id'])
        assert applied==(0,)
        physical_bay=adapter.layout['sets'][0]['bays'][0]
        print('MULTI_APPLIED_BAY_NFB',physical_bay.get('nfb_config_submitted'),
              physical_bay.get('nfb_config'),flush=True)
        assert physical_bay.get('nfb_config_submitted') is True
        assert physical_bay['nfb_config']['layer_count']==2
        assert [r['layer_index'] for r in physical_bay['nfb_config']['holes']]==[0,1]
        assert all(r['manual_x_state']=='UNVERIFIED_BASIS' for r in physical_bay['nfb_config']['holes'])
        print('MULTI_APPLIED_CSV_PHYSICAL_OWNER_PASS',flush=True)
        from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
        from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
        from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot as source_base
        physical_snapshot=project_receiving_bay_legacy_aliases({
            **designer._phase6_input_snapshot,"receiving_layout":adapter.layout,
            "receiving_base_plate":source_base()["receiving_base_plate"],
        },set_index=0,bay_index=0)
        assert physical_snapshot["nfb_config_submitted"] is True
        source_scene=bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        expanded=expand_receiving_nfb_layer_parts(physical_snapshot,source_scene.assembly_parts)
        assert [p.part_key for p in expanded if p.part_key.startswith("base_plate:")] == [
            "base_plate:nfb_layer:0","base_plate:nfb_layer:1"
        ],[p.part_key for p in expanded]
        print('MULTI_APPLIED_TWO_REAL_2D3D_BASES_PASS',flush=True)
        from ae_engine.receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
        from ae_engine.receiving_fixed_plate_formed_skins import build_receiving_formed_fixing_plate_skins
        from ae_engine.receiving_fixed_plate_side_contact import derive_receiving_ear_side_contact_from_formed_skin
        owners=resolve_receiving_tier_ear_mating_xy(physical_snapshot)
        assert len(owners)==4
        formed=[build_receiving_formed_fixing_plate_skins(physical_snapshot,ear.ear_id) for ear in owners]
        assert len({f.part_id for f in formed})==4
        contacts=[derive_receiving_ear_side_contact_from_formed_skin(f) for f in formed]
        assert len(contacts)==4
        assert {c.side_piece_id for c in contacts}=={"box_body:left_side","box_body:right_side"}
        assert all(len(c.world_surface_boundary)==4 for c in contacts)
        print('MULTI_FOUR_REAL_3D_EAR_CONTACTS_PASS',flush=True)

        print('PR1993_MULTI_CANDIDATE_APPLY_PASS',flush=True)
    except Exception as exc:
        print('PR1986_REAL_TK_UAT_FAIL',type(exc).__name__,str(exc),flush=True)
        traceback.print_exc()
        sys.exit(1)
    finally:
        if root is not None:
            try: root.destroy()
            except Exception: pass
