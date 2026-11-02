"""#2517: GUI checkbox selection must consume Engine physical identities."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.parts.panels.common import logical_part_present as gui_present
from gui_modules.project.export_actions import _selected_export_flags


def _requested(**edits):
    intents = {
        "box_body": True, "head": True, "tail": True, "door": True,
        "base_plate": True, "indicator_box": True, "indicator_door": True,
    }
    intents.update(edits)
    return intents


def test_real_two_tier_nfb_sources_extend_old_gui_presence_mirror():
    existing = {"box_body"}
    workspace = ("inner_door:upper:panel", "base_plate:nfb_layer:0",
                 "base_plate:nfb_layer:1")
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    flags = manufacturing_api.selected_project_export_flags(
        snapshot, existing, workspace, _requested(), has_indicator_box=False,
    )
    assert flags == {
        "box_body": True, "head": False, "tail": False, "door": True,
        "base_plate": True, "indicator_box": False, "indicator_door": False,
    }
    assert existing == {"box_body"}


@pytest.mark.parametrize("snapshot", [
    {"model": "受電箱", "nfb_config_submitted": False},
    {"model": "受電箱"},
    {"model": "金庫型", "nfb_config_submitted": True},
    {"model": "unregistered-family", "nfb_config_submitted": True},
])
def test_missing_or_wrong_family_submission_cannot_borrow_workspace_nfb(snapshot):
    flags = manufacturing_api.selected_project_export_flags(
        snapshot, ("box_body",),
        ("inner_door:upper:panel", "base_plate:nfb_layer:0"),
        _requested(),
    )
    assert flags["box_body"]
    assert not flags["door"]
    assert not flags["base_plate"]


@pytest.mark.parametrize("physical", [
    ("base_plate:fixing_plate:nfb_layer:0:left",),
    ("base_plate:nfb_pad:layer:1",),
    ("base_plate:nfb_layer:9",),
])
def test_non_base_physical_id_cannot_create_exportable_base(physical):
    assert not manufacturing_api.logical_part_present(physical, "base_plate")
    assert not gui_present(physical, "base_plate")
    flags = manufacturing_api.selected_project_export_flags(
        {"model": "受電箱", "nfb_config_submitted": True},
        (), physical, _requested(),
    )
    assert not flags["base_plate"]


@pytest.mark.parametrize("parts,role", [
    (("door_c1_r1",), "door"),
    (("inner_door:upper:panel",), "door"),
    (("base_plate_c1_r1",), "base_plate"),
    (("base_plate:nfb_layer:1",), "base_plate"),
    (("box_body:left_side",), "box_body"),
])
def test_existing_family_physical_role_compatibility(parts, role):
    assert manufacturing_api.logical_part_present(parts, role)
    assert gui_present(parts, role)


def test_old_primary_checkbox_root_and_indicator_checks_unchanged():
    flags = manufacturing_api.selected_project_export_flags(
        {"model": "金庫型"}, ("box_body:left_side", "door_c1_r1", "indicator_box",
                          "indicator_door"), (), _requested(),
        has_indicator_box=True,
    )
    assert not flags["box_body"]
    assert flags["door"]
    assert flags["indicator_box"] and flags["indicator_door"]
    assert not flags["base_plate"]


def test_original_gui_action_forwards_only_selections_to_engine(monkeypatch):
    class V:
        def __init__(self, flag):
            self.flag = flag
        def get(self):
            return self.flag
    observed = []
    sentinel = {"door": True, "base_plate": True}
    def engine(snapshot, existing, available, selected, *, has_indicator_box):
        observed.append((snapshot, existing, available, selected, has_indicator_box))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "selected_project_export_flags", engine)
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    workspace = SimpleNamespace(available_parts=("base_plate:nfb_layer:0",))
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=snapshot, designer_workspace=workspace,
        ),
        export_z_var=V(True), export_head_var=V(False), export_tail_var=V(False),
        export_door_var=V(True), export_base_plate_var=V(True),
        export_ib_var=V(False), export_ib_door_var=V(False),
    )
    assert _selected_export_flags(host, {"box_body"}, False) is sentinel
    assert observed[0][:3] == (snapshot, {"box_body"}, workspace.available_parts)
    assert observed[0][3] == _requested(head=False, tail=False,
                                        indicator_box=False, indicator_door=False)
    assert not observed[0][4]


def test_engine_selection_has_no_gui_reverse_import_and_gui_no_physical_id_rules():
    root = Path(__file__).resolve().parents[1]
    engine = (root / "ae_engine/manufacturing_export_selection.py").read_text("utf-8")
    common = (root / "gui_modules/parts/panels/common.py").read_text("utf-8")
    gui = (root / "gui_modules/project/export_actions.py").read_text("utf-8")
    assert "from gui_modules" not in engine
    assert "startsWith" not in common
    assert "inner_door:" not in common
    assert "base_plate:nfb_layer:" not in common
    assert "base_plate:nfb_layer:" not in gui.split("def _selected_export_flags")[1].split("def _validate_selected_indicator_exports")[0]


def test_operator_flags_require_request_mapping():
    with pytest.raises(TypeError, match="PROJECT_EXPORT_OPERATOR_FLAGS_REQUIRED"):
        manufacturing_api.selected_project_export_flags({}, (), (), ("door",))
