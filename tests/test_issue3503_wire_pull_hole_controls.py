"""Native operator add/remove/resize transactions on an existing standard project."""
from dataclasses import replace
import os
import tkinter as tk
from tkinter import filedialog

import pytest

from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

pytestmark = [pytest.mark.requires_tk_display,
              pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')]


def _open(host, root, monkeypatch, path):
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(path))
    host.fold_designer_app.project_file_menu.invoke(0)
    root.update()
    return host.wire_pull_window


def _select_group(win, key):
    win.group_var.set(key)
    win.group_selector.event_generate('<<ComboboxSelected>>')


def _add(win, root, kind, face, xy):
    win.add_kind_var.set(kind)
    win.add_face_var.set(face)
    for axis, v in zip(('X','Y'), xy):
        win.position[axis].set(str(v))
    win.add_button.invoke(); root.update()


def _size(win, root, group, part, **values):
    _select_group(win, group)
    win.member_var.set(part)
    win.member_selector.event_generate('<<ComboboxSelected>>')
    for key, value in values.items():
        win.size_fields[key].set(str(value))
    win.size_button.invoke(); root.update()


def test_hole_group_controls_confirm_save_reload_cancel(tmp_path, monkeypatch):
    import gui
    spec = WirePullBoxSpec(637.,1200.,223.,3.,27.,34.,'flat','flat')
    hole = CircleFeature(4., FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400.,600.), source_type='MANUAL_TEST')
    mark = replace(hole, layer='MARKING', diameter=2., offset=Vec2(420.,620.))
    manual = (('box_body',(hole,mark)),)
    original = api.propose_wire_pull_holes(spec, manual=manual)
    initial = api.build_wire_pull_project_snapshot(spec, original)
    path = write_project(tmp_path/'operator.p6fold', {'schema':PROJECT_SCHEMA,'snapshot':initial})
    saved = path.read_bytes()
    saved_mtime = path.stat().st_mtime_ns
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root); root.update()
        win = _open(host,root,monkeypatch,path)
        assert win.window.winfo_viewable()
        win.window.geometry('850x590'); root.update()
        for button in (win.move_button, win.remove_button, win.add_button, win.size_button,
                       win.confirm_button, win.cancel_button, win.save_button, win.open_button):
            assert button.winfo_viewable() and button.winfo_width() >= button.winfo_reqwidth()
            assert button.winfo_rooty()+button.winfo_height() <= win.window.winfo_rooty()+win.window.winfo_height()
        seal = next(m for m in original.members if m.kind=='seal' and m.part_key=='box_body')
        fixed = next(m for m in original.members if m.kind=='fixed' and m.part_key=='box_body')
        anchor = next(m for m in original.members if m.kind=='anchor')
        # Use actual Engine world coordinates; GUI only collects operator input.
        x,y = seal.world[:2]
        _add(win,root,'封印孔','rear',(x,y-30))
        assert 'ADDITION_FACE_UNSUPPORTED' in win.status.get()
        assert win.proposal == original and path.read_bytes() == saved
        assert win.controller.committed_snapshot() == initial
        assert path.stat().st_mtime_ns == saved_mtime
        _add(win,root,'封印孔',seal.face_id,(x,y-30))
        assert not win.proposal.conflicts
        add = win.proposal.additions[-1]
        assert add.face_id == seal.face_id and add.kind == 'seal'
        assert len([m for m in win.proposal.members if m.group_id==add.group_id]) == 2
        _select_group(win,seal.group_id)
        win.remove_button.invoke(); root.update()
        assert not any(m.group_id==seal.group_id for m in win.proposal.members)
        _size(win,root,add.group_id,'box_body',diameter=12)
        _size(win,root,add.group_id,'lid',diameter=15)
        _size(win,root,fixed.group_id,'lid',slot_width=8,slot_length=12)
        _size(win,root,anchor.group_id,'box_body',diameter=14)
        assert not win.proposal.conflicts
        assert len(win.proposal.sizes)==4
        assert win.proposal.manual == manual
        assert win.controller.committed_snapshot()==initial and path.read_bytes()==saved
        # An inapplicable member and an invalid slot type/size must be rejected.
        before = win.proposal
        _size(win,root,anchor.group_id,'lid',diameter=15)
        assert 'MEMBER' in win.status.get() and win.proposal==before
        _size(win,root,fixed.group_id,'lid',diameter=6)
        assert 'SIZE_OVERRIDE_KIND_MISMATCH' in win.status.get() and win.proposal==before
        _size(win,root,fixed.group_id,'lid',slot_width=12,slot_length=8)
        assert 'SLOT_LENGTH_INVALID' in win.status.get() and win.proposal==before
        assert path.read_bytes()==saved
        # Cancel the whole batch; repeat and then confirm explicitly.
        win.cancel_button.invoke(); root.update()
        assert win.proposal==original and path.read_bytes()==saved
        assert path.stat().st_mtime_ns == saved_mtime
        # A new group must not replace a loaded manual hole or marking. Use
        # the actual rear-face transform (in the test oracle, not GUI code).
        rear = next(f for f in api.resolve_standard_cabinet_topology(spec).part('box_body').mounting_faces if f.face_id=='rear')
        for feature, error in ((hole,'EXISTING_CUTTING_OR_MATERIAL'), (mark,'EXISTING_MARKING_OR_BLIND_HOLE')):
            u,v=feature.offset.x,feature.offset.y
            p=tuple(o+(u-rear.flat_bounds[0])*a+(v-rear.flat_bounds[1])*b for o,a,b in zip(rear.world_origin,rear.u_direction,rear.v_direction))
            _add(win,root,'壁虎孔','rear',p[:2])
            assert any(error in c for c in win.proposal.conflicts)
            assert win.proposal.manual==manual
            win.confirm_button.invoke(); root.update()
            assert win.controller.committed_snapshot()==initial and path.read_bytes()==saved
            assert path.stat().st_mtime_ns == saved_mtime
            win.cancel_button.invoke(); root.update()
            assert win.proposal==original
        _add(win,root,'封印孔',seal.face_id,(x,y-30))
        add = win.proposal.additions[-1]
        _select_group(win,seal.group_id); win.remove_button.invoke(); root.update()
        _size(win,root,add.group_id,'box_body',diameter=12)
        _size(win,root,add.group_id,'lid',diameter=15)
        _size(win,root,fixed.group_id,'lid',slot_width=8,slot_length=12)
        _size(win,root,anchor.group_id,'box_body',diameter=14)
        # Include a new anchor and a fixed pair on each actual rail; one
        # fixed addition may conflict with cyclic slot alternation until both exist.
        _add(win,root,'壁虎孔','rear',(0.,0.))
        assert not win.proposal.conflicts
        anchor_add = win.proposal.additions[-1]
        for face in ('front_left_return','front_right_return'):
            rows = sorted((m for m in original.members if m.kind=='fixed' and m.part_key=='box_body' and m.face_id==face),key=lambda m:m.world[1])
            a,b=rows[:2]
            _add(win,root,'固定孔',face,(a.world[0],(a.world[1]+b.world[1])/2))
        assert not win.proposal.conflicts
        assert len([a for a in win.proposal.additions if a.kind=='fixed'])==2
        assert win.proposal.manual==manual
        win.confirm_button.invoke(); root.update()
        committed = win.controller.committed_snapshot()
        expected = win.proposal
        assert committed != initial and expected.manual==manual
        win.save_button.invoke(); root.update()
        assert read_project(path)['snapshot']==committed
        assert path.read_bytes()!=saved
        saved=path.read_bytes()
        saved_mtime=path.stat().st_mtime_ns
        # Remove an added single group, then cancel; no file write.
        _select_group(win,anchor_add.group_id); win.remove_button.invoke(); root.update()
        assert not any(m.group_id==anchor_add.group_id for m in win.proposal.members)
        win.cancel_button.invoke(); root.update()
        assert win.proposal==expected and path.read_bytes()==saved
        assert path.stat().st_mtime_ns==saved_mtime
    finally:
        root.destroy()
    root=tk.Tk()
    try:
        host=gui.Phase6PrimaryApplication(root); root.update()
        win=_open(host,root,monkeypatch,path)
        assert win.proposal==expected and win.controller.committed_snapshot()==committed
        assert win.proposal.manual==manual
        assert api.wire_pull_hole_member_size(win.proposal,add.group_id,'box_body').diameter==12
        assert api.wire_pull_hole_member_size(win.proposal,add.group_id,'lid').diameter==15
        assert api.wire_pull_hole_member_size(win.proposal,anchor.group_id,'box_body').diameter==14
        _select_group(win,fixed.group_id)
        win.member_var.set('lid'); win.member_selector.event_generate('<<ComboboxSelected>>')
        assert float(win.size_fields['slot_width'].get())==8
        assert float(win.size_fields['slot_length'].get())==12
        renders=dict(api.confirm_wire_pull_holes(spec,expected,manual=manual))
        assert dict(win.renders)==renders
        win.view3d_button.invoke(); root.update()
        assert win.physical and all(p.render_data==renders[p.part_key] for p in win.physical.parts)
        assert not win.physical.manufacturing_verified
        assert path.read_bytes()==saved
    finally:
        root.destroy()


