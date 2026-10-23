# -*- coding: utf-8 -*-
"""#1504 AC-20/SWT-13: parent/layer/slot brand transition preview and rollback."""
from copy import deepcopy

from ae_engine.receiving_nfb_brand_transition import (
    saved_parent_new_reselections, draft_new_reselections,
)
from ae_engine.receiving_nfb_model_identity import numeric_model_refs
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, new_nfb_ui1a_draft,
    set_nfb_layer_brand, set_nfb_slot_brand,
)


def _saved(*brands):
    return {
        "nfb_config_submitted": True,
        "nfb_config": {
            "layer_count": 1,
            "holes": [
                {
                    "physical_hole_id": f"nfb:unit:{i}",
                    "model_filename": numeric_model_refs(brand)[0],
                    "source_brand": brand,
                    "brand_mode": mode,
                    "manual_x_state": "NONE", "manual_x_mm": None,
                    "rotation_deg": 0,
                }
                for i, (brand, mode) in enumerate(brands)
            ],
        },
    }


def test_ac20_saved_parent_impact_counts_only_newly_stale_followers_without_mutation():
    source = _saved(("士林", INHERIT), ("士林", OVERRIDE), ("東元", INHERIT))
    before = deepcopy(source)
    assert saved_parent_new_reselections(source, "士林", "東元") == 1
    assert saved_parent_new_reselections(source, "士林", "士林") == 0
    assert saved_parent_new_reselections(
        {"nfb_config_submitted": False}, "士林", "東元",
    ) == 0
    assert source == before
    assert all(row["rotation_deg"] == 0 for row in source["nfb_config"]["holes"])


def test_swt13_layer_and_explicit_unit_brand_impact_reuses_one_inheritance_rule():
    shihlin = numeric_model_refs("士林")[0]
    old = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=([shihlin, shihlin], ""),
    )
    before = deepcopy(old)
    changed = set_nfb_layer_brand(old, 0, mode=OVERRIDE, value="東元")
    assert draft_new_reselections(old, changed) == 2
    override_one = set_nfb_slot_brand(old, 0, 0, mode=OVERRIDE, value="士林")
    changed_layer = set_nfb_layer_brand(
        override_one, 0, mode=OVERRIDE, value="東元",
    )
    assert draft_new_reselections(override_one, changed_layer) == 1
    same_override = set_nfb_slot_brand(
        old, 0, 0, mode=OVERRIDE, value="士林",
    )
    assert draft_new_reselections(old, same_override) == 0
    assert same_override["layers"][0]["slots"][0]["brand"]["mode"] == OVERRIDE
    assert old == before


def test_ac20_original_single_tk_brand_reselection_warning_cancel_is_atomic(monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    import gui
    import fold_designer_bridge as bridge
    from phase6_quantity_model import QuantityModel

    root = tk.Tk()
    root.withdraw()
    window = None
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        root.update()
        window = bridge._phase6_open_receiving_single_settings(app)
        root.update()
        assert app.designer_workspace.active_mode == "quantity"
        assert window._receiving_multi_brand_selector.get() == "士林"
        before = deepcopy(app.designer_workspace.snapshot())
        brand = window._receiving_multi_brand_selector
        seen = []
        monkeypatch.setattr(messagebox, "askyesno",
                            lambda title, body, **kw: (seen.append((title, body)), False)[1])
        brand.set("東元")
        brand.event_generate("<<ComboboxSelected>>")
        root.update()
        assert seen and "顆 NFB 原型號待重選" in seen[0][1]
        assert "1 顆" in seen[0][1]
        assert brand.get() == "士林"
        assert app.designer_workspace.snapshot() == before

        monkeypatch.setattr(messagebox, "askyesno",
                            lambda title, body, **kw: (seen.append((title, body)), True)[1])
        brand.set("東元")
        brand.event_generate("<<ComboboxSelected>>")
        root.update()
        quantity = QuantityModel.from_payload(app.designer_workspace.snapshot()["quantity"])
        assert quantity.nfb_parent_brand_for_version(quantity.selected_version_id) == "東元"
        assert len(seen) == 2
        assert before["receiving_quantity_box"]["switch_brand"] == "士林"
        # Only the parent changes; its previous numeric model stays sourced
        # to Shihlin and has no fabrication permission until reselected.
        version = quantity.nfb_config_for_version(quantity.selected_version_id)
        assert all(hole["source_brand"] == "士林"
                   for hole in version["nfb_config"]["holes"])
    finally:
        if window is not None and window.winfo_exists():
            window.destroy()
        root.destroy()
