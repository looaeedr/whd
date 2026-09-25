from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
T0_INVENTORY = ROOT / "docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_responsibility_inventory.md"
T0_STATE_OWNER = ROOT / "docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_state_owner_map.md"
DESIGN = ROOT / "docs/superpowers/specs/2026-09-17-issue293-t5-editors-design.md"
PLAN = ROOT / "docs/superpowers/plans/2026-09-17-issue293-t5-editors.md"

ACCEPTED_PREDECESSOR = "2ee5f73183c08f5f6dee3c220f8d95c5f097c9af"
RECONCILIATION_RUN = "35217734914"
RAW_ISSUE_GATE = 4_000
PREDECESSOR_GUI_LOC = 7_453
RECONCILED_GATE = 5_884
DELEGATE_LINES_PER_SYMBOL = 3
IMPORT_WIRING_BUDGET = 24
SAFETY_MARGIN = 20
FINAL_T8_GATE = 2_500

# Exact CURRENT T0 rows assigned to T5 or shared T5/T6 on the accepted #292 tree.
# This intentionally grants every line as removable, even though T0 explicitly
# forbids whole-method relocation of _open_unified_hole_editor. Therefore this is
# an over-generous upper bound for proving the original raw gate impossible.
T0_T5_SYMBOL_LOCS = {
    "_open_unified_hole_editor": 1_333,
    "ask_xy_dialog": 54,
    "draw_hole_editor_hint": 7,
    "open_hole_editor": 20,
    "open_part_hole_editor": 214,
}


def test_issue293_raw_4000_gate_is_impossible_inside_current_t0_t5_scope():
    maximal_removable = sum(T0_T5_SYMBOL_LOCS.values())
    zero_wiring_best_case = PREDECESSOR_GUI_LOC - maximal_removable
    required_removal = PREDECESSOR_GUI_LOC - RAW_ISSUE_GATE

    assert maximal_removable == 1_628
    assert required_removal == 3_453
    assert zero_wiring_best_case == 5_825
    assert zero_wiring_best_case > RAW_ISSUE_GATE


def test_issue293_reconciled_gate_matches_same_budget_method_used_by_t4():
    removable = sum(T0_T5_SYMBOL_LOCS.values())
    delegate_budget = DELEGATE_LINES_PER_SYMBOL * len(T0_T5_SYMBOL_LOCS)
    theoretical_root = (
        PREDECESSOR_GUI_LOC
        - removable
        + delegate_budget
        + IMPORT_WIRING_BUDGET
    )
    suggested_gate = theoretical_root + SAFETY_MARGIN

    assert delegate_budget == 15
    assert theoretical_root == 5_864
    assert suggested_gate == RECONCILED_GATE
    assert RECONCILED_GATE > PREDECESSOR_GUI_LOC - removable
    assert FINAL_T8_GATE < RECONCILED_GATE


def test_issue293_t0_authority_still_assigns_only_these_editor_symbols_to_t5():
    inventory = T0_INVENTORY.read_text(encoding="utf-8")
    state_owner = T0_STATE_OWNER.read_text(encoding="utf-8")

    for symbol in T0_T5_SYMBOL_LOCS:
        assert f"`{symbol}`" in inventory, f"missing CURRENT T0 T5 authority row: {symbol}"
    assert "transient editor state only" in state_owner
    assert "_open_unified_hole_editor" in inventory
    assert "must decompose" in inventory.lower() or "decompose" in inventory.lower()


def test_issue293_design_and_plan_pin_machine_proof_without_weakening_t8_gate():
    design = DESIGN.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    for text in (design, plan):
        assert ACCEPTED_PREDECESSOR in text
        assert RECONCILIATION_RUN in text
        assert "5,884" in text
        assert "2,500" in text
        assert "Phase 2" in text
        assert "transient editor" in text.lower()
