from dataclasses import replace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.operator_box_body_piece_marking import open_box_body_piece_marking_draft as opened
from ae_engine.operator_manual_marking import _build_manual_round_feature, _build_manual_straight_feature
from ae_engine.operator_root_marking_store import ROOT_MARKING_STORE_KEY, project_operator_detached_root_marking_count
from ae_engine.physical_sheet_editor_context import resolve_box_body_piece_manufacturing_witness
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.workspace_state import SharedWorkspaceState
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3414_box_body_piece_marking_occupancy import KEYS, actual

def case():
    state, geometry = actual()
    ws = SharedWorkspaceState(box_body_structure=state)
    def read():
        return {"model":"受電箱","t":2.,**ws.snapshot()}, geometry
    return ws, read

def marks(geometry, key):
    _, stock = resolve_box_body_piece_manufacturing_witness(geometry,key)
    centre = stock.material.representative_point()
    return (_build_manual_straight_feature(Vec2(centre.x-8,centre.y),5.,0.,"solid",10.,5.),
            _build_manual_round_feature(Vec2(centre.x+8,centre.y),5.))

def reload_project(path, snap):
    return read_project(write_project(path, {"schema":PROJECT_SCHEMA,
        "saved_at":"2026-11-27T02:05:00+08:00","snapshot":snap}))["snapshot"]

def test_three_actual_sheets_marks_roundtrip_replacement_keeps_old_unbound(tmp_path):
    ws, read = case()
    old = {}
    for key in KEYS:
        s,g = read()
        draft = opened(s,g,key)
        assert draft.owner_id is None
        assert ws.commit_box_body_piece_marking(draft,marks(g,key),read_current=read)
        old[key] = opened(*read(),key)
        assert len(old[key].saved_marks) == 2
    s,g = read()
    saved = reload_project(tmp_path/"markings.p6fold",s)
    assert saved["existing_parts"] == ["box_body"]
    assert [opened(saved,g,key) for key in KEYS] == list(old.values())
    assert project_operator_detached_root_marking_count(saved) == 0
    assert len(saved[ROOT_MARKING_STORE_KEY]["records"]) == 3
    ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"integral",800))
    ws.set_box_body_structure_state(api.activate_structure_with_defaults(ws.box_body_structure_state(),"three_piece_side_back_split",800))
    after = reload_project(tmp_path/"replacement.p6fold",read()[0])
    assert after[ROOT_MARKING_STORE_KEY] == saved[ROOT_MARKING_STORE_KEY]
    assert project_operator_detached_root_marking_count(after) == 3
    for k in KEYS:
        assert opened(after,g,k).saved_marks == ()
    with pytest.raises(ValueError,match="ROOT_MARKING_OWNER_STALE"):
        ws.commit_box_body_piece_marking(old[KEYS[0]],old[KEYS[0]].saved_marks,read_current=read)
    assert read()[0][ROOT_MARKING_STORE_KEY] == saved[ROOT_MARKING_STORE_KEY]

def test_empty_ineligible_or_stale_draft_does_not_allocate():
    ws, read = case()
    s,g = read()
    k = KEYS[0]
    initial = opened(s,g,k)
    before = ws.snapshot()
    assert not ws.commit_box_body_piece_marking(initial,(),read_current=read)
    with pytest.raises(ValueError, match="SCOPE_UNSUPPORTED"):
        opened({**s,"model":"金庫型"},g,k)
    body = g.parts[0].render_data
    lookalike = replace(g,parts=(replace(g.parts[0],render_data=body.preview_render_data),))
    with pytest.raises(ValueError,match="PHYSICAL_IDENTITY_UNPROVEN"):
        ws.commit_box_body_piece_marking(initial,marks(g,k),read_current=lambda:(s,lookalike))
    assert ws.snapshot() == before

def test_commit_rechecks_live_source_before_assignment():
    ws, read = case()
    s,g = read()
    k = KEYS[0]
    initial = opened(s,g,k)
    before = ws.snapshot()
    revisions = iter([(s,g),({**s,"t":3.},g)])
    with pytest.raises(ValueError,match="ROOT_MARKING_WORKSPACE_STALE"):
        ws.commit_box_body_piece_marking(initial,marks(g,k),read_current=lambda:next(revisions))
    assert ws.snapshot() == before