_FACTORY_KEYS = ('fixed_pitch', 'seal_offset', 'anchor_break', 'anchor_near', 'anchor_far', 'anchor_extra')
_CUSTOM_VALUES = (450., 110., 1050., 110., 160., 1850.)


def _factory_source(legacy=False):
    spec = (WirePullBoxSpec(1003.,1004.,223.,2.,27.,34.,'flat','flat') if legacy else
            WirePullBoxSpec(1003.,1004.,223.,2.))
    factory = api.wire_pull_default_hole_options()
    custom = replace(factory, defaults=replace(factory.defaults, **dict(zip(_FACTORY_KEYS,_CUSTOM_VALUES))), opposite_diagonal=True)
    return spec, custom, replace(custom, defaults=factory.defaults)


def _assert_factory_fields(win):
    defaults = api.wire_pull_default_hole_options().defaults
    assert tuple(float(win.fields[k].get()) for k in _FACTORY_KEYS) == tuple(getattr(defaults,k) for k in _FACTORY_KEYS) == (500.,100.,1000.,100.,150.,1800.)


def test_factory_restore_new_draft(tmp_path, monkeypatch):
    import gui
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root); root.update()
        menu = host.fold_designer_app.project_file_menu
        menu.invoke(next(i for i in range(menu.index('end')+1) if menu.type(i)=='command' and menu.entrycget(i,'label')=='標準拉線箱'))
        root.update()
        win = host.wire_pull_window
        win.window.geometry('850x590'); root.update()
        _assert_factory_fields(win)
        spec, custom, factory = _factory_source()
        for key in ('width','height','depth','thickness','left_return_material_mm','right_return_material_mm'):
            win.fields[key].set(str(getattr(spec,key)))
        for key,value in zip(_FACTORY_KEYS,_CUSTOM_VALUES):
            win.fields[key].set(str(value))
        win.flags['fixed'].set(False); win.flags['seal'].set(False); win.flags['opposite_diagonal'].set(True)
        source, options, edits = win._source()
        assert win.reset_defaults_button.winfo_viewable()
        assert win.reset_defaults_button.winfo_width() >= win.reset_defaults_button.winfo_reqwidth()
        assert win.reset_defaults_button.winfo_rooty()+win.reset_defaults_button.winfo_height() <= win.window.winfo_rooty()+win.window.winfo_height()
        win.reset_defaults_button.invoke(); root.update()
        _assert_factory_fields(win)
        assert win._source() == (source,replace(options,defaults=factory.defaults),edits)
        assert win.proposal is None and not win.renders and win.physical is None
        assert win.controller.committed_snapshot() is None and win.controller.project_path is None
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:pytest.fail('unconfirmed reset reached export dialog'))
        win.export_button.invoke(); assert '儲存' in win.status.get()
        win.preview_button.invoke(); root.update()
        assert win.proposal == api.propose_wire_pull_holes(source,replace(options,defaults=factory.defaults),**edits)
        assert win.controller.committed_snapshot() is None and not list(tmp_path.iterdir())
        print('NEW: six distances restored; dimensions/switches unchanged; no commit, file, or export')
    finally:
        root.destroy()


