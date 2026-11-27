"""Native saved-project DXF command, with real Engine staging/reopen."""
import json
import os
from hashlib import sha256
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from phase6_project_file import read_project

pytestmark = [pytest.mark.requires_tk_display,
              pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')]


def _open_standard(root):
    import gui
    host = gui.Phase6PrimaryApplication(root)
    root.update()
    menu = host.fold_designer_app.project_file_menu
    menu.invoke(next(i for i in range(menu.index('end')+1)
                     if menu.type(i) == 'command' and menu.entrycget(i,'label') == '標準拉線箱'))
    root.update()
    return host, host.wire_pull_window


def _save_and_reopen(root, host, win, monkeypatch, path, width):
    for key, value in dict(width=width,height=1200,depth=223,thickness=3,
                           left_return_material_mm=27,right_return_material_mm=34).items():
        win.fields[key].set(str(value))
    win.confirm_button.invoke()
    monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(path))
    win.save_button.invoke()
    assert path.exists()
    win.window.destroy(); root.update()
    monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(path))
    host.fold_designer_app.project_file_menu.invoke(0)
    root.update()
    assert host.wire_pull_window.window.winfo_viewable()
    return host.wire_pull_window


def _files(folder):
    return {p.name:(sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in folder.iterdir() if p.is_file()}


def test_gui_export_confirm_save_close_reopen_and_four_dxf(tmp_path,monkeypatch):
    root=tk.Tk()
    try:
        host,win=_open_standard(root)
        path=tmp_path/'wire.p6fold'; out=tmp_path/'output'; out.mkdir()
        dialogs=[]
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw: dialogs.append(kw) or str(out))
        win.export_button.invoke()
        assert not dialogs and not list(out.iterdir())
        assert '儲存' in win.status.get()
        win=_save_and_reopen(root,host,win,monkeypatch,path,1801)
        win.window.geometry('850x590'); root.update()
        assert win.export_button.winfo_viewable()
        assert win.export_button.winfo_rooty()+win.export_button.winfo_height() <= win.window.winfo_rooty()+win.window.winfo_height()
        before=sha256(path.read_bytes()).hexdigest()
        win.export_button.invoke(); root.update()
        assert len(dialogs)==1 and '4' in win.status.get()
        proposal,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
        assert len([m for m in proposal.members if m.kind=='anchor'])==6
        assert set(p.name for p in out.iterdir())=={key+'.dxf' for key,_ in renders}
        for key,render in renders:
            target=out/(key+'.dxf')
            doc=ezdxf.readfile(target)
            assert doc.header['$INSUNITS']==4 and not doc.audit().errors
            assert api.verify_saved_part_render_data_dxf(render,target).ok
            print('GUI REOPEN',key,sha256(target.read_bytes()).hexdigest(),len(doc.modelspace()))
        assert sha256(path.read_bytes()).hexdigest()==before
        old=_files(out)
        # Cancellation at folder and overwrite selection is non-mutating.
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:'')
        win.export_button.invoke(); assert _files(out)==old
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(out))
        monkeypatch.setattr(messagebox,'askyesno',lambda **kw:False)
        win.export_button.invoke(); assert _files(out)==old
        # Unsaved field and confirmed-but-unsaved source are both blocked before dialog.
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:pytest.fail('dirty source reached folder dialog'))
        original_x=win.position['X'].get(); win.position['X'].set('42')
        win.export_button.invoke(); assert '儲存' in win.status.get()
        win.position['X'].set(original_x)
        win.fields['width'].set('1800')
        win.export_button.invoke(); assert '儲存' in win.status.get()
        win.confirm_button.invoke()
        win.export_button.invoke(); assert '儲存' in win.status.get()
        assert _files(out)==old
    finally:
        root.destroy()


