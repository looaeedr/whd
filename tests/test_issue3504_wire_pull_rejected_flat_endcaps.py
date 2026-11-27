"""Rejected flat Head/Tail is historical preview data, never a standard job."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog

import ezdxf
import pytest
from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

ERROR = 'WIRE_PULL_FLAT_ENDCAP_WITHDRAWN'
KEYS = ('box_body','head','tail','lid')


def old_project(path):
    spec = WirePullBoxSpec(637.,411.,223.,3.,27.,34.,'flat','flat')
    physical = api.resolve_standard_cabinet_topology(spec)
    assert tuple(len(p.render_data.fold_guides) for p in physical.parts) == (4,0,0,0)
    # Original operator features, not replacements inferred from a new blank.
    hole = CircleFeature(4., FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400.,205.))
    mark = replace(hole, layer='MARKING', diameter=2., offset=Vec2(420.,225.))
    proposal = api.propose_wire_pull_holes(spec, manual=(('box_body',(hole,mark)),))
    assert not proposal.conflicts
    snapshot = api.build_wire_pull_project_snapshot(spec,proposal)
    return write_project(path, {'schema':PROJECT_SCHEMA,'snapshot':snapshot}), proposal, snapshot


def hashes(folder):
    return {p.name:(sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in folder.iterdir() if p.is_file()}


def test_saved_flat_rejected_without_stage_and_preserves_existing_real_dxf(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export, dxf_serialization
    path,proposal,snapshot = old_project(tmp_path/'legacy.p6fold')
    digest = sha256(path.read_bytes()).hexdigest()
    original_file = (path.read_bytes(),path.stat().st_mtime_ns)
    folder = tmp_path/'existing'; folder.mkdir()
    # Real old-family files: never manufacture the withdrawn wire-pull shape
    # just to construct sentinel data.
    for i,key in enumerate(KEYS):
        spec = EndCapPartSpec(width=500.+i*20.,height=600.,depth=200.,thickness=2.,
                              frame_width=25.,model_name='金庫型',is_tail=key=='tail')
        api.generate_part(spec,folder/(key+'.dxf'),ManufacturingContext(resource_root=Path.cwd()))
    before = hashes(folder)
    calls=[]
    original=manufacturing_export._save_resolved_rows_atomic
    def observed(*args,**kwargs):
        calls.append('stage')
        return original(*args,**kwargs)
    monkeypatch.setattr(manufacturing_export,'_save_resolved_rows_atomic',observed)
    source=api.inspect_wire_pull_saved_export(path,expected_snapshot=snapshot)
    with pytest.raises(ValueError,match=ERROR):
        api.save_wire_pull_saved_project_dxf(path,folder,expected_source_sha256=digest,overwrite=True)
    assert source.manufacturing_blocker.startswith(ERROR)
    assert not calls and hashes(folder)==before
    assert (path.read_bytes(),path.stat().st_mtime_ns)==original_file
    for p in folder.iterdir():
        doc=ezdxf.readfile(p)
        assert doc.header['$INSUNITS']==4 and not doc.audit().errors
    restored,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
    assert restored==proposal and tuple(k for k,_ in renders)==KEYS
    print('LEGACY SAVED SOURCE: 4,0,0,0 BEND; blocked before stage; original four DXF SHA/mtime unchanged',before)


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='requires Tk display')
def test_new_window_does_not_assume_flat_and_legacy_reopens_without_conversion(tmp_path,monkeypatch):
    import gui
    path,proposal,snapshot=old_project(tmp_path/'legacy.p6fold')
    original=(path.read_bytes(),path.stat().st_mtime_ns)
    root=tk.Tk()
    try:
        host=gui.Phase6PrimaryApplication(root); root.update()
        menu=host.fold_designer_app.project_file_menu
        index=next(i for i in range(menu.index('end')+1) if menu.type(i)=='command' and menu.entrycget(i,'label')=='標準拉線箱')
        menu.invoke(index); root.update(); win=host.wire_pull_window
        for field in ('width','height','depth','thickness','left_return_material_mm','right_return_material_mm'):
            win.fields[field].set(str(getattr(proposal.spec,field)))
        win.preview_button.invoke(); root.update()
        assert win.proposal is None and not win.renders
        assert 'WIRE_PULL_ENDCAP_FRONT_FOLD_SOURCE_AMBIGUOUS' in win.status.get()
        win.confirm_button.invoke(); root.update()
        assert win.controller.committed_snapshot() is None
        win.window.destroy(); root.update()
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(path))
        menu.invoke(0); root.update(); win=host.wire_pull_window
        assert win.proposal==proposal and win._source()[0]==proposal.spec
        assert win.controller.committed_snapshot()==snapshot
        assert '退修' in win.status.get()
        assert win.renders and dict(win.renders)['head'].fold_guides==()
        win.view3d_button.invoke(); root.update()
        assert win.physical and len(win.physical.parts)==4
        assert '退修' in win._mesh_window.title()
        picker=[]
        monkeypatch.setattr(filedialog,'askdirectory',lambda **kw:picker.append(True))
        win.export_button.invoke(); root.update()
        assert ERROR in win.status.get() and not picker
        win.fields['fixed_pitch'].set('450')
        win.preview_button.invoke(); root.update()
        assert win.proposal.manual==proposal.manual and win.proposal.spec==proposal.spec
        win.cancel_button.invoke(); root.update()
        assert win.proposal==proposal and win.controller.committed_snapshot()==snapshot
        assert (path.read_bytes(),path.stat().st_mtime_ns)==original
        print('NATIVE: new form unresolved; legacy shape/features unchanged; export rejected before picker')
    finally:
        root.destroy()
