from __future__ import annotations

import inspect
import os

import pytest


def test_main_gui_box_body_dimension_path_has_no_legacy_calculate_z_length():
    import gui

    source = inspect.getsource(gui.BoxCalculatorGUI.update_calculations)
    assert "calculate_z_length(" not in source, (
        "Main GUI Box Body dimension projection still owns the fixed-segment "
        "calculate_z_length fallback"
    )


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_main_result_uses_authoritative_1596_material_width():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        app.update_calculations()
        assert app.result_z_var.get() == "1596.00 mm"
        assert app.workspace_controller.box_body_profile()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_receiving_back_panel_adapter_carries_canonical_family_identity():
    import ast
    from pathlib import Path

    source = Path("gui_modules/application/manufacturing_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_box_body_part_spec_from_values"
    )
    body = ast.get_source_segment(source, fn) or ""

    assert "family_name = cabinet_family_policy.canonical_family_name(model_name)" in body
    assert 'back_panel_snapshot["model"] = family_name' in body
    assert "model_name,\n            back_panel_snapshot," in body
    assert "model_name,\n            dict(snapshot or val)," not in body


def test_receiving_back_panel_family_contract_requires_snapshot_identity():
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    structure_state = cabinet_family_policy.resolve_box_body_structure_state("受電箱", None)
    with pytest.raises(ValueError, match="Receiving-only"):
        cabinet_family_policy.resolve_back_panel_contract(
            "受電箱",
            {},
            structure_state=structure_state,
            panel_width=795.0,
            full_panel_height=1596.0,
        )

    contract = cabinet_family_policy.resolve_back_panel_contract(
        "受電箱",
        {"model": "受電箱"},
        structure_state=structure_state,
        panel_width=795.0,
        full_panel_height=1596.0,
    )
    assert contract["mode"] == "FULL"
    assert contract["panel_width"] == 795.0
    assert contract["full_panel_height"] == 1596.0
