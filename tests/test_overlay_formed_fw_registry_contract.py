# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest
from shapely.geometry import box

FIXTURE = Path(__file__).with_name("fixtures") / "vault_overlay_w400_t2_fw25.p6fold"


def _edge_span(material, *, high: bool):
    minx, miny, maxx, maxy = map(float, material.bounds)
    eps = 0.5
    band = (
        box(minx - 1.0, maxy - eps, maxx + 1.0, maxy)
        if high
        else box(minx - 1.0, miny, maxx + 1.0, miny + eps)
    )
    section = material.intersection(band)
    sx0, _sy0, sx1, _sy1 = map(float, section.bounds)
    return sx0 - minx, maxx - sx1, sx1 - sx0


def _destroy(app, root):
    try:
        win = getattr(app, "fold_designer_window", None)
        if win is not None and win.winfo_exists():
            win.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_overlay_registry_declares_standard_material_geometry_inputs():
    from ae_engine.certified_relief_registry import load_external_relief_rule_records

    records = load_external_relief_rule_records()
    overlay = next(row for row in records if row["rule_id"] == "ENDCAP_TOP_OVERLAY_STANDARD_V1")
    assert "BOX_BODY_FORMED_FW" not in overlay["geometry_inputs"]
    assert overlay["geometry_inputs"] == [
        "ENDCAP_SIDE_FOLD", "ENDCAP_FW", "ENDCAP_YTOP1", "SHEET_THICKNESS",
    ]
    assert overlay["standard_ref"] == "ENDCAP_TOP_STANDARD_V1"
    assert overlay["dimension_space"] == "MATERIAL"
    assert overlay["formula"]["primary_u"] == "side_fold + FW"
    assert overlay["formula"]["primary_v"] == "ytop1 + FW - T"
    assert overlay["formula"]["secondary_u"] == "side_fold"
    assert overlay["formula"]["secondary_depth"] == "T"


def test_real_overlay_project_rejects_stale_committed_cache_and_rebuilds_standard_material_relief():
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.load_phase6_project(FIXTURE, open_designer=False)
        val = app.get_float_values()
        # The historical fixture contains an old committed relief signature.
        # Graph/rule revision mismatch must reject replay; 2D then rebuilds from
        # the current STANDARD + Semantic Delta contract before 3D is opened.
        for part_key, is_tail in (("head", False), ("tail", True)):
            spec = app._end_cap_part_spec(val, is_tail=is_tail)
            assert spec.resolved_assembly_relief_cuts == ()
            render = app._authoritative_render_data(
                spec, app._manufacturing_context(draw_stock=False)
            )
            top = _edge_span(render.material, high=(part_key == "tail"))
            assert top == pytest.approx((40.0, 40.0, 342.0))
    finally:
        _destroy(app, root)


def test_overlay_3d_solver_uses_certified_standard_material_rule_and_zero_illegal_penetration():
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.load_phase6_project(FIXTURE, open_designer=False)
        designer = app.open_original_fold_designer()
        designer.preview_3d_enabled = False
        designer._phase6_3d_display_mode = "assembly"
        bundle = bridge._phase6_query_assembly_render_data(designer)
        assert dict(getattr(designer, "_phase6_last_relief_errors", {}) or {}) == {}
        assert bundle.assembly_parts
        for part_key in ("head", "tail"):
            solution = designer._phase6_last_relief_solutions[part_key]
            assert solution.verified is True
            assert solution.trust_level == "CERTIFIED"
            assert solution.rule_id == "ENDCAP_TOP_OVERLAY_STANDARD_V1"
            assert solution.rule_revision == 3
            # residual_pair_count may contain legal mating-line / skin contact;
            # verified=True is the zero-illegal-material-penetration contract.
            assert solution.shadow_validation["verified"] is True
            assert solution.shadow_validation["residual_pair_count"] >= 0
            assert solution.shadow_validation["geometry_inputs"] == [
                "ENDCAP_SIDE_FOLD", "ENDCAP_FW", "ENDCAP_YTOP1", "SHEET_THICKNESS",
            ]
            assert solution.shadow_validation["geometry_evidence"]["owner"] == "RESOLVED_ASSEMBLY_GRAPH"
            assert [r.measurement.primary_u for r in solution.corner_reliefs] == pytest.approx([40.0, 40.0])
            assert [r.measurement.primary_v for r in solution.corner_reliefs] == pytest.approx([39.0, 39.0])
            assert [r.measurement.secondary_u for r in solution.corner_reliefs] == pytest.approx([15.0, 15.0])
            assert [r.measurement.secondary_depth for r in solution.corner_reliefs] == pytest.approx([2.0, 2.0])
            traces = designer._phase6_last_resolved_manufacturing_geometry.relief_rules_for(part_key)
            assert traces
            assert all(trace.revision == 3 for trace in traces)
            assert all(trace.geometry_inputs == (
                "ENDCAP_SIDE_FOLD", "ENDCAP_FW", "ENDCAP_YTOP1", "SHEET_THICKNESS",
            ) for trace in traces)
            assert all(trace.geometry_evidence["owner"] == "RESOLVED_ASSEMBLY_GRAPH" for trace in traces)
    finally:
        _destroy(app, root)
