"""#2517/#2383: Receiving rear dimensional authority is the public Engine API."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api, resolve_box_body_back_panel_contract
from integration_cli.worker_receiving_side_panel import receiving_side_panel_spec_from_trusted_part
from integration_cli.worker_receiving_back_panel import receiving_back_panel_spec_from_trusted_part
from tests.test_issue2383_receiving_side_panel_worker_api import _part as side_part
from tests.test_issue2383_receiving_back_panel_worker_api import _part as back_part


def _outside_snapshot(part):
    dims = part["dimensions_mm"]
    return {
        "model": "受電箱", "w": dims["width"], "h": dims["height"],
        "d": dims["depth"], "t": dims["thickness"],
        "fw": part["frame_width_mm"],
        "zl1": part["box_zl1_mm"], "zl2": part["box_zl2_mm"],
        "zr2": part["box_zr2_mm"],
    }


@pytest.mark.parametrize("role", ("left_side", "right_side"))
def test_worker_split_side_rear_contract_is_exact_engine_family_result(role):
    part = side_part(role)
    spec, selected = receiving_side_panel_spec_from_trusted_part(part)
    assert selected == role
    assert len(spec.fold_profile) == 8
    assert resolve_box_body_back_panel_contract is manufacturing_api.resolve_box_body_back_panel_contract
    expected = resolve_box_body_back_panel_contract(
        "受電箱", _outside_snapshot(part), structure_state=spec.structure_state,
    )
    assert spec.back_panel_contract == expected
    assert expected["mode"] == "FULL"


@pytest.mark.parametrize("mode", ("FULL", "BACK_OPENING"))
def test_worker_rear_mode_uses_public_engine_contract_without_secondary_formula(mode):
    part = back_part(mode)
    spec = receiving_back_panel_spec_from_trusted_part(part)
    expected = manufacturing_api.resolve_box_body_back_panel_contract(
        "受電箱", _outside_snapshot(part), structure_state=spec.structure_state,
    )
    assert spec.back_panel_contract == expected
    assert spec.back_panel_contract["mode"] == mode
    assert bool(spec.back_panel_contract["opening"]) == (mode == "BACK_OPENING")


def test_worker_rear_contract_is_only_from_engine_not_worker_formula():
    side = inspect.getsource(receiving_side_panel_spec_from_trusted_part)
    back = inspect.getsource(receiving_back_panel_spec_from_trusted_part)
    assert "resolve_box_body_back_panel_contract(" in side
    assert "resolve_box_body_back_panel_contract(" in back
    for source in (side, back):
        assert "back_width_comp_t" not in source
        assert "box_body_height_from_corner_policies(" not in source
        assert "resolve_back_panel_contract(" not in source
