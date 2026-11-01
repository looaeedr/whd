"""#2517: GUI physical identity/namespace synchronization is Engine-owned."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect

import pytest

from ae_engine import (
    DerivedPartProjectionRequest, DerivedPartRequestAssemblyInput,
    DerivedPartSyncPlan, build_derived_part_projection_request,
    build_derived_part_sync_plan, manufacturing_api,
)
from ae_engine import derived_part_projection as engine
import phase6_derived_part_projection as legacy
from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController


def request(*, receiving=False, door_keys=("door_c1_r1", "door_c1_r2")):
    return engine.DerivedPartRequestAssemblyInput(
        door_part_keys=door_keys,
        door_profiles={"door_c1_r1": {"X": [{"len": 100.0}]}},
        base_plate_profiles={"base_plate_c1_r1": {"X": [{"len": 90.0}]}},
        divider_profiles={"box_body:divider:1": {"X": [{"len": 20.0}]}},
        inner_profiles={"inner_door:1": {"Y": [{"len": 50.0}]}},
        box_piece_profiles={"box_body:left": {"X": [{"len": 22.0}]}},
        current_piece_keys=("box_body:old",),
        source_parts=("box_body", "door", "base_plate"),
        available_parts=("box_body", "door", "base_plate", "box_body:left"),
        source_part_features={"door_c1_r1": [{"kind": "saved"}]},
        known_feature_keys=(),
        single_door_profiles={"X": [{"len": 800.0}]},
        single_base_plate_profiles={"X": [{"len": 690.0}]},
        active_part="base_plate" if not receiving else "base_plate_c1_r2",
        selected_part="door",
        preserve_single_base_plate=receiving,
    )


@pytest.mark.parametrize("receiving", [False, True])
def test_engine_public_request_and_legacy_alias_share_one_physical_owner(receiving):
    source = request(receiving=receiving)
    original = deepcopy(source)
    projected = manufacturing_api.build_derived_part_projection_request(source)
    assert isinstance(projected, DerivedPartProjectionRequest)
    assert projected == engine.build_derived_part_projection_request(source)
    assert projected == legacy.build_derived_part_projection_request(source)
    assert build_derived_part_projection_request is engine.build_derived_part_projection_request
    plan = manufacturing_api.build_derived_part_sync_plan(projected)
    assert isinstance(plan, DerivedPartSyncPlan)
    assert plan == build_derived_part_sync_plan(projected)
    assert plan == legacy.build_derived_part_sync_plan(projected)
    assert source == original

    assert [p.namespace for p in plan.namespaces] == [
        "door_c", "base_plate_c", "box_body:divider:", "inner_door:"
    ]
    assert "door" in plan.remove_part_keys
    assert "box_body:old" in plan.remove_part_keys
    assert [p.part_key for p in plan.stash_features] == ["door_c1_r1"]
    assert plan.selected_part_repair == "door_c1_r1"
    if receiving:
        assert "base_plate" not in plan.remove_part_keys
        assert plan.active_part_repair == "base_plate"
        assert plan.namespaces[1].parts == ()
    else:
        assert "base_plate" in plan.remove_part_keys
        assert plan.active_part_repair == "base_plate_c1_r1"
        assert [p.part_key for p in plan.namespaces[1].parts] == ["base_plate_c1_r1"]

    assert engine.materialize_profiles(plan.namespaces[0].parts[0]) == {
        "X": [{"len": 100.0}]
    }
    with pytest.raises(FrozenInstanceError):
        plan.active_part_repair = "different"


def test_single_door_reactivation_preserves_stash_without_extra_part_identity():
    source = request(door_keys=())
    source = engine.DerivedPartRequestAssemblyInput(
        **{**source.__dict__, "available_parts": ("box_body",),
           "current_piece_keys": (), "source_parts": ("door", "base_plate")}
    )
    plan = manufacturing_api.build_derived_part_sync_plan(
        manufacturing_api.build_derived_part_projection_request(source)
    )
    assert [p.part_key for p in plan.add_parts][:2] == ["door", "base_plate"]
    assert [p.part_key for p in plan.stash_profiles][:2] == ["door", "base_plate"]
    assert engine.materialize_profiles(plan.stash_profiles[0]) == {
        "X": [{"len": 800.0}]
    }


def test_gui_module_is_compat_only_and_workspace_owner_still_applies_plan():
    assert legacy.DerivedPartSyncPlan is manufacturing_api.DerivedPartSyncPlan
    assert legacy.DerivedPartRequestAssemblyInput is manufacturing_api.DerivedPartRequestAssemblyInput
    assert legacy.materialize_profiles is manufacturing_api.materialize_profiles
    assert inspect.getsource(legacy).find("def build_derived_part_projection_request(") < 0
    assert "manufacturing_api" not in inspect.getsource(legacy)
    from gui_modules.application import fold_designer_composition_shell_settings as comp
    assert comp.build_derived_part_projection_request is manufacturing_api.build_derived_part_projection_request
    assert comp.build_derived_part_sync_plan is manufacturing_api.build_derived_part_sync_plan
    source = inspect.getsource(Phase6WorkspaceNavigationController.apply_derived_sync_plan)
    assert "self.sync_derived_parts(" in source
    assert "self.remove_part(" in source
    assert "manufacturing_api" not in inspect.getsource(engine)
