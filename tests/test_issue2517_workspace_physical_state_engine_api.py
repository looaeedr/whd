"""#2517: physical Workspace state must have one Engine owner for all clients."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
import phase6_workspace_state as legacy
from phase6_workspace_controller import Phase6WorkspaceController
from phase6_designer_workspace import Phase6DesignerWorkspace


def test_public_engine_workspace_exports_exact_same_canonical_objects():
    assert legacy.SharedWorkspaceState is manufacturing_api.SharedWorkspaceState
    assert legacy.normalize_existing_parts is manufacturing_api.normalize_existing_parts
    assert legacy.MANDATORY_PART == manufacturing_api.MANDATORY_PART == "box_body"
    assert legacy.PART_ORDER is manufacturing_api.PART_ORDER


def test_main_and_designer_share_api_but_not_mutable_physical_state():
    initial = {
        "existing_parts": ["head", "box_body", "tail"],
        "active_part": "tail",
        "part_profiles": {"tail": {"Y": [{"len": 12.0}]}},
    }
    main = Phase6WorkspaceController()
    main.commit_workspace(deepcopy(initial))
    designer = Phase6DesignerWorkspace.from_snapshot(deepcopy(initial))
    assert type(main._shared_state) is manufacturing_api.SharedWorkspaceState
    assert type(designer._shared_state) is manufacturing_api.SharedWorkspaceState
    assert main._shared_state is not designer._shared_state
    main.set_part_presence("tail", False)
    assert main.active_part == "box_body"
    assert "tail" in designer.available_parts
    assert main.profile_for("tail") == {"Y": [{"len": 12.0}]}


def test_public_engine_rejects_unbacked_custom_physical_identity():
    state = manufacturing_api.SharedWorkspaceState()
    before = state.snapshot()
    with pytest.raises(ValueError, match="metadata"):
        state.set_part_presence("custom:1", True, active_repair="first")
    assert state.snapshot() == before


def test_public_engine_custom_id_survives_remove_and_readd():
    state = manufacturing_api.SharedWorkspaceState()
    key = state.add_custom_part(
        display_name="左側彎片", fold_axis="X", transverse_length=110.0,
    )
    assert key == "custom:1"
    snap = state.snapshot()
    assert key in snap["existing_parts"] and snap["custom_parts"]["items"][key]
    state.set_part_presence(key, False, active_repair="first")
    assert key not in state.snapshot()["existing_parts"]
    new_key = state.add_custom_part(
        display_name="右側彎片", fold_axis="Y", transverse_length=90.0,
    )
    assert new_key == "custom:2"