def test_public_structural_modal_reuses_real_stock_tools_without_claiming_other_piece():
    ws, read = case()
    snapshot, geometry = read()
    left, _, right = KEYS
    before = ws.snapshot()
    draft, modal = api.open_box_body_piece_marking_modal_source(snapshot, geometry, left)
    _, render = resolve_box_body_piece_manufacturing_witness(geometry, left)
    assert modal.context.render_data is render
    assert modal.context.part_key == left
    centre = render.material.representative_point()
    line = api.create_physical_sheet_mark(
        modal, (), tool="line", midpoint=Vec2(centre.x - 8, centre.y),
        length=5., angle_deg=0.,
    )
    circle = api.create_physical_sheet_mark(
        modal, (line,), tool="circle", centre=Vec2(centre.x + 8, centre.y),
        diameter=5.,
    )
    accepted = api.validate_physical_sheet_marking_draft(modal, (line,circle))
    assert accepted == (line,circle)
    assert ws.snapshot() == before
    assert ws.commit_box_body_piece_marking(draft,accepted,read_current=read)
    again, opened_left = api.open_box_body_piece_marking_modal_source(*read(), left)
    untouched, opened_right = api.open_box_body_piece_marking_modal_source(*read(), right)
    assert again.saved_marks == (line,circle)
    assert opened_left.owner_id != opened_right.owner_id
    assert not untouched.saved_marks and untouched.owner_id is None
    assert opened_right.context.render_data is not opened_left.context.render_data
    with pytest.raises(ValueError):
        api.create_physical_sheet_mark(
            opened_right, (), tool="circle", centre=Vec2(-1000., -1000.), diameter=5.,
        )


def test_workspace_editor_binding_uses_current_child_and_one_confirm(monkeypatch):
    from types import SimpleNamespace
    from gui_modules.application import physical_part_hole_editor as editor
    from phase6_designer_workspace import Phase6DesignerWorkspace
    import phase6_manufacturing_adapter

    shared, read = case()
    snapshot, geometry = read()
    left, _, right = KEYS
    ws = Phase6DesignerWorkspace(shared_state=shared, active_mode="set_bay")
    ws.replace_available_parts(("box_body", *KEYS))
    body = geometry.part("box_body").render_data
    monkeypatch.setattr(phase6_manufacturing_adapter, "build_scene_payload_for_app",
                        lambda app, key: {"model":"受電箱"})
    app = SimpleNamespace(
        designer_workspace=ws, _phase6_input_snapshot=snapshot,
        _phase6_resolve_manufacturing_geometry=lambda: geometry,
        _phase6_publish_live_state=lambda *, force: None,
    )
    host = SimpleNamespace(
        fold_designer_app=app, project_controller=SimpleNamespace(project_load_epoch=1),
        _query_fold_designer_render_data=lambda key,payload: body,
        _open_unified_hole_editor=lambda key,*args,**kwargs: (key,kwargs),
    )
    assert left in ws.available_parts and right in ws.available_parts
    before = ws.snapshot()
    key,left_window = editor.open_workspace_sheet_editor(host,left)
    assert key == left
    assert left_window["manual_marking_draft"].context.part_key == left
    assert left_window["feature_list_override"] == []
    assert ws.snapshot() == before  # open/Cancel has no commit
    left_window["on_confirm_features"](marks(geometry,left))
    after = ws.snapshot()
    expected, _ = api.open_box_body_piece_marking_modal_source(*read(), left)
    assert len(expected.saved_marks) == 2
    key,right_window = editor.open_workspace_sheet_editor(host,right)
    assert key == right
    assert right_window["manual_marking_draft"].context.part_key == right
    assert right_window["feature_list_override"] == []
    assert ws.snapshot() == after
    host.project_controller.project_load_epoch += 1
    with pytest.raises(ValueError,match="PHYSICAL_MARK_PROJECT_SESSION_STALE"):
        right_window["on_confirm_features"](marks(geometry,right))
    assert ws.snapshot() == after


def test_public_drawing_view_projects_only_source_bound_user_delta():
    ws, read = case()
    s,g = read()
    left, _, right = KEYS
    _, stock = resolve_box_body_piece_manufacturing_witness(g,left)
    _, other = resolve_box_body_piece_manufacturing_witness(g,right)
    assert api.project_workspace_owner_marking_display(s,left,stock,resolve_geometry=lambda:g) is stock
    assert ws.commit_box_body_piece_marking(opened(s,g,left),marks(g,left),read_current=read)
    s,g = read()
    view = api.project_workspace_owner_marking_display(s,left,stock,resolve_geometry=lambda:g)
    assert tuple(view.scene.primitives[:-2]) == tuple(stock.scene.primitives)
    assert [p.layer for p in view.scene.primitives[-2:]] == ["MARKING", "MARKING"]
    assert view.metadata[api.OWNER_MARKING_VIEW_ONLY] is True
    assert api.project_workspace_owner_marking_display(s,right,other,resolve_geometry=lambda:g) is other
    stale = api.project_workspace_owner_marking_display(s,left,other,resolve_geometry=lambda:g)
    assert stale.metadata[api.OWNER_MARKING_VIEW_DIAGNOSTIC] == "ROOT_MARKING_DISPLAY_SOURCE_MISMATCH"
    assert stale.scene is other.scene
