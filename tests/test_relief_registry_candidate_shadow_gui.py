# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from ae_engine.certified_relief_registry import load_external_relief_rule_records


def test_candidate_record_gets_its_own_shadow_validation_without_mutating_registry():
    import fold_designer_bridge as bridge
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app._set_box_assembly_type("INSERT", recalculate=True, notify_designer=False, reset_bottom_defaults=False)
        designer = app.open_original_fold_designer()
        designer.preview_3d_enabled = False
        source = next(
            dict(row) for row in load_external_relief_rule_records()
            if row.get("active", True) and row["rule_id"] == "ENDCAP_TOP_INSERT_STANDARD_V1"
        )
        record = {
            key: source[key]
            for key in (
                "rule_id", "cabinet_family", "part_role", "joint_face", "assembly_intent",
                "joint_signature", "topology_levels", "preconditions", "formula", "source",
            )
        }
        record["rule_id"] = "FORM_PREVIEW_INSERT_STANDARD"
        evidence = bridge._phase6_registry_validate_candidate_3d(
            designer, record, candidate_id="candidate-test"
        )
        assert evidence["candidate_specific"] is True
        assert evidence["candidate_id"] == "candidate-test"
        assert evidence["zero_penetration"] is True
        assert evidence["validated_parts"] == ["head", "tail"]
        assert all(row["rule_id"] == "FORM_PREVIEW_INSERT_STANDARD" for row in evidence["solutions"].values())
    finally:
        try:
            designer.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
