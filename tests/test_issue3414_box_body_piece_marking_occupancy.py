from copy import deepcopy
from dataclasses import replace
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.box_body_structure_state import (
    read_box_body_piece_marking_owner as owner,
    propose_box_body_piece_marking_occupancy as propose,
)
from ae_engine.contracts import ManufacturingContext, ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.workspace_state import SharedWorkspaceState
from tests.test_issue2517_confirmed_receiving_box_body_three_physical_dxf import _three_piece_spec
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

KEYS = ("box_body:left_side", "box_body:back", "box_body:right_side")
TOKEN_KEY = "physical_piece_marking_occupancy"

def actual():
    spec = _three_piece_spec()
    body = api.build_box_body_structure_render_data(spec, ManufacturingContext())
    return spec.structure_state, ResolvedManufacturingGeometry((ResolvedManufacturingPart("box_body",body),))

def allocated():
    source, geometry = actual()
    before = deepcopy(source)
    state = source
    for k in KEYS:
        state = propose(state, k, geometry)
    assert before == source
    assert all(owner(source,k) is None for k in KEYS)
    assert len({owner(state,k) for k in KEYS}) == 3
    return state, geometry

def test_true_three_piece_project_roundtrip(tmp_path):
    state, geometry = allocated()
    assert propose(state, KEYS[0], geometry) == state
    ws = SharedWorkspaceState(box_body_structure=state)
    src = {**ws.snapshot(), "model":"受電箱"}
    loaded = read_project(write_project(tmp_path/"receiving.p6fold", {
        "schema": PROJECT_SCHEMA, "saved_at":"2026-11-26T00:05:00+08:00",
        "snapshot":src,
    }))["snapshot"]
    assert all(owner(loaded["box_body_structure"],k) == owner(state,k) for k in KEYS)
    assert loaded["existing_parts"] == ["box_body"]

def test_reactivation_does_not_revive_owner():
    state, geometry = allocated()
    original = owner(state, KEYS[0])
    state = api.activate_structure_with_defaults(state,"integral",800)
    assert TOKEN_KEY not in state
    state = api.activate_structure_with_defaults(state,"three_piece_side_back_split",800)
    assert all(owner(state,k) is None for k in KEYS)
    assert owner(propose(state,KEYS[0],geometry),KEYS[0]) != original

def test_back_replacement_preserves_only_unreplaced_occupancy():
    old, _ = allocated()
    assert api.set_side_back_back_panel_mode(old,"FULL") == old
    new = api.set_side_back_back_panel_mode(old,"HALF")
    assert owner(new, KEYS[1]) is None
    assert owner(api.set_side_back_back_panel_mode(new,"FULL"), KEYS[1]) is None
    assert all(owner(new,k) == owner(old,k) for k in (KEYS[0],KEYS[2]))

@pytest.mark.parametrize("raw",[{"box_body":"root-owner:"+"a"*32},{KEYS[0]:"a"},dict.fromkeys(KEYS,"root-owner:"+"a"*32)])
def test_reject_malformed_occupancy(raw):
    state,_ = actual()
    with pytest.raises(ValueError,match="OCCUPANCY_INVALID"):
        owner({**state,TOKEN_KEY:raw},KEYS[0])

def test_normalize_legacy_does_not_allocate_and_aggregate_is_not_a_witness():
    state, geometry = actual()
    assert TOKEN_KEY not in api.normalize_box_body_structure_state(state)
    body = geometry.parts[0].render_data
    aggregate = replace(geometry, parts=(replace(geometry.parts[0],render_data=body.preview_render_data),))
    with pytest.raises(ValueError,match="PHYSICAL_IDENTITY_UNPROVEN"):
        propose(state, KEYS[0], aggregate)
