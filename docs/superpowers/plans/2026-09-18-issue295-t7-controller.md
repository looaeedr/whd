---
whd_doc_role: REFERENCE
whd_contract: issue295-t7-controller-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #295 T7 — implementation plan

## Identity
- Parent: #287
- Task: #295 / T7
- Accepted predecessor: #294 @ `936d50970b5d360f304f88c76215e3aa3ebe7de2`
- Work branch: `refactor/issue295-gui-phase2-t7-controller-20260918`
- Design: `docs/superpowers/specs/2026-09-18-issue295-t7-controller-design.md`
- Scope census: `35310346416`
- Final structural gate: `gui.py <= 2,500`
- Production integration remains #296/T8 responsibility.

## Execution rule
Every behavior-moving slice uses:

```text
characterization RED
→ verify intended failure provenance
→ minimal extraction GREEN
→ focused regression
→ commit
```

No concrete Actions RUN ID means `RUN_NOT_CREATED`: fix trigger/ref/prerequisite immediately and poll only after a concrete RUN exists.

## Task 1 — Fresh scope census and hard-gate lock [DONE]
Run `35310346416` on exact predecessor `936d5097…`:
- root 4,718;
- hard gate 2,500;
- required removal 2,218;
- current T7-labelled surface 2,310;
- all-T7 zero-wiring theoretical root 2,408.

Conclusion: gate stays fixed. HOLD adapter rows must be proved and extracted; wrappers must be collapsed aggressively but safely.

## Task 2 — Architecture / ownership RED
Create `tests/test_issue295_gui_phase2_t7_controller.py`.

RED must prove:
- focused T7 application/project/visibility modules are not yet the owners;
- key T7 root methods remain real implementations;
- new modules may not import `gui` or compatibility exports;
- project schema owner remains outside GUI modules;
- WorkspaceController remains physical presence/active-part owner;
- manufacturing adapters delegate to existing engine/manufacturing authority;
- module/class/method size gates;
- hard root gate `<=2500`.

## Task 3 — State-sync and init-variable split
Characterize the current state initialized by `init_variables`.

Extract focused initialization/state-sync helpers without creating a second committed state store. Move shared T4/T7 serializers/sync routing where proven.

Focused evidence:
- settings snapshot parity;
- corner state parity;
- door/multipart state parity;
- project/workspace owner identity unchanged.

## Task 4 — Fold Designer application adapter
Characterize and extract:
- `_fold_designer_secondary_scene_rows`
- `_query_fold_designer_baseline_data`
- `_apply_cabinet_family_endcap_policy`
- `_fold_designer_corner_policy_from_payload`
- `_authoritative_render_data`
- `_require_verified_baseline_sources_for_manufacturing`
- `_export_authoritative_part`
- `_fold_designer_part_spec_from_payload`
- `_query_fold_designer_render_data`
- `_make_original_fold_designer_snapshot`

Separate projection/orchestration from authoritative engine calls. Do not move geometry authority.

## Task 5 — Cabinet/runtime controller
Characterize and extract:
- `_inherit_known_corner_state_into_custom`
- `_capture_cabinet_family_runtime`
- `_restore_cabinet_family_runtime`
- `_apply_cabinet_family_for_current_model`
- `on_baseline_changed`
- `get_float_values`
- indicator-result projection helpers.

Preserve SettingsService and existing host/controller owners.

## Task 6 — Calculation orchestration
Characterize `update_calculations` outputs/side effects and extract only orchestration.

Focused regressions cover:
- result value parity;
- update scheduler behavior;
- display refresh routing;
- no formula/source duplication.

## Task 7 — Manufacturing adapter
Characterize and extract:
- manufacturing context;
- box-body/endcap/door/base-plate/indicator spec adapters;
- relief signature/resolved committed relief cuts;
- indicator editor contexts.

Prove exact spec/result parity and that no geometry formula is newly authored in GUI modules.

## Task 8 — Export/project state adapter
Characterize and extract:
- multi-door DXF export routing;
- multi-door indicator-box export routing;
- selected DXF export routing;
- single/multi indicator state snapshot/apply.

Preserve ProjectController and manufacturing export authority.

## Task 9 — Visibility + compatibility/root cleanup
Move physical presence routing into `gui_modules/visibility/controller.py`.

Inventory all remaining root wrappers and callers. Collapse already-extracted implementation wrappers to direct aliases where safe.

Any compatibility shim retained must include the lifecycle metadata required by #295.

Hard check after this task:
```text
gui.py <= 2,500
```

## Task 10 — Focused T7 acceptance
L0:
- dependency direction;
- no duplicate owner/state;
- no GUI module imports `gui` or compatibility layer;
- size gates;
- `gui.py <=2500`.

L2:
- project/workspace/settings state parity;
- snapshot/apply parity;
- physical presence and active-part parity;
- manufacturing adapter contract parity.

L3:
- export routing;
- project open/save/reload;
- cabinet-family result routing;
- 2D/3D state synchronization.

L4 Xvfb:
- visibility/show-hide;
- multipart independent visibility;
- receiving/vault workflows;
- project open/save UI paths where applicable.

## Task 11 — Full Headless/Xvfb acceptance
Run candidate/predecessor full A/B.

Acceptance requires:
- candidate-only failures = 0;
- signature mismatches = 0;
- protected invariants GREEN;
- structural gate GREEN.

Inherited failures must be classified only by exact node/signature A/B evidence.

## Task 12 — Cleanup / closure guard
Remove temporary #295 workflows/helpers/checkpoints from the accepted candidate.

Fresh-read canonical #295 branch/head and Issue state. Build terminal checkpoint bound to:
- issue #295;
- branch `refactor/issue295-gui-phase2-t7-controller-20260918`;
- fresh clean candidate HEAD.

Use current production finalization guard authority out-of-tree if needed. Invoke:
- `assert-finalizable`;
- `authorize-finalization`;
- `verify-finalization-proof`.

Before remote branch deletion, live-fetch every OPEN PR and protect both head/base refs with `tools/branch_cleanup_ref_guard.py`.

Preserve the accepted #295 canonical branch for #296/T8 lineage.

Close #295 only after remote readback proves `closed/completed`.

## No production integration
Do not update production in T7.
