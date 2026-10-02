---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 280 / T5 Permanent TEST Move Manifest

Date: 2026-09-15
Task: #280 / T5
Pre-move task head: `d268511b4fb62a226ef303856387e0619889ea28`
Pre-move remote baseline: RUN `34992353304`, attempt 2 — SUCCESS — **42 PASS / 0 FAIL** — artifact `10405894006`

## Hard rule

This manifest is the complete authorization set for T5 path moves/splits. Files not listed here must remain in place. T5 does not create a new retirement decision, weaken an assertion, change expected behavior, or touch production/runtime sources.

## Whole-file moves

| Old path | New path | Responsibility | Contract action |
| --- | --- | --- | --- |
| `tests/test_phase6_semantic_doc_status.py` | `tests/governance/test_semantic_doc_status.py` | structured documentation governance | path-only move |
| `tests/test_issue76_box_body_subtabs_2d_3d.py` | `tests/ui/test_box_body_physical_child_navigation.py` | user-visible logical/physical box-body navigation | path-only move |
| `tests/test_box_body_single_source_t3.py` | `tests/architecture/test_box_body_single_source.py` | authoritative render/material single-source; no caller structural rebuild | path-only move |
| `tests/test_issue209_part_panel_projection.py` | `tests/projection/test_part_panel_projection.py` | logical presence projection without identity rewrite | path-only move |
| `tests/test_gui_drawing_contract.py` | `tests/ui/test_gui_drawing_contract.py` | durable drawing behavior | path-only move |
| `tests/test_gui_toolbar_contract.py` | `tests/ui/test_gui_toolbar_contract.py` | operator-facing toolbar semantics | path-only move |
| `tests/test_issue210_project_actions_move_contract.py` | `tests/architecture/test_project_actions_ownership.py` | project-action ownership and no reverse GUI dependency | path-only move |

For every whole-file move, the destination content must be byte-for-byte identical to the source content at the pre-move candidate except for a trailing newline normalization if GitHub API requires it. No test function body, marker, expected value, helper, import, or assertion may change.

## Approved #211 split

Source: `tests/test_issue211_renderer_dependency_gate.py`

### `tests/projection/test_renderer_behavior.py`

Move these nodes unchanged:

1. `test_behavior_draw_grid_preserves_current_canvas_contract`
2. `test_behavior_resolved_feature_projection_preserves_current_primitives`
3. `test_behavior_baseline_secondary_skips_primary_outline_and_bend_layers`

Copy only the test-only imports/constants/helpers required by those three nodes.

### `tests/architecture/test_renderer_ownership.py`

Move these nodes unchanged:

1. `test_structure_safe_helpers_move_to_render_2d_without_reverse_gui_dependency`
2. `test_structure_phase6_host_no_longer_defines_safe_helper_bodies`
3. `test_structure_existing_3d_deep_module_remains_the_only_new_3d_owner`

Copy only the test-only imports/constants/helpers required by those three nodes.

After both destination files exist, delete the old #211 file. There must still be exactly six #211-derived permanent nodes.

## Collection equivalence key

Whole-file moves preserve function names one-to-one. #211 preserves the six function names one-to-one across the two destinations. The post-move QA gate must compare pre-move and post-move function-name sets through this manifest and fail closed on:

- missing old function,
- duplicated destination function,
- unexplained new function,
- unexplained disappearance,
- destination outside the paths above.

## Non-authorized issue-number tests

Any other `tests/test_issue*.py` not explicitly listed above remains unchanged and in place. T5 must not infer that an issue-number filename is stale merely because of its name.

## Protected acceptance boundaries

- T2 `eb967e92c951cec8fde9c76d171a9685232a3ea2`, T3 `e1d484c247af5b7f384a8883d31357efb7820049`, and T4 `0eabb64a8308f74b9c8b66f982626d2907f00646` must remain ancestors of the final T5 candidate.
- Production source drift must remain `0`.
- `config.ini` and protected DXF manifest must remain unchanged.
- Existing display-gating markers are preserved; T5 may not add skip/xfail outcome controls.
- Final remote verification must include governance, UI/Xvfb, projection, architecture, collection equivalence, and protected invariants.
