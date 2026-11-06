"""#2517: GUI Receiving modes must be the public Engine state transition."""
from __future__ import annotations

from copy import deepcopy
import ast
import inspect

import pytest

from ae_engine import manufacturing_api
import ae_engine.receiving_mode_session as engine_modes
import phase6_receiving_modes as gui_modes
from phase6_workspace_controller import DEFAULT_EXISTING_PARTS


def test_mode_initializer_and_session_are_same_public_engine_identity():
    assert gui_modes.fresh_receiving_mode is manufacturing_api.fresh_receiving_mode
    assert gui_modes.ReceivingModeSession is manufacturing_api.ReceivingModeSession
    assert gui_modes.ReceivingModeSession is engine_modes.ReceivingModeSession
    assert DEFAULT_EXISTING_PARTS == set(manufacturing_api.DEFAULT_OPERATOR_EXISTING_PARTS)
    assert manufacturing_api.DEFAULT_OPERATOR_EXISTING_PARTS == (
        "box_body", "head", "tail", "door", "base_plate",
    )


def test_engine_mode_state_has_no_reverse_gui_or_phase6_imports():
    source = ast.parse(inspect.getsource(engine_modes))
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("phase6_", "gui_modules")), node.module
        elif isinstance(node, ast.Import):
            assert all(not item.name.startswith(("phase6_", "gui_modules")) for item in node.names)


@pytest.mark.parametrize("mode", ["set_bay", "quantity"])
def test_public_fresh_mode_owns_one_cabinet_door_layout_and_detached_inputs(mode):
    dims = {"w": 800, "h": 1600, "d": 350}
    before = deepcopy(dims)
    snapshot = manufacturing_api.fresh_receiving_mode(mode, dims)
    assert dims == before
    assert snapshot["active_mode"] == mode
    assert snapshot["existing_parts"] == list(manufacturing_api.DEFAULT_OPERATOR_EXISTING_PARTS)
    assert snapshot["door_layout_columns"] == [[800.0, [1100.0, 500.0]]]
    assert len(snapshot["receiving_layout"]["sets"]) == 1
    assert len(snapshot["receiving_layout"]["sets"][0]["bays"]) == 1
    if mode == "quantity":
        assert snapshot["quantity"]["selected_version_id"] == "quantity-v1"
        assert snapshot["receiving_quantity_box"]["w"] == 800
    else:
        assert "quantity" not in snapshot


@pytest.mark.parametrize("bad", [None, False, 0, -1, "nan", "invalid"])
def test_public_fresh_mode_rejects_invalid_dimensions_without_mutation(bad):
    dims = {"w": 800, "h": bad, "d": 350}
    before = deepcopy(dims)
    with pytest.raises(ValueError):
        manufacturing_api.fresh_receiving_mode("set_bay", dims)
    assert dims == before


def test_public_engine_session_tracks_revisions_and_independent_mode_buffers():
    original = manufacturing_api.fresh_receiving_mode(
        "set_bay", {"w": 800, "h": 1600, "d": 350},
    )
    original["_runtime_family_presets"] = {"金庫型": {"settings": {"w": 400, "h": 600, "d": 250, "t": 2}}}
    session = manufacturing_api.ReceivingModeSession(original)
    assert session.needs_initialization("quantity")
    assert not session.switch("quantity")
    assert session.snapshot() == original
    assert session.switch("quantity", dimensions={"w": 900, "h": 1700, "d": 400})
    quantity = session.snapshot()
    assert quantity["active_mode"] == "quantity"
    assert quantity["_runtime_family_presets"] == original["_runtime_family_presets"]
    assert original["active_mode"] == "set_bay"
    assert session.switch("set_bay", current_snapshot=quantity)
    assert session.snapshot() == original
