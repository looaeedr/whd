"""#2517: BoxBody folded outside/material readback belongs to headless Engine."""
from __future__ import annotations
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from phase6_fold_profiles import (
    formed_box_body_fw_widths as gui_formed_fw,
    read_box_body_profile as gui_readback,
    ui_segment_length_to_engine as gui_to_material,
    can_remove_segment as gui_can_remove,
)
from tests.test_phase6_linked_fold_chain_and_parts import _box_profile


SNAPSHOT = {
    "model": "金庫型", "w": 400, "d": 250, "h": 600, "t": 2,
    "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_engine_box_body_fold_outside_readback_matches_gui_without_mutating_source(family):
    source = {**SNAPSHOT, "model": family}
    rows = manufacturing_api.build_box_body_fold_profile(source)
    preserved = deepcopy(rows)
    outside = manufacturing_api.read_box_body_outside_dimensions(rows, source)
    assert outside == gui_readback(rows, source)
    assert outside["w"] == source["w"]
    assert outside["d"] == source["d"]
    assert rows == preserved


def test_engine_formed_fw_recomputes_real_bends_and_ignores_stale_witness():
    rows = _box_profile()
    rows[0]["ui_len_add"] = 999
    rows[-1]["ui_len_add"] = 999
    preserved = deepcopy(rows)
    assert manufacturing_api.formed_box_body_fw_widths(rows, 2) == (27.0, 27.0)
    assert gui_formed_fw(rows, 2) == (27.0, 27.0)
    assert rows == preserved


def test_engine_material_length_from_outside_and_removal_gate():
    segment = {"len": 25, "ui_len_add": 2, "phase6_key": "fw_left"}
    assert manufacturing_api.box_body_ui_segment_length_to_material(segment, 27) == 25
    assert gui_to_material(segment, 27) == 25
    assert not manufacturing_api.can_remove_box_body_fold_segment(segment)
    assert not gui_can_remove(segment)
    assert not manufacturing_api.can_remove_box_body_fold_segment({"core": "D", "len": 250})
    assert manufacturing_api.can_remove_box_body_fold_segment({"phase6_key": "custom", "len": 12})


def test_engine_refuses_asymmetric_d_core_on_readback():
    rows = manufacturing_api.build_box_body_fold_profile(SNAPSHOT)
    edited = deepcopy(rows)
    next(row for row in edited if row.get("phase6_key") == "d_left")["len"] += 4
    with pytest.raises(ValueError, match="兩個 D 必須相同"):
        manufacturing_api.read_box_body_outside_dimensions(edited, SNAPSHOT)


def test_gui_fold_readback_has_no_manufacturing_formula():
    for func, api in (
        (gui_formed_fw, "formed_box_body_fw_widths"),
        (gui_readback, "read_box_body_outside_dimensions"),
        (gui_to_material, "box_body_ui_segment_length_to_material"),
        (gui_can_remove, "can_remove_box_body_fold_segment"),
    ):
        source = inspect.getsource(func)
        assert f"manufacturing_api.{api}(" in source
        assert "cabinet_family_policy." not in source
    assert "from phase6_" not in inspect.getsource(manufacturing_api.read_box_body_outside_dimensions)
