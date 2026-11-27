from dataclasses import replace
import pytest
from ae_engine import manufacturing_api as a
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart, ManufacturingContext
from ae_engine.physical_sheet_editor_context import resolve_box_body_piece_manufacturing_witness as resolve
from tests.test_issue2517_confirmed_receiving_box_body_three_physical_dxf import _three_piece_spec

def make():
    return a.build_box_body_structure_render_data(_three_piece_spec(), ManufacturingContext())
def geometry(body,*extra):
    return ResolvedManufacturingGeometry((ResolvedManufacturingPart("box_body",body),*extra))
@pytest.mark.parametrize('role',['left_side','back','right_side'])
def test_exact_geometry_roles(role):
    b=make(); expected=next(p for p in b.pieces if p.role==role)
    g=geometry(replace(b,pieces=tuple(reversed(b.pieces))))
    k,r=resolve(g,'box_body:'+role)
    assert (k,r)==('box_body:'+expected.key,expected.render_data)
    assert r is expected.render_data

@pytest.mark.parametrize('case',['forged_topology','duplicate_role','aggregate_only','aliased_sheet','missing_role'])
def test_bad_witness_rejected(case):
    b=make(); l=b.pieces[0]; assert l.role=='left_side'
    if case=='forged_topology':
        b=replace(b,pieces=(replace(l,key='forged'),*b.pieces[1:]))
    elif case=='duplicate_role':
        b=replace(b,pieces=(*b.pieces,l))
    elif case=='aggregate_only':
        b=b.preview_render_data
    elif case=='missing_role':
        b=replace(b,pieces=b.pieces[1:])
    extra=(ResolvedManufacturingPart('unrelated',l.render_data),) if case=='aliased_sheet' else ()
    with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_UNPROVEN'):
        resolve(geometry(b,*extra),'box_body:left_side')
