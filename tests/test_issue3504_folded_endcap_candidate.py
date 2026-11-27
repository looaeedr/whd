"""User-confirmed material Fold defaults and bounded folded preview candidate.
Q61: verify physical geometry and narrowly admitted saved-source export.
"""
from dataclasses import replace
from hashlib import sha256
from itertools import combinations, accumulate
from pathlib import Path
from math import fsum
import os

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union
from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.assembly_geometry import diagnose_world_mesh_triangle_edge_incidence, diagnose_world_mesh_self_intersections
from ae_engine.assembly_geometry_primitives import triangle_bounds
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
from phase6_project_file import PROJECT_SCHEMA, write_project, read_project


def projected(tris, axes):
    polys=[Polygon([(p[axes[0]],p[axes[1]]) for p in tri]) for tri in tris]
    return unary_union([p for p in polys if p.area>1e-10])


def volume(tris):
    return fsum(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]) for a,b,c in tris)/6.


@pytest.mark.parametrize('t,fw,adjust', [(3.,25.,False),(1.5,34.,True)])
def test_real_folded_preview_and_saved_source(tmp_path,t,fw,adjust):
    s=WirePullBoxSpec(637.,411.,223.,t) if not adjust else WirePullBoxSpec(637.,411.,223.,t,fw,fw,
        head_left_material_mm=17.,head_right_material_mm=19.,head_bottom_material_mm=18.,
        tail_left_material_mm=16.,tail_right_material_mm=20.,tail_bottom_material_mm=22.)
    base=api.resolve_standard_cabinet_topology(s)
    proposal=api.propose_wire_pull_holes(s)
    assert not proposal.conflicts
    render_pairs=api.confirm_wire_pull_holes(s,proposal)
    result=api.confirm_wire_pull_hole_topology(s,proposal)
    assert tuple(len(p.render_data.fold_guides) for p in result.parts)==(4,4,4,0)
    assert tuple(hi-lo for lo,hi in result.outside_bounds)==pytest.approx((637,411,223))
    body,head,tail,lid=result.parts
    assert (body.x_profile[0].length,body.x_profile[-1].length)==(fw,fw)
    assert tuple(r.phase6_key for r in head.y_profile)==('fw','endcap_d_core','ybottom1')
    assert tuple(r.phase6_key for r in tail.y_profile)==('ybottom1','endcap_d_core','fw')
    assert head.y_profile[0].length==tail.y_profile[-1].length==fw
    # Re-read the actual body Fold and physical skin datum through the public
    # linked owner; no legacy Family D offset, no use of cap output as input.
    faces={f.face_id:f for f in body.mounting_faces}
    body_bounds=triangle_bounds(body.world_triangles)
    source=api.LinkedEndcapInsertSource(
        faces['right'].world_origin[0]-faces['left'].world_origin[0]-2*t,
        faces['front_left_return'].world_origin[2]-(faces['rear'].world_origin[2]+t),t,
        tuple(getattr(s,'head_'+edge+'_material_mm') for edge in ('left','right','bottom')),
        tuple(getattr(s,'tail_'+edge+'_material_mm') for edge in ('left','right','bottom')))
    rows=[dict(len=r.length,phase6_key=r.phase6_key,
               **({'angle':r.angle} if r.angle is not None else {}),
               **({'core':r.core} if r.core else {})) for r in body.x_profile]
    linked=api.build_linked_endcap_xy_fold_profiles({},rows,insert_source=source)
    # Independent legacy control: same source turns and front mating chain,
    # but the legacy Family core compensation must not set this geometry.
    from copy import deepcopy
    legacy_rows=deepcopy(rows)
    for row,name in zip(legacy_rows,('fw_left','d_left','w','d_right','fw_right')):
        row['phase6_key']=name
    legacy=api.build_linked_endcap_xy_fold_profiles(
        dict(w=s.width,d=s.depth,t=t,fw=fw,yl1=15,yr1=15,ybottom1=15),legacy_rows)
    for cap,sign in ((head,1),(tail,-1)):
        key=cap.part_key
        for axis,profile in (('X',cap.x_profile),('Y',cap.y_profile)):
            rows_public=linked[key][axis]
            assert [(r.length,r.angle,r.phase6_key,r.core) for r in profile]==[(r['len'],r.get('angle'),r['phase6_key'],r.get('core')) for r in rows_public]
            assert [(r.phase6_key,r.angle) for r in profile]==[(r['phase6_key'],r.get('angle')) for r in legacy[key][axis]]
            assert tuple(g.position for g in cap.render_data.fold_guides if g.axis==axis.lower())==pytest.approx(tuple(accumulate(r['len'] for r in rows_public[:-1])))
        assert cap.y_profile[1].length==pytest.approx(source.outside_depth-2*t)
        assert cap.x_profile[1].length==pytest.approx(source.outside_width-2*t)
        assert cap.x_profile[0].length==getattr(s,key+'_left_material_mm')
        assert cap.x_profile[-1].length==getattr(s,key+'_right_material_mm')
        assert (cap.y_profile[-1] if sign==1 else cap.y_profile[0]).length==getattr(s,key+'_bottom_material_mm')
        assert cap.mounting_faces[0].outward_normal==(0,sign,0)
        assert triangle_bounds(cap.world_triangles)[1][1 if sign==1 else 0]==pytest.approx(sign*s.height/2)
        assert cap.render_data.material.equals(material_polygon_from_final_scene(cap.render_data.scene))
        assert cap.render_data.unfolded_topology.width==pytest.approx(sum(r.length for r in cap.x_profile))
        assert cap.render_data.unfolded_topology.height==pytest.approx(sum(r.length for r in cap.y_profile))
        diag=diagnose_world_mesh_self_intersections(cap.world_triangles)
        assert not diag.crossing_pair_count and not diag.coplanar_overlap_pair_count and not diag.numerical_budget_exhausted
        # Whole XZ projection separation proves zero positive volume with the
        # vertical body, even across holes. Boundary intersection is contact.
        bp=projected(body.world_triangles,(0,2)); cp=projected(cap.world_triangles,(0,2))
        assert bp.intersection(cp).area<1e-8
        assert bp.boundary.intersection(cp.boundary).length>0
        assert triangle_bounds(cap.world_triangles)[2][1]==pytest.approx(triangle_bounds(lid.world_triangles)[2][0])
        print('CAP',t,fw,key,'blank',cap.render_data.unfolded_topology.width,cap.render_data.unfolded_topology.height,'XZ overlap',bp.intersection(cp).area,'contact projection',bp.boundary.intersection(cp.boundary).length,'volume',volume(cap.world_triangles))
    for part in result.parts:
        assert diagnose_world_mesh_triangle_edge_incidence(part.world_triangles).edges_manifold_closed
        assert volume(part.world_triangles)>0
        assert part.render_data==dict(render_pairs)[part.part_key]
    b,l=triangle_bounds(body.world_triangles),triangle_bounds(lid.world_triangles)
    assert all(abs(g-1)<1e-6 for axis in (0,1) for g in (l[axis][0]-b[axis][0],b[axis][1]-l[axis][1]))
    assert l[2][0]==b[2][1]
    assert all(j.clearance_policy=='ZERO' for j in result.joints)
    # Same body/lid hole sources as the old, symmetric source.
    old=api.propose_wire_pull_holes(replace(s,head_form='flat',tail_form='flat'))
    assert proposal.members==old.members
    path=write_project(tmp_path/'folded.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':api.build_wire_pull_project_snapshot(s,proposal)})
    digest=sha256(path.read_bytes()).hexdigest()
    restored,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
    assert restored==proposal and renders==render_pairs
    assert api.confirm_wire_pull_hole_topology(s,restored).parts==result.parts
    from ae_engine.cabinet_types.wire_pull_saved_export import _verify_standard_solid_contact
    contacts=_verify_standard_solid_contact(result,t)
    for key,areas in contacts.items():
        assert min(areas)>0
        print('TRUE COPLANAR CONTACT mm2',key,areas)
    for part in result.parts:
        diag=diagnose_world_mesh_self_intersections(part.world_triangles,max_nonadjacent_pairs=max(1,len(part.world_triangles)**2))
        assert not diag.crossing_pair_count and not diag.coplanar_overlap_pair_count and not diag.numerical_budget_exhausted
    assert api.inspect_wire_pull_saved_export(path).manufacturing_blocker is None
    outputs=api.save_wire_pull_saved_project_dxf(path,tmp_path/'out',expected_source_sha256=digest)
    import ezdxf
    assert tuple(outputs)==('box_body','head','tail','lid')
    for key,render in renders:
        target=Path(outputs[key]); doc=ezdxf.readfile(target)
        assert doc.header['$INSUNITS']==4 and not doc.audit().errors
        assert api.verify_saved_part_render_data_dxf(render,target).ok
        print('Q61 REOPEN',t,fw,key,sha256(target.read_bytes()).hexdigest(),len(doc.modelspace()))


