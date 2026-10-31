"""#2517/#2383: genuine Receiving side/back spec is produced by public Engine."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import (
    manufacturing_api, resolve_receiving_split_box_body_spec,
    select_receiving_split_rear_mode,
)
from integration_cli.worker_receiving_side_panel import receiving_side_panel_spec_from_trusted_part
from integration_cli.worker_receiving_back_panel import receiving_back_panel_spec_from_trusted_part
from tests.test_issue2383_receiving_side_panel_worker_api import _part as side_part
from tests.test_issue2383_receiving_back_panel_worker_api import _part as back_part


def _snapshot(part):
    dims = part["dimensions_mm"]
    return {
        "model": "受電箱",
        "w": dims["width"], "h": dims["height"], "d": dims["depth"],
        "t": dims["thickness"], "fw": part["frame_width_mm"],
        "zl1": part["box_zl1_mm"], "zl2": part["box_zl2_mm"],
        "zr2": part["box_zr2_mm"],
    }


@pytest.mark.parametrize("role", ("left_side", "right_side"))
def test_engine_split_side_is_same_physical_fold_and_rear_contract_as_worker(role):
    part = side_part(role)
    canonical = manufacturing_api.resolve_receiving_split_box_body_spec(_snapshot(part))
    worker_spec, selected_role = receiving_side_panel_spec_from_trusted_part(part)
    assert selected_role == role
    assert canonical == worker_spec
    assert resolve_receiving_split_box_body_spec is manufacturing_api.resolve_receiving_split_box_body_spec
    assert len(canonical.fold_profile) == 8
    assert canonical.back_panel_contract["mode"] == "FULL"


@pytest.mark.parametrize("mode", ("FULL", "BACK_OPENING"))
def test_engine_back_panel_mode_is_the_worker_canonical_physical_spec(mode):
    part = back_part(mode)
    base = resolve_receiving_split_box_body_spec(_snapshot(part))
    canonical = manufacturing_api.select_receiving_split_rear_mode(
        base, _snapshot(part), mode=mode,
    )
    assert select_receiving_split_rear_mode is manufacturing_api.select_receiving_split_rear_mode
    assert canonical == receiving_back_panel_spec_from_trusted_part(part)
    assert canonical.back_panel_contract["mode"] == mode
    assert bool(canonical.back_panel_contract["opening"]) == (mode == "BACK_OPENING")


def test_unsupported_rear_mode_or_mismatched_physical_outside_inputs_fail_closed():
    source = _snapshot(side_part())
    spec = resolve_receiving_split_box_body_spec(source)
    with pytest.raises(ValueError):
        select_receiving_split_rear_mode(spec, source, mode="HALF")
    wrong = {**source, "w": source["w"] + 100}
    with pytest.raises(ValueError):
        select_receiving_split_rear_mode(spec, wrong, mode="FULL")
    with pytest.raises(ValueError):
        resolve_receiving_split_box_body_spec({**source, "model": "金庫型"})


def test_worker_side_back_no_longer_owns_fold_or_compensation_formula():
    side = inspect.getsource(receiving_side_panel_spec_from_trusted_part)
    back = inspect.getsource(receiving_back_panel_spec_from_trusted_part)
    assert "resolve_receiving_split_box_body_spec(snapshot)" in side
    assert "select_receiving_split_rear_mode(" in back
    for source in (side, back):
        assert "build_box_body_profile(" not in source
        assert "box_body_height_from_corner_policies(" not in source
        assert "back_width_comp_t" not in source
        assert "resolve_back_panel_contract(" not in source
