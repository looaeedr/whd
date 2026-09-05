# -*- coding: utf-8 -*-
"""End-to-end registry-driven acceptance matrix for cabinet Assembly Intents.

The parametrization comes directly from the active Certified Relief Registry.
Adding a new certified Assembly Intent therefore adds a required GUI/2D/3D/
save-reload acceptance case automatically.
"""
from __future__ import annotations

import tkinter as tk

import pytest

from ae_engine.certified_relief_registry import (
    CertifiedReliefStatus,
    registered_certified_relief_rules,
)


def _registered_certified_intents():
    active = {CertifiedReliefStatus.CERTIFIED, CertifiedReliefStatus.CERTIFIED_FROM_3D}
    return tuple(sorted(
        {
            rule.assembly_intent
            for rule in registered_certified_relief_rules()
            if rule.status in active and rule.assembly_intent is not None
        },
        key=lambda item: item.value,
    ))


REGISTERED_CERTIFIED_INTENTS = _registered_certified_intents()


def _destroy(app, root):
    try:
        window = getattr(app, "fold_designer_window", None)
        if window is not None and window.winfo_exists():
            window.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.mark.parametrize("intent", REGISTERED_CERTIFIED_INTENTS, ids=lambda item: item.value)
def test_registered_assembly_intent_gui_2d_3d_collision_and_reload_matrix(intent, tmp_path):
    import fold_designer_bridge as bridge
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    save_path = tmp_path / f"assembly-{intent.value}.p6fold"
    try:
        app._set_box_assembly_type(
            intent, recalculate=True, notify_designer=False, reset_bottom_defaults=False
        )
        assert app._current_box_assembly_type() is intent

        designer = app.open_original_fold_designer()
        designer.preview_3d_enabled = False
        designer._phase6_3d_display_mode = "assembly"
        bundle = bridge._phase6_query_assembly_render_data(designer)

        assert dict(getattr(designer, "_phase6_last_relief_errors", {}) or {}) == {}
        solutions = dict(getattr(designer, "_phase6_last_relief_solutions", {}) or {})
        assert set(solutions) >= {"head", "tail"}
        for key in ("head", "tail"):
            solution = solutions[key]
            assert solution.rule_id
            assert int(solution.rule_revision) >= 1
            assert solution.trust_level in {
                CertifiedReliefStatus.CERTIFIED.value,
                CertifiedReliefStatus.CERTIFIED_FROM_3D.value,
                CertifiedReliefStatus.ENGINE_CONFLICT.value,
            }
        assert {part.part_key for part in bundle.interference_probe_parts} >= {"head", "tail"}

        assembly_by_key = {part.part_key: part.render_data for part in bundle.assembly_parts}
        val = app.get_float_values()
        expected_material = {}
        for key, is_tail in (("head", False), ("tail", True)):
            main_2d = app._authoritative_render_data(
                app._end_cap_part_spec(val, is_tail=is_tail),
                app._manufacturing_context(draw_stock=False),
            )
            expected_material[key] = main_2d.material
            assert main_2d.material.symmetric_difference(assembly_by_key[key].material).area <= 1e-6

            designer.activate_part(key)
            single_3d = bridge._phase6_query_final_render_data(designer)
            assert single_3d.material.symmetric_difference(main_2d.material).area <= 1e-6

        # Actual assembly renderer must show the pre-solve collision evidence,
        # even though the displayed EndCaps are already the verified solved parts.
        designer._phase6_3d_display_mode = "assembly"
        bridge._phase6_render_true_cutting_mesh(designer)
        diagnostic = designer.final_scene_view.last_interference_diagnostic
        assert diagnostic.has_interference is True
        assert len(diagnostic.intersection_segments) > 0

        app.project_controller.save(
            save_path,
            app._compose_phase6_project_snapshot_from_main_gui,
            active_part_hint="box_body",
        )
        saved_relief = dict(getattr(app, "assembly_relief_state", {}) or {})
        saved_parts = dict(saved_relief.get("parts", {}) or {})
        for key in ("head", "tail"):
            assert saved_parts[key]["rule_id"] == solutions[key].rule_id
            assert int(saved_parts[key]["rule_revision"]) == int(solutions[key].rule_revision)
            assert saved_parts[key]["trust_level"] == solutions[key].trust_level
    finally:
        _destroy(app, root)

    root2 = tk.Tk(); root2.withdraw()
    app2 = gui.BoxCalculatorGUI(root2)
    try:
        app2.load_phase6_project(save_path, open_designer=False)
        assert app2._current_box_assembly_type() is intent
        reloaded_parts = dict((app2.assembly_relief_state or {}).get("parts", {}) or {})
        for key in ("head", "tail"):
            assert reloaded_parts[key]["rule_id"] == solutions[key].rule_id
            assert int(reloaded_parts[key]["rule_revision"]) == int(solutions[key].rule_revision)
            assert reloaded_parts[key]["trust_level"] == solutions[key].trust_level
        val2 = app2.get_float_values()
        for key, is_tail in (("head", False), ("tail", True)):
            reloaded = app2._authoritative_render_data(
                app2._end_cap_part_spec(val2, is_tail=is_tail),
                app2._manufacturing_context(draw_stock=False),
            )
            assert reloaded.material.symmetric_difference(expected_material[key]).area <= 1e-6
    finally:
        _destroy(app2, root2)
