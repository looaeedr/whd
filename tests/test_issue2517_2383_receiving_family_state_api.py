"""#2517/#2383: Receiving physical 3-sheet Family state is a public Engine API."""
from __future__ import annotations

from copy import deepcopy
import inspect

from ae_engine import manufacturing_api, resolve_receiving_box_body_structure_state
from ae_engine.box_body_structure_state import default_box_body_structure_state
from ae_engine.cabinet_types import receiving
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_spec_from_trusted_part,
)
from tests.test_issue2383_receiving_side_panel_worker_api import _part


def _side_cfg(state):
    return state["configs"]["three_piece_side_back_split"]


def test_fresh_receiving_side_back_state_is_engine_owned_and_source_immutable():
    state = resolve_receiving_box_body_structure_state(None)
    assert resolve_receiving_box_body_structure_state is manufacturing_api.resolve_receiving_box_body_structure_state
    assert resolve_receiving_box_body_structure_state is receiving.resolve_box_body_structure_state
    assert state["active_type"] == "three_piece_side_back_split"
    assert state["locked"] is True
    assert _side_cfg(state)["side_rear_bend"] == 18.0
    assert _side_cfg(state)["side_rear_bend_dimension_space"] == "OUTSIDE"
    assert _side_cfg(state)["back_width_comp_t"] == 2.5
    assert _side_cfg(state)["back_panel_mode"] == "FULL"


def test_legacy_receiving_state_preserves_original_material_rear_bend():
    original = default_box_body_structure_state()
    original["active_type"] = "three_piece_side_back_split"
    config = _side_cfg(original)
    config["side_rear_bend"] = 15.0
    config["back_panel_mode"] = "BACK_OPENING"
    config.pop("side_rear_bend_dimension_space", None)
    preserved = deepcopy(original)
    result = resolve_receiving_box_body_structure_state(original)
    assert original == preserved
    assert _side_cfg(result)["side_rear_bend"] == 15.0
    assert _side_cfg(result)["side_rear_bend_dimension_space"] == "MATERIAL"
    assert _side_cfg(result)["back_width_comp_t"] == 2.5
    assert _side_cfg(result)["back_panel_mode"] == "BACK_OPENING"


def test_real_receiving_side_worker_uses_public_engine_family_state():
    expected = resolve_receiving_box_body_structure_state(None)
    for role in ("left_side", "right_side"):
        spec, actual_role = receiving_side_panel_spec_from_trusted_part(_part(role))
        assert actual_role == role
        assert spec.structure_state == expected
        assert len(spec.fold_profile) == 8


def test_receiving_family_and_worker_no_longer_import_phase6_or_private_family_module():
    factory_source = inspect.getsource(receiving.resolve_box_body_structure_state)
    worker_source = inspect.getsource(receiving_side_panel_spec_from_trusted_part)
    assert "from phase6_" not in factory_source
    assert "from ae_engine.cabinet_types import receiving" not in worker_source
    assert "resolve_receiving_box_body_structure_state(None)" in worker_source
