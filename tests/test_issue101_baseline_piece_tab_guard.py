# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

import pytest

import fold_designer_bridge as bridge
import gui


def test_fold_designer_known_family_switch_keeps_target_defaults_through_delayed_piece_tab_event():
    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        assert designer.baseline_model_var.get() == "金庫型"

        designer.baseline_model_var.set("受電箱")
        # Delivery of ttk <<NotebookTabChanged>> is deferred.  This update is
        # intentionally part of the regression: programmatic BoxBody child-tab
        # refresh must not save the outgoing family editor over fresh defaults.
        root.update_idletasks()
        root.update()

        snap = dict(designer._phase6_input_snapshot)
        assert snap["model"] == "受電箱"
        assert snap["fw"] == pytest.approx(29.0)
        assert snap["zl1"] == pytest.approx(-24.0)
        assert snap["zl2"] == pytest.approx(24.0)
        assert snap["zr1"] == pytest.approx(15.0)
        assert snap["zr2"] == pytest.approx(18.0)

        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        body = resolved.part("box_body")
        by_role = {piece.role: piece for piece in tuple(body.render_data.pieces or ())}
        left = {row.phase6_key: row for row in by_role["left_side"].fold_profile}
        right = {row.phase6_key: row for row in by_role["right_side"].fold_profile}
        assert left["zl1"].formed_length == pytest.approx(24.0)
        assert right["zr2"].formed_length == pytest.approx(18.0)

        divider_diags = [
            row for row in tuple(resolved.diagnostics or ())
            if "divider:" in str(getattr(row, "subject_part", ""))
        ]
        assert divider_diags
        assert divider_diags[0].candidate_status == "CERTIFIED_REGISTRY_VERIFIED"
        assert divider_diags[0].illegal_penetration is False
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()
