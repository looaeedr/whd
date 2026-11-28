from copy import deepcopy
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import CircleFeature,FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_designer_workspace import Phase6DesignerWorkspace as WS
from phase6_project_file import PROJECT_SCHEMA,write_project,read_project

def setup_case():
    w=WS.from_snapshot({'model':'金庫型'})
    k=w.add_custom_part(display_name='板',fold_axis='X',transverse_length=300)
    return w,k
def snapshot(w):
    return {'model':'金庫型','t':2,'workspace':w.snapshot()}
def receipt(s,k,features=()):
    r=api.build_part_render_data(api.custom_part_spec(s,k,features=features))
    return api.open_physical_sheet_marking(k,snapshot=s,geometry=api.selected_normal_marking_inventory(k,r))
def prepared(w,k):
    s=snapshot(w); r=receipt(s,k)
    p=r.source._render.material.representative_point()
    mark=r.create((),midpoint=Vec2(p.x,p.y),length=8,angle_deg=37)
    draft=api.open_workspace_owner_marking_draft(s,r)
    return s,r,api.prepare_workspace_owner_marking_commit(s,draft,r,(mark,))
def hole():
    return CircleFeature(5,FeatureAnchor.TOP_RIGHT,Vec2(-10,-10))

def test_stale_role_callback_cannot_commit():
    w,k=setup_case()
    s,r,upd=prepared(w,k)
    def read_old_during_live_change():
        w.stash_features(k,(hole(),))
        return s
    with pytest.raises(ValueError,match='PHYSICAL_MARKING_CUSTOM_SOURCE_MISMATCH|ROOT_MARKING_SOURCE_STALE'):
        w.commit_owner_marking_update(upd,model=s['model'],read_current_receipt=lambda:r,read_current_source=read_old_during_live_change)

def test_pending_stock_change_does_not_leave_old_seal():
    w,k=setup_case()
    s,r,upd=prepared(w,k)
    try:
        changed=w.commit_owner_marking_update(upd,model=s['model'],read_current_receipt=lambda:r,read_current_source=lambda:s,pending_role_features=(hole(),))
    except ValueError:
        return
    current=snapshot(w); assert changed
    fresh=receipt(current,k,w.features_for(k))
    api.open_workspace_owner_marking_draft(current,fresh)

def test_true_project_hydrates_nested_only_custom_hole(tmp_path):
    w,k=setup_case()
    w.stash_features(k,(hole(),))
    s=snapshot(w)
    s['part_features']={'door':[]}
    p=write_project(tmp_path/'custom.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':s})
    saved=read_project(p)['snapshot']
    assert saved['workspace']['part_features'][k]
    reopened=WS.from_snapshot(saved)
    assert reopened.features_for(k)==[hole()]
    receipt(saved,k,reopened.features_for(k))
