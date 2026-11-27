"""Q61: rear-only inherited rule, identity binding and true-solid refusal."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from ae_engine import manufacturing_api as api, WirePullBoxSpec
from ae_engine import certified_relief_corner_policy as registry
from ae_engine.certified_relief_registry import _assembly_joint_corner_names, _physical_cut_from_relief
from ae_engine.sheetmetal_geometry import resolve_corner_relief
from ae_engine.cabinet_types.wire_pull_saved_export import _verify_standard_solid_contact
from phase6_project_file import PROJECT_SCHEMA, write_project


def test_q61_only_vault_rear_pair_and_role_mirror(monkeypatch):
    spec=WirePullBoxSpec(637,411,223,3)
    result=api.resolve_standard_cabinet_topology(spec)
    for key in ('head','tail'):
        cap=result.part(key); r=cap.render_data
        vault=registry.lookup_certified_corner_policy_rule(cabinet_family='金庫型',part_role=key)
        assert r.metadata['wire_pull_corner_rules']==('ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1',
            f'{vault.rule_id}@{vault.revision}:bottom_left,bottom_right')
        removed=box(*r.material.bounds).difference(Polygon(r.material.exterior))
        x0,y0,x1,y1=r.material.bounds; mid=(y0+y1)/2
        rear_region=box(x0,mid,x1,y1) if key=='head' else box(x0,y0,x1,mid)
        back=cap.y_profile[-1 if key=='head' else 0].length
        expected=unary_union([_physical_cut_from_relief(name,resolve_corner_relief(
            vault.corner_selections[which],fold_u=side.length,fold_v=back,thickness=spec.thickness,fw=0.),r.material.bounds)
            for name,which,side in zip(_assembly_joint_corner_names(cap.y_profile,'BOTTOM'),
                                      ('bottom_left','bottom_right'),(cap.x_profile[0],cap.x_profile[-1]))])
        assert removed.intersection(rear_region).equals(expected)
    def vertices(part,sign):
        return {tuple(round(v,8) for v in (p[0],sign*p[1],p[2])) for tri in part.world_triangles for p in tri}
    assert vertices(result.part('head'),-1)==vertices(result.part('tail'),1)
    # Missing or changed revision must NOT fall back to a default corner.
    original=registry._CORNER_POLICY_RULES
    for changed in (tuple(r for r in original if r.rule_id!='VAULT_ENDCAP_FIXED_POLICY_V1'),
                    tuple(replace(r,revision=r.revision+1) if r.rule_id=='VAULT_ENDCAP_FIXED_POLICY_V1' else r for r in original)):
        monkeypatch.setattr(registry,'_CORNER_POLICY_RULES',changed)
        with pytest.raises(ValueError,match='REAR_CORNER_RULE_SOURCE_REQUIRED'):
            api.resolve_standard_cabinet_topology(spec)


def test_rule_identity_cannot_be_removed_or_replaced(tmp_path,monkeypatch):
    from ae_engine import manufacturing_export
    from tests.test_issue3503_wire_pull_saved_export import _existing_qualified_files,files
    spec=WirePullBoxSpec(637,411,223,3)
    proposal=api.propose_wire_pull_holes(spec)
    path=write_project(tmp_path/'source.p6fold',{'schema':PROJECT_SCHEMA,'snapshot':api.build_wire_pull_project_snapshot(spec,proposal)})
    original=path.read_bytes(); out=tmp_path/'out'; old=_existing_qualified_files(out)
    def forbidden(*args,**kwargs): pytest.fail('unbound relief identity reached staging')
    monkeypatch.setattr(manufacturing_export,'_save_resolved_rows_atomic',forbidden)
    for mode in ('missing','wrong','swapped'):
        raw=json.loads(original); identity=raw['snapshot']['wire_pull_standard']['identity']
        if mode=='missing': del identity['corner_rules']
        elif mode=='wrong': identity['corner_rules'][0][1][1]='VAULT_ENDCAP_FIXED_POLICY_V1@999:bottom_left,bottom_right'
        else: identity['corner_rules'].reverse()
        path.write_text(json.dumps(raw),encoding='utf-8')
        with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_CHANGED'):
            api.inspect_wire_pull_saved_export(path)
        with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_CHANGED'):
            api.save_wire_pull_saved_project_dxf(path,out,expected_source_sha256=sha256(path.read_bytes()).hexdigest(),overwrite=True)
        assert files(out)==old


def test_actual_solid_contact_oracle_refuses_hidden_front_rail_overlap():
    from ae_engine.assembly_geometry_primitives import thicken_orthogonal_inside_surface
    spec=WirePullBoxSpec(637,411,223,3)
    r=api.resolve_standard_cabinet_topology(spec); body,head,tail,lid=r.parts
    assert min(_verify_standard_solid_contact(r,spec.thickness)['head'])>0
    # An added small true-thickness component inside the front rail lies inside
    # the cap's existing bbox: a bbox-only oracle would miss it.
    x,y,z=-310.,190.,106.
    tris=(((x,y,z),(x+1,y,z),(x+1,y+1,z)),((x,y,z),(x+1,y+1,z),(x,y+1,z)))
    insert=thicken_orthogonal_inside_surface(tris,((0,0,1),(0,0,1)),1.)
    corrupt=replace(head,world_triangles=head.world_triangles+tuple(insert))
    from ae_engine.assembly_geometry_primitives import triangle_bounds
    assert triangle_bounds(corrupt.world_triangles)==triangle_bounds(head.world_triangles)
    with pytest.raises(ValueError,match='SOLID_PENETRATION'):
        _verify_standard_solid_contact(replace(r,parts=(body,corrupt,tail,lid)),spec.thickness)