def test_asymmetric_returns_and_malformed_new_fold_are_refused():
    s=WirePullBoxSpec(637,411,223,3)
    for bad,match in ((replace(s,right_return_material_mm=34),'FRONT_FOLD_SOURCE_AMBIGUOUS'),
                      (replace(s,head_bottom_material_mm=0),'INVALID_DIMENSION'),
                      (replace(s,tail_left_material_mm=True),'SOURCE_REQUIRED'),
                      (replace(s,head_clearance_mm=.5),'INSERT_ZERO_REQUIRED')):
        with pytest.raises(ValueError,match=match): api.resolve_standard_cabinet_topology(bad)


def test_old_flat_schema_still_reopens(tmp_path):
    s=WirePullBoxSpec(637,411,223,3,27,34,'flat','flat')
    p=api.propose_wire_pull_holes(s)
    sn=api.build_wire_pull_project_snapshot(s,p)
    raw=sn['wire_pull_standard']['spec']
    for k in list(raw):
        if k.startswith(('head_','tail_')) and k.endswith('_material_mm'): del raw[k]
    path=write_project(tmp_path/'legacy.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':sn})
    restored,renders=api.restore_wire_pull_project_snapshot(read_project(path)['snapshot'])
    assert restored==p and tuple(len(r.fold_guides) for _,r in renders)==(4,0,0,0)
    assert api.inspect_wire_pull_saved_export(path).manufacturing_blocker.startswith('WIRE_PULL_FLAT_ENDCAP_WITHDRAWN')


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_new_gui_defaults_adjust_and_reopen(tmp_path, monkeypatch):
    import tkinter as tk
    import gui
    from tkinter import filedialog
    root=tk.Tk()
    try:
        host=gui.Phase6PrimaryApplication(root); root.update()
        menu=host.fold_designer_app.project_file_menu
        i=next(i for i in range(menu.index('end')+1) if menu.type(i)=='command' and menu.entrycget(i,'label')=='標準拉線箱')
        menu.invoke(i); root.update(); win=host.wire_pull_window
        assert tuple(win.fields[k].get() for k in ('left_return_material_mm','right_return_material_mm'))==('25.0','25.0')
        assert all(win.fields[k].get()=='15.0' for k in win.fields if k.startswith(('head_','tail_')))
        for k,v in dict(width=637,height=411,depth=223,thickness=3,head_left_material_mm=17,tail_bottom_material_mm=19).items(): win.fields[k].set(str(v))
        win.preview_button.invoke(); root.update(); assert win.proposal is not None and not win.proposal.conflicts
        assert tuple(len(r.fold_guides) for _,r in win.renders)==(4,4,4,0)
        win.view3d_button.invoke(); root.update(); assert win.physical is not None
        win.confirm_button.invoke(); root.update(); snapshot=win.controller.committed_snapshot(); assert snapshot
        target=tmp_path/'gui.p6fold'; monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(target))
        win.save_button.invoke(); root.update(); assert target.exists()
        win.window.destroy(); root.update()
        monkeypatch.setattr(filedialog,'askopenfilename',lambda **kw:str(target))
        menu.invoke(0); root.update(); reopened=host.wire_pull_window
        assert reopened.controller.committed_snapshot()==snapshot
        assert reopened.fields['head_left_material_mm'].get()=='17.0'
        assert reopened.fields['tail_bottom_material_mm'].get()=='19.0'
        assert tuple(len(r.fold_guides) for _,r in reopened.renders)==(4,4,4,0)
    finally: root.destroy()