def test_gui_export_drift_wrong_board_and_reopen_failure_preserve_output(tmp_path,monkeypatch):
    from ae_engine import dxf_serialization
    root=tk.Tk()
    try:
        host,win=_open_standard(root)
        path=tmp_path/'wire.p6fold'; out=tmp_path/'output'; out.mkdir()
        win=_save_and_reopen(root,host,win,monkeypatch,path,637)
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(out))
        win.export_button.invoke()
        old=_files(out); assert len(old)==4
        original_bytes=path.read_bytes()
        monkeypatch.setattr(messagebox,'askyesno',lambda **kw:True)
        # A changed file must never be implicitly re-authorized by inspecting it again.
        path.write_bytes(original_bytes+b'\n')
        win.export_button.invoke(); assert 'SAVED_SOURCE_CHANGED' in win.status.get()
        assert _files(out)==old
        path.write_bytes(original_bytes)
        def change_during_dialog(**kw):
            win.flags['seal'].set(False)
            return str(out)
        monkeypatch.setattr(filedialog,'askdirectory',change_during_dialog)
        win.export_button.invoke(); assert _files(out)==old and '儲存' in win.status.get()
        win.cancel_button.invoke()
        # Wrong physical identity in the saved file, including a bad load attempt.
        raw=json.loads(original_bytes); raw['snapshot']['wire_pull_standard']['identity']['holes'][0][3]='rear'
        path.write_text(json.dumps(raw),encoding='utf-8')
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:str(out))
        win.export_button.invoke(); assert _files(out)==old and 'PHYSICAL_IDENTITY_CHANGED' in win.status.get()
        win.open_button.invoke(); assert 'PHYSICAL_IDENTITY_CHANGED' in win.status.get()
        assert _files(out)==old
        path.write_bytes(original_bytes)
        # The overwrite modal cannot silently permit a newly edited project.
        def change_during_overwrite(**kw):
            win.fields['width'].set('800')
            return True
        monkeypatch.setattr(messagebox,'askyesno',change_during_overwrite)
        win.export_button.invoke(); assert _files(out)==old and '儲存' in win.status.get()
        win.cancel_button.invoke()
        monkeypatch.setattr(messagebox,'askyesno',lambda **kw:True)
        # Wrong physical board in the actual staged DXF must not pass reopen.
        writer=dxf_serialization.save_scene_dxf
        _,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
        def wrong_board(target,scene):
            writer(target,dict(renders)['head'].scene if Path(target).name.startswith('.lid.tmp-') else scene)
        monkeypatch.setattr(dxf_serialization,'save_scene_dxf',wrong_board)
        win.export_button.invoke()
        assert 'STAGED_DXF_ROUNDTRIP_FAILED: lid' in win.status.get() and _files(out)==old
        # Corrupt actual staged tail, no fake verifier, old four files untouched.
        def bad_unit(target,scene):
            writer(target,scene)
            if Path(target).name.startswith('.tail.tmp-'):
                doc=ezdxf.readfile(target); doc.header['$INSUNITS']=6; doc.saveas(target)
        monkeypatch.setattr(dxf_serialization,'save_scene_dxf',bad_unit)
        win.export_button.invoke()
        assert 'STAGED_DXF_ROUNDTRIP_FAILED: tail' in win.status.get()
        assert _files(out)==old and len(list(out.iterdir()))==4
        print('GUI negative: stale, dialog edit, wrong face, unit tamper; unchanged',old)
        # A live UI source change during the actual atomic move also rolls back.
        from ae_engine import manufacturing_export
        monkeypatch.setattr(dxf_serialization,'save_scene_dxf',writer)
        move=manufacturing_export.os.replace; changed=[]
        def change_after_move(src,dst):
            result=move(src,dst)
            if not changed and Path(src).parent.name.startswith('.whd-dxf-stage-') and Path(dst).parent==out:
                changed.append(Path(dst).name); win.flags['seal'].set(False)
            return result
        monkeypatch.setattr(manufacturing_export.os,'replace',change_after_move)
        win.export_button.invoke()
        assert changed and '儲存' in win.status.get() and _files(out)==old
        monkeypatch.setattr(manufacturing_export.os,'replace',move)
        win.cancel_button.invoke()
        # A legitimate newly confirmed and saved revision can overwrite.
        win.fields['width'].set('800'); win.confirm_button.invoke(); win.save_button.invoke()
        win.export_button.invoke(); assert '4' in win.status.get()
        _,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
        for key,render in renders:
            assert api.verify_saved_part_render_data_dxf(render,out/(key+'.dxf')).ok
        assert _files(out)!=old
    finally:
        root.destroy()
