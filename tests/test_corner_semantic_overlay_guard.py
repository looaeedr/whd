# -*- coding: utf-8 -*-
"""Regression guard: a maintenance overlay must never downgrade semantic CornerType.

This file intentionally checks both user-facing UI and the production data path that
connects EndCap policies to Box Body assembly.  It exists because a four-file overlay
(gui.py/ae.py/contracts.py/manufacturing_api.py) once restored legacy C01..C04 UI and
silently dropped head/tail CornerType policies.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import fields

import pytest

import gui
from phase6_workspace_controller import Phase6WorkspaceController
from ae_engine.contracts import BoxBodyPartSpec
from ae_engine.corner_type_ui import (
    known_model_corner_state,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
)
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CrossCornerMode,
)


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_new_gui_never_exposes_legacy_c_codes_as_corner_choices():
    source = Path(gui.__file__).read_text(encoding="utf-8")
    for legacy in ("CornerTypeId.C01", "CornerTypeId.C02", "CornerTypeId.C03", "CornerTypeId.C04"):
        assert legacy not in source, f"legacy CornerType leaked back into GUI: {legacy}"
    assert "EDITABLE_CORNER_TYPE_IDS" in source
    assert "manual_corner_rotation_var" not in source
    assert "on_manual_corner_rotation_changed" not in source


def test_known_endcap_state_is_semantic_not_legacy_codes():
    state = known_model_corner_state(["head", "tail"])
    for part in ("head", "tail"):
        top = state[part]["top_left"]
        bottom = state[part]["bottom_left"]
        assert top.type_id is CornerTypeId.INSERT_OVERLAY
        assert top.amount_t == pytest.approx(1.0)
        assert top.secondary_retain_t == pytest.approx(0.5)
        assert top.secondary_depth_t == pytest.approx(2.0)
        assert bottom.type_id is CornerTypeId.CROSS
        assert bottom.cross_mode is CrossCornerMode.EXTRA_CUT
        assert bottom.direction is CornerDirection.BOTH
        assert bottom.amount_t == pytest.approx(0.5)


def test_known_to_custom_reseeds_endcap_semantics_in_main_gui():
    app = object.__new__(gui.BoxCalculatorGUI)
    app.workspace_controller = Phase6WorkspaceController()
    parts = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
    app.manual_corner_state = new_manual_corner_state(parts)
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(parts)
    app.baseline_var = DummyVar("自訂")
    app._baseline_last_value = "金庫型"
    app._fold_designer_baseline_commit_guard = False
    app.refresh_corner_type_panel = lambda: None
    app.update_calculations = lambda: None
    app._door_layout_baseline_cache = {}
    app._box_body_baseline_face_cache = {}

    app.on_baseline_changed()

    assert app._baseline_last_value == "自訂"
    assert app.manual_corner_state["head"]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY
    assert app.manual_corner_state["tail"]["top_left"].type_id is CornerTypeId.INSERT_OVERLAY
    assert app.manual_corner_state["head"]["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT
    assert app.manual_corner_state["tail"]["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT


def test_box_body_contract_cannot_drop_head_tail_corner_policies():
    names = {f.name for f in fields(BoxBodyPartSpec)}
    assert "head_corner_policy" in names
    assert "tail_corner_policy" in names

    source = Path(gui.__file__).read_text(encoding="utf-8")
    assert "head_corner_policy=head_policy" in source
    assert "tail_corner_policy=tail_policy" in source


def test_known_to_custom_endcap_export_keeps_semantic_two_stage_corner(tmp_path):
    import ezdxf
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import generate_part

    app = object.__new__(gui.BoxCalculatorGUI)
    app.workspace_controller = Phase6WorkspaceController()
    parts = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
    app.manual_corner_state = new_manual_corner_state(parts)
    app.manual_corner_pair_same = new_manual_corner_pair_same_state(parts)
    app.baseline_var = DummyVar("自訂")
    app._baseline_last_value = "金庫型"
    app._fold_designer_baseline_commit_guard = False
    app.refresh_corner_type_panel = lambda: None
    app.update_calculations = lambda: None
    app._door_layout_baseline_cache = {}
    app._box_body_baseline_face_cache = {}
    app.on_baseline_changed()
    app._baseline_source_model = lambda: None
    app.head_holes = []
    app.tail_holes = []

    spec = app._end_cap_part_spec({
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "zl1": 15.0, "zr1": 15.0,
    }, is_tail=False)
    out = tmp_path / "head.dxf"
    generate_part(spec, out, ManufacturingContext(draw_stock=False))
    doc = ezdxf.readfile(out)
    cutting = [
        ent for ent in doc.modelspace()
        if str(ent.dxf.layer).upper() == "CUTTING" and ent.dxftype() == "LWPOLYLINE"
    ]
    assert len(cutting) == 1
    pts = [(round(float(x), 6), round(float(y), 6)) for x, y, *_ in cutting[0].get_points()]
    # 17-point contour proves the top INSERT_OVERLAY second stage is present;
    # the regressed CROSS-standard export only has 13 points.
    assert len(pts) == 17
    assert (40.0, 0.0) in pts
    assert (40.0, 39.0) in pts
    assert (16.0, 39.0) in pts
    assert (16.0, 43.0) in pts
