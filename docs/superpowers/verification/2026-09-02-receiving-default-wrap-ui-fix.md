# 2026-09-02 Receiving Default / WRAP UI Ownership Verification

## Root causes
1. `fold_designer_bridge._phase6_store_editor_values()` treated every non-bool setting as numeric. `ui_text_size="medium"` raised `ValueError` inside the receiving family transaction, leaving snapshot and live UI out of sync.
2. Receiving family switch wrote BOTTOM=WRAP directly and two 3D Checkbuttons could also own the same relation, conflicting with the canonical Assembly Intent → Resolved AssemblyJoint Graph chain.

## Corrected contract
- Receiving family defaults are W=800, H=1600, D=350 and commit atomically across snapshot, live settings, 3D W/H/D vars, and main GUI.
- Receiving family alone never invents WRAP.
- `包覆貼外` is the high-level preset that projects BOTTOM=WRAP.
- No standalone `啟用外側包覆` / `啟用 WRAP` relation control exists in 3D.
- When the canonical bottom Joint is WRAP, the unlocked EndCap page exposes reserve X/Y only; reserve edits do not mutate the Joint relation.

## TDD / fresh verification
- RED: `test_live_switch_to_receiving_rebases_whd_with_string_ui_setting_in_snapshot` failed with live `_settings_values` still `400/600/250` while snapshot was `800/1600/350`.
- RED: Receiving default semantic test returned `enabled=True`; GUI/main-family tests returned `BOTTOM=WRAP` immediately after family selection.
- GREEN direct affected files:
  - `tests/test_phase6_receiving_followup_20260830.py`: 6 passed
  - `tests/test_receiving_bottom_wrap_linkage.py`: 3 passed
  - `tests/test_receiving_cabinet_2d.py`: 13 passed
  - `tests/test_corner_parameter_lock.py`: 12 passed
  - total: 34 passed, 0 failed
- GREEN ownership/registry layer: `test_rebuild_t1_t2_joint_graph.py`, `test_rebuild_t3_intent_graph_ui.py`, `test_rebuild_t6_receiving_joint_ownership.py`, `test_assembly_joint_serialization.py`, `test_certified_relief_runtime_contract.py`, `test_receiving_bottom_wrap_registry.py`: 53 passed, 0 failed.

## Integrity
- `config.ini` SHA256 = `e0d8e0c9a6db736f1f7882ff2246cb2845467431bafa583f81a35a0e1d551dc5`; unchanged by this task.
- Preflight evidence: `docs/superpowers/verification/2026-09-02-receiving-default-wrap-ui-preflight.md`.
