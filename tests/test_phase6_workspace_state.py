from copy import deepcopy
from pathlib import Path

import pytest


def test_normalize_existing_parts_is_deterministic_and_keeps_box_body():
    from phase6_workspace_state import normalize_existing_parts

    raw = [" door ", "tail", "", "head", "door", "custom_b", "custom_a", "box_body"]
    assert normalize_existing_parts(raw) == (
        "box_body", "head", "tail", "door", "custom_b", "custom_a",
    )


def test_active_repair_policies_are_explicit():
    from phase6_workspace_state import SharedWorkspaceState

    first = SharedWorkspaceState(existing_parts=["head"], active_part="missing", active_repair="first")
    assert first.active_part == "box_body"

    none = SharedWorkspaceState(existing_parts=["head"], active_part="missing", active_repair="none")
    assert none.active_part is None

    with pytest.raises(ValueError, match="active_part"):
        SharedWorkspaceState(existing_parts=["head"], active_part="missing", active_repair="raise")


def test_presence_changes_preserve_profile_stash_and_repair_active_by_owner_policy():
    from phase6_workspace_state import SharedWorkspaceState

    state = SharedWorkspaceState(
        existing_parts=["box_body", "head", "tail"],
        active_part="tail",
        part_profiles={"tail": {"Y": [{"len": 33.0}]}},
        active_repair="first",
    )
    state.set_part_presence("tail", False, active_repair="first")
    assert state.existing_parts == ("box_body", "head")
    assert state.active_part == "box_body"
    assert state.profile_for("tail") == {"Y": [{"len": 33.0}]}

    state.set_part_presence("tail", True, active_repair="first")
    assert state.profile_for("tail") == {"Y": [{"len": 33.0}]}


def test_snapshot_is_defensive_and_structure_is_canonicalized():
    from phase6_workspace_state import SharedWorkspaceState
    from phase6_box_body_structure import BoxBodyStructureType

    source_profiles = {"head": {"X": [{"len": 12.0}]}}
    source_structure = {"active_type": BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value}
    state = SharedWorkspaceState(
        existing_parts=["head"],
        active_part="head",
        part_profiles=source_profiles,
        box_body_structure=source_structure,
        active_repair="first",
    )
    source_profiles["head"]["X"][0]["len"] = 999.0
    source_structure["active_type"] = "BROKEN"

    snap = state.snapshot()
    snap["part_profiles"]["head"]["X"][0]["len"] = 777.0
    snap["box_body_structure"]["active_type"] = "BROKEN"

    assert state.profile_for("head")["X"][0]["len"] == 12.0
    assert state.box_body_structure_state()["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value


def test_shared_core_has_only_shared_fields_and_no_forbidden_dependencies():
    import phase6_workspace_state

    source = Path(phase6_workspace_state.__file__).read_text(encoding="utf-8")
    forbidden_imports = (
        "tkinter", "phase6_project_session", "phase6_project_controller",
        "fold_designer_bridge", "renderer", "manufacturing_api", "ae_engine",
    )
    assert not [name for name in forbidden_imports if name in source]

    state = phase6_workspace_state.SharedWorkspaceState()
    assert not hasattr(state, "selected_part")
    assert not hasattr(state, "dirty")
    assert not hasattr(state, "switching")
    assert not hasattr(state, "part_features")
    assert not hasattr(state, "box_body_profile")


def test_main_and_designer_use_independent_shared_state_instances_and_same_normalization():
    from phase6_workspace_controller import Phase6WorkspaceController
    from phase6_designer_workspace import Phase6DesignerWorkspace

    raw = {
        "existing_parts": ["door", "head", "door", "custom", ""],
        "active_part": "missing",
        "part_profiles": {"door": {"X": [{"len": 22.0}], "Y": []}},
    }
    main = Phase6WorkspaceController(default_existing_parts=[])
    main.commit_workspace(deepcopy(raw))
    designer = Phase6DesignerWorkspace.from_snapshot(deepcopy(raw))

    assert main.workspace_snapshot()["existing_parts"] == list(designer.available_parts)
    assert main.workspace_snapshot()["existing_parts"] == ["box_body", "head", "door", "custom"]
    assert main.active_part == "box_body"
    assert designer.active_part is None
    assert main._shared_state is not designer._shared_state