def test_linked_insert_source_rejects_asymmetry_and_preserves_fractional_material():
    from copy import deepcopy
    spec=WirePullBoxSpec(637,411,223,1.5,30.25,30.25,
                         head_left_material_mm=15.25,tail_bottom_material_mm=16.75)
    body=api.resolve_standard_cabinet_topology(spec).part('box_body')
    rows=[dict(len=r.length,phase6_key=r.phase6_key,**({'angle':r.angle} if r.angle is not None else {}),**({'core':r.core} if r.core else {})) for r in body.x_profile]
    src=api.LinkedEndcapInsertSource(634.,220.,1.5,(15.25,15.,15.),(15.,15.,16.75))
    original=deepcopy(rows)
    result=api.build_linked_endcap_xy_fold_profiles({},rows,insert_source=src)
    assert rows==original
    assert result['head']['Y'][0]['len']==result['tail']['Y'][-1]['len']==30.25
    assert result['head']['X'][0]['len']==15.25 and result['tail']['Y'][0]['len']==16.75
    rows[-1]['len']=30.5
    with pytest.raises(ValueError,match='FRONT_FOLD_SOURCE_AMBIGUOUS'):
        api.build_linked_endcap_xy_fold_profiles({},rows,insert_source=src)
    rows=deepcopy(original);rows[1]['angle']=-45
    with pytest.raises(ValueError,match='FRONT_SUPPORT_SOURCE_REQUIRED'):
        api.build_linked_endcap_xy_fold_profiles({},rows,insert_source=src)