@pytest.mark.parametrize("legacy",[False,True])
def test_factory_restore_reopen_cancel_confirm_save(tmp_path, monkeypatch,legacy):
    import gui
    import ezdxf
    spec, custom, factory = _factory_source(legacy)
    anchors = [m for m in api.propose_wire_pull_holes(spec,custom).members if m.kind=='anchor']
    hole = CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(400.,600.),source_type='MANUAL_TEST')
    edits = dict(manual=(('box_body',(hole,)),), sizes=(api.make_wire_pull_hole_size_override(anchors[0].group_id,'box_body',diameter=14),),
                 additions=(api.make_wire_pull_hole_addition('added:anchor:reset-test','anchor','rear',(0.,0.)),), removed=(anchors[1].group_id,),
                 overrides=((anchors[2].group_id,(anchors[2].world[0]+20.,anchors[2].world[1])),))
    original = api.propose_wire_pull_holes(spec,custom,**edits)
    expected = api.propose_wire_pull_holes(spec,factory,**edits)
    assert not original.conflicts and not expected.conflicts and original.members != expected.members
    initial = api.build_wire_pull_project_snapshot(spec,original)
    path = write_project(tmp_path/'custom.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':initial})
    before = (path.read_bytes(),path.stat().st_mtime_ns)
    out = tmp_path/'out'; out.mkdir()
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root); root.update()
        win = _open(host,root,monkeypatch,path)
        assert win.proposal == original
        saved_source = win._source(); witness = win._saved_export
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:pytest.fail('uncommitted reset reached export dialog'))
        for do_confirm in (False,True):
            win.reset_defaults_button.invoke(); root.update()
            _assert_factory_fields(win)
            assert win._source() == (saved_source[0],factory,saved_source[2])
            assert win.controller.committed_snapshot() == initial and win._saved_export is witness
            assert win.proposal is None and not win.renders and win.physical is None
            assert (path.read_bytes(),path.stat().st_mtime_ns) == before
            win.export_button.invoke(); assert '儲存' in win.status.get() and not list(out.iterdir())
            win.preview_button.invoke(); root.update()
            assert win.proposal == expected
            assert win.renders == api.confirm_wire_pull_holes(spec,expected,manual=expected.manual)
            assert win.controller.committed_snapshot() == initial
            if not do_confirm:
                win.cancel_button.invoke(); root.update()
                assert win.proposal == original and win._source() == saved_source
                assert win.controller.committed_snapshot() == initial
                assert (path.read_bytes(),path.stat().st_mtime_ns) == before
                print('CANCEL: custom six values, all manual edits, original bytes/mtime restored')
            else:
                win.confirm_button.invoke(); root.update()
                committed = win.controller.committed_snapshot()
                assert committed == api.build_wire_pull_project_snapshot(spec,expected)
                assert (path.read_bytes(),path.stat().st_mtime_ns) == before
                win.export_button.invoke(); assert '儲存' in win.status.get() and not list(out.iterdir())
                win.save_button.invoke(); root.update()
                assert read_project(path)['snapshot'] == committed
                assert path.read_bytes() != before[0]
                print('CONFIRM: Engine proposal matched; old-file export blocked before save')
    finally:
        root.destroy()
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root); root.update()
        win = _open(host,root,monkeypatch,path)
        _assert_factory_fields(win)
        assert win.proposal == expected and win.controller.committed_snapshot() == committed
        assert win.proposal.manual == original.manual and win.proposal.options.opposite_diagonal
        for key in ('overrides','additions','removed','sizes'):
            assert getattr(win.proposal,key) == getattr(original,key)
        assert api.wire_pull_hole_member_size(win.proposal,anchors[0].group_id,'box_body').diameter == 14
        from tests.test_issue3503_wire_pull_gui_export import _existing_real_files
        from ae_engine import manufacturing_export
        _existing_real_files(out)
        old = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in out.iterdir()}
        if legacy:
            def forbidden(*args,**kwargs): pytest.fail('withdrawn source reached picker or stage')
            monkeypatch.setattr(filedialog,'askdirectory',forbidden)
            monkeypatch.setattr(manufacturing_export,'_save_resolved_rows_atomic',forbidden)
            win.export_button.invoke(); root.update()
            assert 'WIRE_PULL_FLAT_ENDCAP_WITHDRAWN' in win.status.get()
            assert {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in out.iterdir()}==old
        else:
            from tkinter import messagebox
            monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(out))
            monkeypatch.setattr(messagebox,'askyesno',lambda **kw:True)
            win.export_button.invoke(); root.update()
            assert '4' in win.status.get(),win.status.get()
            assert {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in out.iterdir()}!=old
            for key,render in win.renders:
                assert api.verify_saved_part_render_data_dxf(render,out/(key+'.dxf')).ok
        assert tuple(len(r.fold_guides) for _,r in win.renders)==((4,0,0,0) if legacy else (4,4,4,0))
        for target in out.iterdir():
            doc=ezdxf.readfile(target); assert doc.header['$INSUNITS']==4 and not doc.audit().errors
        output = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in out.iterdir()}
        path.write_bytes(path.read_bytes()+b'\n')
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:pytest.fail('stale source reached export dialog'))
        win.export_button.invoke(); assert 'SAVED_SOURCE_CHANGED' in win.status.get()
        assert {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in out.iterdir()} == output
        print('REOPEN: six defaults and five edit sources preserved; Ø14, four mm DXF verified; withdrawn and stale sources rejected')
    finally:
        root.destroy()


