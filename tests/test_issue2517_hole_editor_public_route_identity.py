"""#2517: real Hole Editor entry routes via Engine public physical identity."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.physical_part_identity import (
    OperatorHoleEditorRoute, project_operator_hole_editor_route,
)
from gui_modules.editors import hole_editor as gui


@pytest.mark.parametrize("part,model,multi,connected,kind,indices", (
    ("head", "金庫型", False, False, "endcap", (None, None)),
    ("tail", "受電箱", False, False, "endcap", (None, None)),
    ("door_c1_r2", "金庫型", False, True, "door_cell", (0, 1)),
    ("door_c3_r11", "受電箱", False, True, "door_cell", (2, 10)),
    ("box_body:back", "金庫型", False, True, "workspace_sheet", (None, None)),
    ("box_body:right_side", "受電箱", False, True, "workspace_sheet", (None, None)),
    ("box_body:divider:vertical:1", "金庫型", False, True, "workspace_sheet", (None, None)),
    ("base_plate:fixing_plate:nfb_layer:0:left", "受電箱", False, True, "workspace_sheet", (None, None)),
    ("base_plate_c1_r1", "受電箱", False, True, "workspace_sheet", (None, None)),
    ("custom:17", "金庫型", False, True, "workspace_sheet", (None, None)),
    ("inner_door:bay1_frame", "受電箱", False, True, "workspace_sheet", (None, None)),
    ("inner_door:bay1:panel", "受電箱", False, True, "inner_door_panel", (None, None)),
    ("box_body", "金庫型", False, True, "box_body_face", (None, None)),
    ("door", "金庫型", "false", True, "simple_part", (None, None)),
    ("door", "金庫型", "true", True, "selected_door_cell", (None, None)),
    ("base_plate", "受電箱", False, True, "workspace_sheet", (None, None)),
    ("base_plate", "RECEIVING", False, True, "workspace_sheet", (None, None)),
    ("base_plate", "受電箱", False, False, "simple_part", (None, None)),
    ("base_plate", "金庫型", False, True, "simple_part", (None, None)),
    ("indicator_box", "受電箱", False, True, "simple_part", (None, None)),
    ("indicator_door", "金庫型", False, True, "simple_part", (None, None)),
))
def test_public_engine_route_preserves_canonical_part_role_and_cell_indices(
    part, model, multi, connected, kind, indices
):
    route = api.project_operator_hole_editor_route(
        part, model=model,
        multi_door_enabled=multi, has_fold_designer=connected,
    )
    assert isinstance(route, OperatorHoleEditorRoute)
    assert route.kind == kind
    assert route.part_key == part
    assert (route.column_index, route.row_index) == indices
    assert api.project_operator_hole_editor_route is project_operator_hole_editor_route
    assert ae_engine.project_operator_hole_editor_route is project_operator_hole_editor_route


@pytest.mark.parametrize("part", ("door_c0_r1", "door_c1_r0", "unknown_part", "door_c1_r-1", "", None, True))
def test_unknown_or_zero_door_cell_identity_rejected_before_working_on_part(part):
    with pytest.raises(ValueError, match="HOLE_EDITOR_"):
        api.project_operator_hole_editor_route(part, model="受電箱")


@pytest.mark.parametrize("bad", ("maybe", 2, 1.5, None, float("nan")))
def test_invalid_persisted_multi_door_flag_cannot_enable_editor_route(bad):
    with pytest.raises(ValueError, match="布林值"):
        api.project_operator_hole_editor_route(
            "door", model="受電箱", multi_door_enabled=bad,
        )


def _host(part_model="受電箱", *, multi=False, connected=False):
    events = []
    workspace = SimpleNamespace(set_active_part=lambda part: events.append(("active", part)))
    host = SimpleNamespace(
        workspace_controller=workspace,
        baseline_var=SimpleNamespace(get=lambda: part_model),
        multi_door_enabled_var=SimpleNamespace(get=lambda: multi),
        fold_designer_app=SimpleNamespace() if connected else None,
    )
    return host, events


def test_actual_gui_endcap_uses_engine_route_before_active_mutation(monkeypatch):
    host, events = _host("金庫型")
    monkeypatch.setattr(gui, "open_hole_editor",
                        lambda owner, part: events.append(("endcap", part)) or "opened")
    assert gui.open_part_hole_editor(host, "head") == "opened"
    assert events == [("active", "head"), ("endcap", "head")]


def test_actual_gui_door_cell_decodes_exact_engine_indices(monkeypatch):
    host, events = _host()
    host.open_door_layout_cell_editor = (
        lambda c, r: events.append(("cell", c, r)) or "cell-opened"
    )
    assert gui.open_part_hole_editor(host, "door_c3_r2") == "cell-opened"
    assert events == [("active", "door_c3_r2"), ("cell", 2, 1)]


def test_actual_gui_workspace_editor_receives_physical_identity(monkeypatch):
    from gui_modules.application import physical_part_hole_editor as target
    host, events = _host(connected=True)
    monkeypatch.setattr(
        target, "open_workspace_sheet_editor",
        lambda owner, part: events.append(("workspace", part)) or "workspace-opened",
    )
    assert gui.open_part_hole_editor(host, "base_plate") == "workspace-opened"
    assert events == [("active", "base_plate"), ("workspace", "base_plate")]


def test_actual_gui_box_body_face_keeps_only_presentation_selection(monkeypatch):
    host, events = _host("金庫型")
    host.box_body_face_features = {}
    host.box_body_face_selected_var = SimpleNamespace(get=lambda: "right")
    host.open_box_body_face_editor = lambda face: events.append(("face", face)) or "face-opened"
    assert gui.open_part_hole_editor(host, "box_body") == "face-opened"
    assert events == [("active", "box_body"), ("face", "right")]
    assert set(host.box_body_face_features) == {"left", "back", "right"}


def test_actual_gui_inner_door_panel_routes_to_existing_editor(monkeypatch):
    from gui_modules.application import receiving_inner_door_hole_editor as target
    host, events = _host(connected=True)
    monkeypatch.setattr(
        target, "open_inner_door_hole_editor",
        lambda app, key, *, from_part_preview: (
            events.append(("inner", key, from_part_preview)) or "inner-opened"
        ),
    )
    assert gui.open_part_hole_editor(host, "inner_door:set1:panel") == "inner-opened"
    assert events == [
        ("active", "inner_door:set1:panel"),
        ("inner", "inner_door:set1:panel", True),
    ]


def test_actual_gui_selected_door_cell_consumes_engine_flag_no_truthy_false(monkeypatch):
    host, events = _host(multi="true")
    host.get_selected_door_layout_cell = lambda: SimpleNamespace(
        column_index=2, row_index=1,
    )
    host.open_door_layout_cell_editor = (
        lambda c, r: events.append(("cell", c, r)) or "opened"
    )
    assert gui.open_part_hole_editor(host, "door") is None
    assert events == [("active", "door"), ("cell", 2, 1)]


@pytest.mark.parametrize("part,multi", (
    ("door_c0_r2", False), ("unknown_part", False),
    ("head", "maybe"), ("door", "maybe"),
))
def test_invalid_gui_physical_route_does_not_touch_workspace(monkeypatch, part, multi):
    host, events = _host(multi=multi)
    warnings = []
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, message: warnings.append((title, message)))
    assert gui.open_part_hole_editor(host, part) is None
    assert events == []
    assert len(warnings) == 1
    assert "HOLE_EDITOR_" in warnings[0][1] or "布林值" in warnings[0][1]


def test_gui_no_longer_owns_manufacturing_part_prefix_family_or_door_cell_parsing():
    code = inspect.getsource(gui.open_part_hole_editor)
    assert "manufacturing_api.project_operator_hole_editor_route(" in code
    assert "route.kind" in code
    assert ".startswith((" not in code
    assert "re.fullmatch(" not in code
    assert "host.baseline_var.get() == '受電箱'" not in code
    assert "multi_door_enabled_var.get():" not in code
