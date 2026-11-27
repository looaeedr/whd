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


def make_project(path, w, t=3.):
    spec = WirePullBoxSpec(w,1200.,223.,t,27.,34.,'flat','flat')
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
def test_real_saved_four_part_reopen(tmp_path,w,t):
    project = make_project(tmp_path/'source.p6fold',w,t)
    source = api.inspect_wire_pull_saved_export(project)
    assert source.source_sha256 == digest(project)
    assert source.part_keys == KEYS
    proposal,renders = api.restore_wire_pull_project_snapshot(read_project(project)['snapshot'])
    assert len([m for m in proposal.members if m.kind=='anchor']) == (4 if w==637 else 6)
    out = tmp_path/'output'
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
    api.save_wire_pull_saved_project_dxf(project,out,expected_source_sha256=initial.source_sha256)
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


def test_cross_board_rows_and_marking_tamper_rejected(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export, dxf_serialization
    from ae_engine.cabinet_types.wire_pull_saved_export import _SavedProjectRows
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
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


def test_atomic_late_source_change_rolls_back_all_four(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
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


def test_stage_byte_drift_rejects_without_replacing(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export
    project=make_project(tmp_path/'source.p6fold',637.)
    sha=digest(project); out=tmp_path/'output'
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
    spec=WirePullBoxSpec(637.,1200.,223.,3.,27.,34.,'flat','flat')
    hole=CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(400.,600.),source_type='MANUAL_TEST')
    for name,features,match in (
        ('duplicate',(hole,hole),'SAVED_CUTTING_CONTOUR_CONFLICT'),
        ('blind',(replace(hole,layer='BLIND_HOLE'),),'SAVED_PROCESS_UNSUPPORTED'),
    ):
        proposal=api.propose_wire_pull_holes(spec,manual=(('box_body',features),))
        assert not proposal.conflicts
        project=write_project(tmp_path/(name+'.p6fold'),{'schema':PROJECT_SCHEMA,'snapshot':api.build_wire_pull_project_snapshot(spec,proposal)})
        target=tmp_path/name
        with pytest.raises(ValueError,match=match):
            api.save_wire_pull_saved_project_dxf(project,target,expected_source_sha256=digest(project))
        assert not target.exists()
        print('UNSUPPORTED',name,match)


def test_current_confirmed_source_overwrites_all_four(tmp_path):
    project=make_project(tmp_path/'source.p6fold',637.)
    out=tmp_path/'output'
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