def test_factory_restore_conflict_preserves_committed_source(tmp_path, monkeypatch):
    import gui
    spec, custom, factory = _factory_source()
    member = next(m for m in api.propose_wire_pull_holes(spec,factory).members if m.kind=='anchor')
    manual = (('box_body',(CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,member.feature.offset,source_type='MANUAL_TEST'),)),)
    original = api.propose_wire_pull_holes(spec,custom,manual=manual)
    expected = api.propose_wire_pull_holes(spec,factory,manual=manual)
    assert not original.conflicts and any('EXISTING_CUTTING_OR_MATERIAL' in c for c in expected.conflicts)
    initial = api.build_wire_pull_project_snapshot(spec,original)
    path = write_project(tmp_path/'conflict.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':initial})
    before = (path.read_bytes(),path.stat().st_mtime_ns)
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root); root.update()
        win = _open(host,root,monkeypatch,path)
        win.reset_defaults_button.invoke(); root.update()
        win.confirm_button.invoke(); root.update()
        assert win.proposal == expected and 'WIRE_PULL_HOLE_CONFLICT' in win.status.get()
        assert win.controller.committed_snapshot() == initial and not win.renders
        assert (path.read_bytes(),path.stat().st_mtime_ns) == before
        win.cancel_button.invoke(); root.update()
        assert win.proposal == original and win.controller.committed_snapshot() == initial
        assert (path.read_bytes(),path.stat().st_mtime_ns) == before
        print('CONFLICT: restored distances hit manual CUTTING; Engine rejects confirm; cancel preserves source')
    finally:
        root.destroy()
