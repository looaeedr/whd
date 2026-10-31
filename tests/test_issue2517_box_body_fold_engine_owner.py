"""#2517 headless physical BoxBody Fold authority, GUI and Worker thin callers."""
from __future__ import annotations
import inspect
import pytest

from ae_engine import manufacturing_api, build_box_body_fold_profile, box_body_profile_to_fold_segments
from ae_engine import box_body_fold_profile as owner
from ae_engine.contracts import FoldProfileSegment
from phase6_fold_profiles import (
    build_box_body_profile as gui_builder,
    profile_to_fold_segments as gui_converter,
    apply_outside_dimension_compensation as gui_compensation,
)
from integration_cli.worker_receiving_side_panel import receiving_side_panel_spec_from_trusted_part
from tests.test_issue2383_receiving_side_panel_worker_api import _part as receiving_part


@pytest.mark.parametrize("family", ("受電箱", "金庫型"))
def test_engine_fold_matches_existing_vault_and_receiving_gui_and_material_dto(family):
    values = {
        "model": family, "w": 800.0, "h": 1600.0,
        "d": 350.0, "t": 2.0, "fw": 29.0,
        "zl1": -24.0, "zl2": 24.0, "zr2": 18.0, "zr1": 15.0,
    }
    rows = manufacturing_api.build_box_body_fold_profile(values)
    assert build_box_body_fold_profile is manufacturing_api.build_box_body_fold_profile
    assert rows == gui_builder(values)
    assert [r.get("core") for r in rows].count("D") == 2
    assert [r.get("core") for r in rows].count("W") == 1
    assert len(rows) == (8 if family == "受電箱" else 9)
    segments = box_body_profile_to_fold_segments(rows)
    assert box_body_profile_to_fold_segments is manufacturing_api.box_body_profile_to_fold_segments
    assert segments == gui_converter(rows)
    assert all(isinstance(s, FoldProfileSegment) and s.length >= 0 for s in segments)


def test_receiving_worker_consumes_actual_engine_fold_without_phase6_formula():
    part = receiving_part("left_side")
    spec, role = receiving_side_panel_spec_from_trusted_part(part)
    dims = part["dimensions_mm"]
    snapshot = {
        "model": "受電箱", "w": dims["width"], "h": dims["height"],
        "d": dims["depth"], "t": dims["thickness"], "fw": part["frame_width_mm"],
        "zl1": part["box_zl1_mm"], "zl2": part["box_zl2_mm"],
        "zr2": part["box_zr2_mm"],
    }
    assert role == "left_side"
    assert spec.fold_profile == box_body_profile_to_fold_segments(build_box_body_fold_profile(snapshot))
    src = inspect.getsource(receiving_side_panel_spec_from_trusted_part)
    assert "build_box_body_fold_profile(snapshot)" in src
    assert "box_body_profile_to_fold_segments(fold_rows)" in src
    assert "from phase6_fold_profiles" not in src


def test_adjacent_bend_compensation_stays_engine_only_and_recomputes_when_removed():
    rows = [{"len": 20.0, "angle": 90}, {"len": 100.0}, {"len": 10.0}]
    result = owner.apply_outside_dimension_compensation(rows, 2.0)
    assert [r.get("ui_len_add") for r in result] == [2.0, 2.0, None]
    assert gui_compensation(rows, 2.0) == result
    rows[0].pop("angle")
    assert [r.get("ui_len_add") for r in owner.apply_outside_dimension_compensation(rows, 2.0)] == [None, None, None]
    src = inspect.getsource(owner)
    assert "from phase6" not in src and "import tkinter" not in src
    assert "_engine_build_box_body_fold_profile(snapshot)" in inspect.getsource(gui_builder)
