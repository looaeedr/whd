from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
T0_INVENTORY = ROOT / "docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_responsibility_inventory.md"
T0_DEPENDENCY = ROOT / "docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_dependency_map.md"
T0_STATE_OWNER = ROOT / "docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_state_owner_map.md"
DESIGN = ROOT / "docs/superpowers/specs/2026-09-18-issue294-t6-rendering-design.md"
PLAN = ROOT / "docs/superpowers/plans/2026-09-18-issue294-t6-rendering.md"

ACCEPTED_PREDECESSOR = "e05204366146cf44d2c8cb2ad939f5f753aba030"
RECONCILIATION_RUN = "35290713319"
RAW_ISSUE_GATE = 3_000
PREDECESSOR_GUI_LOC = 5_876
PURE_T6_LOC = 1_302
SHARED_REVIEW_LOC = 348
DERIVED_CACHE_REVIEW_LOC = 36
PURE_T6_SYMBOL_COUNT = 37
DELEGATE_LINES_PER_SYMBOL = 3
IMPORT_WIRING_BUDGET = 24
SAFETY_MARGIN = 20
RECONCILED_GATE = 4_729
FINAL_T8_GATE = 2_500

PURE_T6_SYMBOLS = {
    "_YMirroredPreviewTransform",
    "_box_body_baseline_faces",
    "_box_body_face_at_canvas_point",
    "_box_body_face_baseline_scene",
    "_box_body_piece_face_key",
    "_box_body_piece_label",
    "_door_layout_cell_at_canvas_point",
    "_draw_box_body_piece_preview",
    "_draw_door_layout_dividers_and_frames",
    "_draw_phase6_annotation_projection",
    "_draw_phase6_corner_dimension_overlay",
    "_on_box_body_piece_2d_tab_changed",
    "_phase6_2d_material_viewport",
    "_rects_overlap",
    "_refresh_box_body_piece_tabs_2d",
    "draw_base_plate",
    "draw_box_body",
    "draw_door",
    "draw_door_layout_overview",
    "draw_end_cap",
    "draw_indicator_box",
    "draw_indicator_door",
    "draw_preview",
    "feature_surface_from_drawing_scene",
    "layout_reference_overlay_rects",
    "on_box_body_canvas_press",
    "on_box_body_piece_double_click",
    "on_door_canvas_double_click",
    "on_door_canvas_drag",
    "on_door_canvas_press",
    "on_door_canvas_release",
    "open_box_body_face_editor",
    "render_resolved_features",
    "render_secondary_scene",
    "render_structural_result",
    "render_surface_user_features",
    "select_box_body_face",
}


def test_issue294_raw_3000_gate_is_impossible_even_with_overgenerous_t6_credit():
    maximal_removable = PURE_T6_LOC + SHARED_REVIEW_LOC + DERIVED_CACHE_REVIEW_LOC
    zero_wiring_best_case = PREDECESSOR_GUI_LOC - maximal_removable
    required_removal = PREDECESSOR_GUI_LOC - RAW_ISSUE_GATE

    assert maximal_removable == 1_686
    assert required_removal == 2_876
    assert zero_wiring_best_case == 4_190
    assert zero_wiring_best_case > RAW_ISSUE_GATE


def test_issue294_reconciled_gate_uses_only_pure_t6_legal_budget():
    assert len(PURE_T6_SYMBOLS) == PURE_T6_SYMBOL_COUNT
    delegate_budget = DELEGATE_LINES_PER_SYMBOL * PURE_T6_SYMBOL_COUNT
    theoretical_root = (
        PREDECESSOR_GUI_LOC
        - PURE_T6_LOC
        + delegate_budget
        + IMPORT_WIRING_BUDGET
    )
    suggested_gate = theoretical_root + SAFETY_MARGIN

    assert delegate_budget == 111
    assert theoretical_root == 4_709
    assert suggested_gate == RECONCILED_GATE
    assert RECONCILED_GATE > PREDECESSOR_GUI_LOC - PURE_T6_LOC
    assert FINAL_T8_GATE < RECONCILED_GATE


def test_issue294_t0_authority_keeps_rendering_one_way_and_geometry_external():
    inventory = T0_INVENTORY.read_text(encoding="utf-8")
    dependency = T0_DEPENDENCY.read_text(encoding="utf-8")
    state_owner = T0_STATE_OWNER.read_text(encoding="utf-8")

    for symbol in PURE_T6_SYMBOLS:
        assert f"`{symbol}`" in inventory, f"missing CURRENT T0 T6 authority row: {symbol}"

    assert "resolved data → rendering only" in dependency
    assert "Rendering must never rederive manufacturing geometry" in dependency
    assert "presentation/derived render state only" in state_owner
    assert "may not own physical presence, project truth, DXF truth, or manufacturing dimensions" in state_owner


def test_issue294_design_and_plan_pin_machine_proof_without_weakening_phase2_gate():
    design = DESIGN.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    for text in (design, plan):
        assert ACCEPTED_PREDECESSOR in text
        assert RECONCILIATION_RUN in text
        assert "4,729" in text
        assert "2,500" in text
        assert "Phase 2" in text
        assert "resolved" in text.lower()
        assert "render" in text.lower()
