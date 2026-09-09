# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.box_body_structure import resolve_box_body_structure
from phase6_fold_profiles import (
    apply_outside_dimension_compensation,
    build_box_body_profile,
    engine_segment_length_to_ui,
)


def _fresh_receiving():
    snap = receiving.apply_family_defaults({"t": 2.0})
    state = receiving.resolve_box_body_structure_state(None)
    result = resolve_box_body_structure(
        build_box_body_profile(snap),
        w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=state,
    )
    return snap, state, result


def _piece(result, role):
    return next(piece for piece in result.pieces if piece.role == role)


def _operator_values(rows, thickness):
    rows = [dict(row) for row in rows]
    apply_outside_dimension_compensation(rows, thickness)
    values = []
    for row in rows:
        magnitude = engine_segment_length_to_ui(row)
        sign = -1 if float(row.get("phase6_ui_sign", 1.0)) < 0 else 1
        values.append(sign * magnitude)
    return values


def test_receiving_fresh_side_panel_defaults_are_operator_outside_authority():
    snap, state, _result = _fresh_receiving()
    assert (
        snap["zl1"], snap["zl2"], snap["fw"], snap["d"], snap["zr2"]
    ) == (-24.0, 24.0, 29.0, 350.0, 18.0)

    cfg = state["configs"]["three_piece_side_back_split"]
    assert cfg["side_rear_bend"] == pytest.approx(18.0)
    assert cfg["side_rear_bend_dimension_space"] == "OUTSIDE"


def test_receiving_outside_defaults_derive_material_once_without_becoming_ui_authority():
    _snap, _state, result = _fresh_receiving()
    left = _piece(result, "left_side")
    right = _piece(result, "right_side")

    assert [(row.phase6_key, row.length) for row in left.fold_profile] == [
        ("zl1", 22.0),
        ("zl2", 20.0),
        ("fw_left", 25.0),
        ("d_left", 346.0),
        ("side_rear_bend_left", 16.0),
    ]
    # Manufacturing-local right-side traversal is rear -> front.
    assert [(row.phase6_key, row.length) for row in right.fold_profile] == [
        ("side_rear_bend_right", 16.0),
        ("d_right", 346.0),
        ("fw_right", 25.0),
        ("zr2", 16.0),
    ]


def test_receiving_physical_child_editor_projection_is_outside_and_front_to_rear():
    import fold_designer_bridge as bridge

    snap, _state, result = _fresh_receiving()
    profiles = bridge._phase6_box_body_piece_part_profiles(result, snap)

    left = profiles["box_body:left_side"]["X"]
    right = profiles["box_body:right_side"]["X"]

    assert [row["phase6_key"] for row in left] == [
        "zl1", "zl2", "fw_left", "d_left", "side_rear_bend_left"
    ]
    assert _operator_values(left, snap["t"]) == [-24, 24, 29, 350, 18]

    # Operator-facing order is explicitly front -> rear, even though the
    # manufacturing-local right-side fold chain is stored rear -> front.
    assert [row["phase6_key"] for row in right] == [
        "zr2", "fw_right", "d_right", "side_rear_bend_right"
    ]
    assert _operator_values(right, snap["t"]) == [18, 29, 350, 18]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_designer_controls_show_exact_outside_defaults_for_each_physical_side():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1200x900")
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.activate_part("box_body:left_side")
        root.update_idletasks(); root.update()
        assert [int(ctrl["len"].get()) for ctrl in designer.bend_ui.controls] == [
            -24, 24, 29, 350, 18
        ]

        designer.activate_part("box_body:right_side")
        root.update_idletasks(); root.update()
        assert [int(ctrl["len"].get()) for ctrl in designer.bend_ui.controls] == [
            18, 29, 350, 18
        ]
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_receiving_legacy_unmarked_rear_bend_remains_material_for_reload_compatibility():
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        default_box_body_structure_state,
        set_active_structure,
    )

    legacy = set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )
    legacy["configs"]["three_piece_side_back_split"]["side_rear_bend"] = 15.0
    resolved_state = receiving.resolve_box_body_structure_state(legacy)
    cfg = resolved_state["configs"]["three_piece_side_back_split"]
    assert cfg["side_rear_bend"] == pytest.approx(15.0)
    assert cfg["side_rear_bend_dimension_space"] == "MATERIAL"

    snap = receiving.apply_family_defaults({"t": 2.0})
    result = resolve_box_body_structure(
        build_box_body_profile(snap),
        w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=resolved_state,
    )
    left = _piece(result, "left_side")
    assert left.fold_profile[-1].length == pytest.approx(15.0)
