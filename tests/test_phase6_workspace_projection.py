from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace


def _canonical_shared():
    return {
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {"head": {"X": [{"len": 11.0}], "Y": []}},
        "box_body_structure": {"schema_version": 1, "active_type": "INTEGRAL", "locked": False, "configs": {}},
    }


def test_main_project_compose_uses_workspace_owner_for_all_four_shared_fields():
    import gui

    canonical = _canonical_shared()
    canonical["box_body_profile"] = [{"phase6_key": "w", "len": 400.0}]

    class WorkspaceOwner:
        def workspace_snapshot(self):
            return deepcopy(canonical)

    fake = SimpleNamespace(
        workspace_controller=WorkspaceOwner(),
        endcap_fw_state={"mode": "LINKED"},
        endcap_bottom_wrap_state={"mode": "LINKED"},
    )
    fake._make_original_fold_designer_snapshot = lambda: {
        "existing_parts": ["box_body", "door"],
        "active_part": "door",
        "part_profiles": {"door": {"X": [{"len": 999.0}], "Y": []}},
        "box_body_profile": [{"phase6_key": "w", "len": 999.0}],
        "workspace": {"box_body_structure": {"active_type": "BROKEN"}},
    }

    result = gui.BoxCalculatorGUI._compose_phase6_project_snapshot_from_main_gui(fake)
    workspace = result["workspace"]
    for key in ("existing_parts", "active_part", "part_profiles", "box_body_structure"):
        assert workspace[key] == canonical[key]


def test_designer_owner_exports_live_active_profile_without_mutating_stash():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {"head": {"X": [{"len": 11.0}], "Y": []}},
    })
    exported = ws.export_shared_snapshot(
        live_active_profiles={"X": [{"len": 33.0}], "Y": []}
    )
    assert exported["part_profiles"]["head"]["X"][0]["len"] == 33.0
    assert ws.profiles_for("head")["X"][0]["len"] == 11.0
    assert tuple(exported) == ("existing_parts", "active_part", "part_profiles", "box_body_structure")


def test_bridge_collects_shared_fields_through_designer_owner_export_seam():
    import fold_designer_bridge as bridge

    canonical = _canonical_shared()

    class DesignerOwner:
        active_part = "head"
        def export_shared_snapshot(self, *, live_active_profiles=None):
            result = deepcopy(canonical)
            if live_active_profiles is not None:
                result["part_profiles"]["head"] = deepcopy(live_active_profiles)
            return result
        def box_body_structure_state(self):
            raise AssertionError("adapter should not rebuild shared structure")

    holder = SimpleNamespace(
        designer_workspace=DesignerOwner(),
        state=SimpleNamespace(
            profiles={"X": [{"len": 55.0}], "Y": []},
            profiles_vault={"箱身": [{"phase6_key": "w", "len": 400.0}]},
        ),
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_endcap_fw_state={},
        _phase6_input_snapshot={"fw": 25.0},
    )
    result = bridge._phase6_collect_workspace_state(holder)
    assert result["existing_parts"] == canonical["existing_parts"]
    assert result["active_part"] == "head"
    assert result["part_profiles"]["head"]["X"][0]["len"] == 55.0
    assert result["box_body_structure"] == canonical["box_body_structure"]


def test_bridge_compatibility_properties_delegate_through_designer_owner_api():
    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    assert "_designer_workspace(self)._" not in source
