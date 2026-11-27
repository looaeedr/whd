"""Saved-source four-part admission, not a preview or a generic family unlock."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import ezdxf
import pytest
from ae_engine import manufacturing_api as api, WirePullBoxSpec
from ae_engine.cabinet_types import resolve_cabinet_type
from ae_engine.cabinet_types.wire_pull_holes import HoleDefaults, HoleOptions
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

KEYS = ('box_body', 'head', 'tail', 'lid')


def make_project(path, w, t=3., *, legacy=False):
    spec = (WirePullBoxSpec(w,1200.,223.,t,27.,34.,'flat','flat') if legacy else
            WirePullBoxSpec(w,1200.,223.,t))
    hole = CircleFeature(4., FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400.,600.), source_type='MANUAL_TEST')
    mark = replace(hole, layer='MARKING', diameter=2., offset=Vec2(420.,620.))
    options = HoleOptions(HoleDefaults(480.,110.,1000.,100.,150.,1800.))
    proposal = api.propose_wire_pull_holes(spec,options,manual=(('box_body',(hole,mark)),))
    assert not proposal.conflicts
    return write_project(path,{'schema':PROJECT_SCHEMA,'snapshot':api.build_wire_pull_project_snapshot(spec,proposal)})


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def files(folder):
    return {p.name:(digest(p),p.stat().st_mtime_ns) for p in folder.iterdir() if p.is_file()}


@pytest.mark.parametrize('w,t',[(637.,3.),(1801.,1.5)])
def test_real_saved_four_part_reopen_after_admission(tmp_path,w,t):
    project = make_project(tmp_path/'source.p6fold',w,t)
    source = api.inspect_wire_pull_saved_export(project)
    assert source.source_sha256 == digest(project)
    assert source.part_keys == KEYS
    proposal,renders = api.restore_wire_pull_project_snapshot(read_project(project)['snapshot'])
    assert len([m for m in proposal.members if m.kind=='anchor']) == (4 if w==637 else 6)
    out = tmp_path/'output'
    _require_admitted(project)
    result = api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=source.source_sha256)
    assert tuple(result) == KEYS and len(list(out.iterdir())) == 4
    for key,render in renders:
        target=Path(result[key]); assert target.name==key+'.dxf'
        doc=ezdxf.readfile(target); assert not doc.audit().errors and doc.header['$INSUNITS']==4
        assert api.verify_saved_part_render_data_dxf(render,target).ok
        assert not list(doc.modelspace().query('*[layer=="CHECK"]'))
        if key=='box_body':
            assert len(doc.modelspace().query('CIRCLE[layer=="MARKING"]'))==1
            assert len(doc.modelspace().query('*[layer=="BEND"]'))==4
        elif key in ('head','tail'):
            assert len(doc.modelspace().query('*[layer=="BEND"]'))==4
        else:
            assert not list(doc.modelspace().query('*[layer=="BEND"]'))
        print('REOPEN',w,t,key,digest(target),len(doc.modelspace()))
    old=files(out)
    with pytest.raises(FileExistsError):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=source.source_sha256)
    assert files(out)==old
    assert digest(project)==source.source_sha256
    assert resolve_cabinet_type('WIRE_PULL').implemented is False
    with pytest.raises(ValueError,match='CABINET_FAMILY_NOT_IMPLEMENTED'):
        api.save_part_render_data_dxf(dict(renders)['lid'],out/'lid.dxf',overwrite=True)
    assert files(out)==old


def test_saved_source_stale_identity_and_preview_no_overwrite(tmp_path):
    project = make_project(tmp_path/'source.p6fold',637.)
    initial = api.inspect_wire_pull_saved_export(project)
    out=tmp_path/'output'
    _existing_qualified_files(out)
    old=files(out)
    make_project(project,1801.)
    with pytest.raises(ValueError,match='SAVED_SOURCE_CHANGED'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=initial.source_sha256,overwrite=True)
    assert files(out)==old
    raw=json.loads(project.read_text())
    raw['snapshot']['wire_pull_standard']['identity']['holes'][0][3]='rear'
    project.write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_CHANGED'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=digest(project),overwrite=True)
    assert files(out)==old
    print('STALE/WRONG FACE: old four sha/mtime unchanged',old)


def test_cross_board_rows_and_marking_tamper_rejected_after_admission(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export, dxf_serialization
    from ae_engine.cabinet_types.wire_pull_saved_export import _SavedProjectRows
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
    _require_admitted(project)
    api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha)
    old=files(out)
    source=_SavedProjectRows(project,sha)
    rows=list(source.rows)
    rows[-1]=(rows[-1][0],rows[-1][1],rows[1][2])
    with pytest.raises(ValueError,match='SAVED_EXPORT_ROWS_CHANGED'):
        source.assert_rows(rows)
    # Exercise the actual shared staging path with a different canonical sheet.
    original=dxf_serialization.save_scene_dxf
    def cross_board(path,scene):
        original(path, source.rows[1][2].scene if '.lid.tmp-' in Path(path).name else scene)
    monkeypatch.setattr(dxf_serialization,'save_scene_dxf',cross_board)
    with pytest.raises(ValueError,match='STAGED_DXF_ROUNDTRIP_FAILED: lid'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha,overwrite=True)
    assert files(out)==old
    def moved_mark(path,scene):
        original(path,scene)
        if '.box_body.tmp-' in Path(path).name:
            doc=ezdxf.readfile(path)
            mark=doc.modelspace().query('CIRCLE[layer=="MARKING"]')[0]
            x,y,z=mark.dxf.center; mark.dxf.center=(x+.5,y,z)
            doc.saveas(path)
    monkeypatch.setattr(dxf_serialization,'save_scene_dxf',moved_mark)
    with pytest.raises(ValueError,match='STAGED_DXF_ROUNDTRIP_FAILED: box_body'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha,overwrite=True)
    assert files(out)==old
    assert sorted(p.name for p in out.iterdir())==sorted(old)
    print('CROSS BOARD/MARKING TAMPER: old four sha/mtime unchanged',old)


def test_atomic_late_source_change_rolls_back_all_four_after_admission(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
    _require_admitted(project)
    api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha)
    old=files(out)
    original=manufacturing_export.os.replace
    changed=[]
    def drift_after_first_move(src,dst):
        result=original(src,dst)
        if not changed and Path(src).parent.name.startswith('.whd-dxf-stage-') and Path(dst).parent==out:
            changed.append(Path(dst).name)
            project.write_bytes(project.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(manufacturing_export.os,'replace',drift_after_first_move)
    with pytest.raises(ValueError,match='SAVED_SOURCE_CHANGED'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha,overwrite=True)
    assert changed and digest(project)!=sha
    assert files(out)==old and sorted(p.name for p in out.iterdir())==sorted(old)
    for name in old: assert not ezdxf.readfile(out/name).audit().errors
    print('ROLLBACK after move',changed,'old four sha/mtime unchanged',old)


def test_stage_byte_drift_rejects_without_replacing_after_admission(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
    _require_admitted(project)
    api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha)
    old=files(out)
    commit=manufacturing_export._atomic_commit_staged_dxfs
    def drift(staged,root,**kwargs):
        target=staged['tail']; target.write_bytes(target.read_bytes()+b'\n')
        return commit(staged,root,**kwargs)
    monkeypatch.setattr(manufacturing_export,'_atomic_commit_staged_dxfs',drift)
    with pytest.raises(ValueError,match='WHD_STAGED_DXF'):
        api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha,overwrite=True)
    assert files(out)==old and sorted(p.name for p in out.iterdir())==sorted(old)
    print('STAGED BYTES: old four sha/mtime unchanged',old)


def test_unproven_manual_process_and_duplicate_cut_refuse(tmp_path):
    from ae_engine.cabinet_types.wire_pull_saved_export import _validate_process_shapes
    spec=WirePullBoxSpec(637.,1200.,223.,3.)
    hole=CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(400.,600.),source_type='MANUAL_TEST')
    for name,features,match in (
        ('duplicate',(hole,hole),'SAVED_CUTTING_CONTOUR_CONFLICT'),
        ('blind',(replace(hole,layer='BLIND_HOLE'),),'SAVED_PROCESS_UNSUPPORTED'),
    ):
        proposal=api.propose_wire_pull_holes(spec,manual=(('box_body',features),))
        assert not proposal.conflicts
        project=write_project(tmp_path/(name+'.p6fold'),{'schema':PROJECT_SCHEMA,'snapshot':api.build_wire_pull_project_snapshot(spec,proposal)})
        target=tmp_path/name
        _,renders=api.restore_wire_pull_project_snapshot(read_project(project)['snapshot'])
        with pytest.raises(ValueError,match=match):
            _validate_process_shapes(dict(renders)['box_body'],'box_body')
        with pytest.raises(ValueError,match=match):
            api.save_wire_pull_saved_project_dxf(project,target,expected_source_sha256=digest(project))
        assert not target.exists()
        print('UNSUPPORTED',name,match)


def test_current_confirmed_source_overwrites_all_four_after_admission(tmp_path):
    project=make_project(tmp_path/'source.p6fold',637.)
    out=tmp_path/'output'
    _require_admitted(project)
    api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=digest(project))
    before=files(out)
    make_project(project,1801.)
    sha=api.inspect_wire_pull_saved_export(project).source_sha256
    outputs=api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=sha,overwrite=True)
    assert tuple(outputs)==KEYS
    _,renders=api.restore_wire_pull_project_snapshot(read_project(project)['snapshot'])
    for key,render in renders:
        path=Path(outputs[key]); assert digest(path)!=before[path.name][0]
        assert api.verify_saved_part_render_data_dxf(render,path).ok
        assert ezdxf.readfile(path).header['$INSUNITS']==4
    print('SUCCESSFUL overwrite with newly reopened source',sha)


def _require_admitted(project):
    assert api.inspect_wire_pull_saved_export(project).manufacturing_blocker is None


def _qualified_rows(delta=0):
    # Independently legal existing Family parts, NOT admitted wire-pull parts.
    from ae_engine.contracts import EndCapPartSpec, ManufacturingContext
    rows=[]
    for i,key in enumerate(KEYS):
        mark=CircleFeature(2.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(100.,100.),layer='MARKING')
        spec=EndCapPartSpec(width=500.+20.*i+delta,height=600.,depth=200.,thickness=2.,
                           frame_width=25.,model_name='金庫型',is_tail=key=='tail',holes=(mark,))
        render=api.build_part_render_data(spec,ManufacturingContext(resource_root=Path.cwd()))
        rows.append((key,key+'.dxf',render))
    return tuple(rows)


def _existing_qualified_files(out):
    out.mkdir(parents=True,exist_ok=True)
    for key,filename,render in _qualified_rows():
        api.save_part_render_data_dxf(render,out/filename,verify_reopen=True)
        assert api.verify_saved_part_render_data_dxf(render,out/filename).ok
        doc=ezdxf.readfile(out/filename); assert doc.header['$INSUNITS']==4 and not doc.audit().errors
    return files(out)


@pytest.mark.parametrize('w,t,legacy',[(637.,3.,False),(1801.,1.5,False),(637.,3.,True)])
def test_real_saved_four_part_reopen(tmp_path,monkeypatch,w,t,legacy):
    from ae_engine import manufacturing_export
    project=make_project(tmp_path/'source.p6fold',w,t,legacy=legacy)
    source=api.inspect_wire_pull_saved_export(project)
    assert source.source_sha256==digest(project) and source.part_keys==KEYS
    proposal,renders=api.restore_wire_pull_project_snapshot(read_project(project)['snapshot'])
    assert len([m for m in proposal.members if m.kind=='anchor'])==(4 if w==637 else 6)
    assert tuple(len(r.fold_guides) for _,r in renders)==((4,0,0,0) if legacy else (4,4,4,0))
    assert len([p for p in dict(renders)['box_body'].scene.primitives if p.layer=='MARKING'])==1
    old=_existing_qualified_files(tmp_path/'out'); before=(project.read_bytes(),project.stat().st_mtime_ns)
    if legacy:
        blocker='WIRE_PULL_FLAT_ENDCAP_WITHDRAWN'
        assert source.manufacturing_blocker.startswith(blocker)
        def forbidden(*args,**kwargs): pytest.fail('withdrawn source entered real staging')
        monkeypatch.setattr(manufacturing_export,'_save_resolved_rows_atomic',forbidden)
        for overwrite in (False,True):
            with pytest.raises(ValueError,match=blocker):
                api.save_wire_pull_saved_project_dxf(project,tmp_path/'out',expected_source_sha256=source.source_sha256,overwrite=overwrite)
            assert files(tmp_path/'out')==old
        with pytest.raises(ValueError,match=blocker):
            api.save_wire_pull_saved_project_dxf(project,tmp_path/'new',expected_source_sha256=source.source_sha256)
        assert not (tmp_path/'new').exists()
    else:
        assert source.manufacturing_blocker is None
        with pytest.raises(FileExistsError):
            api.save_wire_pull_saved_project_dxf(project,tmp_path/'out',expected_source_sha256=source.source_sha256)
        assert files(tmp_path/'out')==old
        paths=api.save_wire_pull_saved_project_dxf(project,tmp_path/'out',expected_source_sha256=source.source_sha256,overwrite=True)
        assert tuple(paths)==KEYS
        for key,render in renders:
            assert api.verify_saved_part_render_data_dxf(render,paths[key]).ok
        old=files(tmp_path/'out')
    assert (project.read_bytes(),project.stat().st_mtime_ns)==before
    assert resolve_cabinet_type('WIRE_PULL').implemented is False
    with pytest.raises(ValueError,match='CABINET_FAMILY_NOT_IMPLEMENTED'):
        api.save_part_render_data_dxf(dict(renders)['lid'],tmp_path/'out'/'lid.dxf',overwrite=True)
    assert files(tmp_path/'out')==old


def test_cross_board_rows_and_marking_tamper_rejected(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export as sink, manufacturing_verification, dxf_serialization
    rows=_qualified_rows(10); out=tmp_path/'out'; old=_existing_qualified_files(out)
    def writer(render,path,*,overwrite):
        # Same qualified shared sink; substitute a wrong real board or units,
        # never an uncertified wire-pull render or a mocked verifier.
        dxf_serialization.save_scene_dxf(path,rows[1][2].scene if Path(path).name=='lid.dxf' else render.scene)
    with pytest.raises(ValueError,match='STAGED_DXF_ROUNDTRIP_FAILED: lid'):
        sink._save_resolved_rows_atomic(rows,out,save_part_render_data_dxf=writer,overwrite=True,verify_all_staged=True)
    assert files(out)==old
    def bad_unit(render,path,*,overwrite):
        dxf_serialization.save_scene_dxf(path,render.scene)
        if Path(path).name=='tail.dxf':
            doc=ezdxf.readfile(path); doc.header['$INSUNITS']=6; doc.saveas(path)
    with pytest.raises(ValueError,match='STAGED_DXF_ROUNDTRIP_FAILED: tail'):
        sink._save_resolved_rows_atomic(rows,out,save_part_render_data_dxf=bad_unit,overwrite=True,verify_all_staged=True)
    assert files(out)==old
    # Exercise the strict marking-circle oracle on a REAL qualified file.
    render=rows[0][2]; target=tmp_path/'mark.dxf'; api.save_part_render_data_dxf(render,target,verify_reopen=True)
    assert manufacturing_verification.verify_saved_part_render_data_dxf(render,target,verify_all_marking_circles=True).ok
    doc=ezdxf.readfile(target); mark=doc.modelspace().query('CIRCLE[layer=="MARKING"]')[0]
    x,y,z=mark.dxf.center; mark.dxf.center=(x+.5,y,z); doc.saveas(target)
    assert not manufacturing_verification.verify_saved_part_render_data_dxf(render,target,verify_all_marking_circles=True).ok
    assert files(out)==old


def _qualified_verified_stage(tmp_path):
    from ae_engine import manufacturing_export as sink
    out=tmp_path/'out'; old=_existing_qualified_files(out)
    rows=_qualified_rows(20); stage=tmp_path/'stage'; stage.mkdir()
    staged={}; seals={}
    for key,name,render in rows:
        path=stage/name; api.save_part_render_data_dxf(render,path,verify_reopen=True)
        assert api.verify_saved_part_render_data_dxf(render,path).ok
        staged[key]=path; seals[key]=sink.verified_dxf_content_digest(path)
    return out,old,rows,staged,seals


def test_atomic_late_source_change_rolls_back_all_four(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export as sink
    out,old,rows,staged,seals=_qualified_verified_stage(tmp_path)
    # Real saved source revision guard, same shared atomic move owner.
    project=make_project(tmp_path/'source.p6fold',637.); sha=digest(project)
    original=sink.os.replace; changed=[]
    def guard():
        if digest(project)!=sha: raise ValueError('WIRE_PULL_SAVED_SOURCE_CHANGED')
    def move(src,dst):
        result=original(src,dst)
        if not changed and Path(src).parent==tmp_path/'stage' and Path(dst).parent==out:
            changed.append(Path(dst).name); project.write_bytes(project.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(sink.os,'replace',move)
    with pytest.raises(ValueError,match='SAVED_SOURCE_CHANGED'):
        sink._atomic_commit_staged_dxfs(staged,out,overwrite=True,pre_commit_guard=guard,verified_byte_seals=seals)
    assert changed and digest(project)!=sha and files(out)==old
    assert all(not ezdxf.readfile(out/name).audit().errors for name in old)


def test_stage_byte_drift_rejects_without_replacing(tmp_path):
    from ae_engine import manufacturing_export as sink
    out,old,rows,staged,seals=_qualified_verified_stage(tmp_path)
    path=staged['tail']; path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='WHD_STAGED_DXF'):
        sink._atomic_commit_staged_dxfs(staged,out,overwrite=True,verified_byte_seals=seals)
    assert files(out)==old and set(p.name for p in out.iterdir())==set(old)


def test_current_confirmed_source_overwrites_all_four(tmp_path):
    from ae_engine import manufacturing_export as sink
    out,old,rows,staged,seals=_qualified_verified_stage(tmp_path)
    with pytest.raises(FileExistsError):
        sink._atomic_commit_staged_dxfs(staged,out,overwrite=False,verified_byte_seals=seals)
    assert files(out)==old
    outputs=sink._atomic_commit_staged_dxfs(staged,out,overwrite=True,verified_byte_seals=seals)
    assert tuple(outputs)==KEYS
    for key,name,render in rows:
        path=Path(outputs[key]); assert digest(path)!=old[name][0]
        assert api.verify_saved_part_render_data_dxf(render,path).ok
        assert ezdxf.readfile(path).header['$INSUNITS']==4
