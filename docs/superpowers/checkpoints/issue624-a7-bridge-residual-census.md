# Issue #624 / Phase 7 A7 — fresh residual Bridge deletion-test census

Schema: WHD_PHASE7_A7_BRIDGE_RESIDUAL_CENSUS_V1

- Issue: #624
- Master: #627
- Approved RED: P7-R-A
- Frozen X base: `b61db24e4428100b7e7d627ae946a04f93ca0f8b`
- Accepted predecessor / A6 head: `99e389de4e82ad5e34f80cc91e2e83aab0dd0f7d`
- Census branch: `work/issue627-phase7-large-module-decomposition-20260924`
- Census input Bridge SHA: `0bd6b1c412dc2aeff7ce1e389ca2aeecb11d6217`
- Bridge size at census: 6477 lines
- Decision rule: LOC is evidence only; removal requires fresh NO_CALLER/SUPERSEDED evidence and protected compatibility seams stay intact.

## DT-0 — target characterization

A7 runs after A2–A6 deeper owners exist. The residual target is not “make Bridge small”; it is to remove only responsibilities that no longer have a runtime/facade caller while preserving the accepted compatibility root.

Protected KEEP boundaries:

- `_fix11_init`: atomic bootstrap / predecessor / legacy host / workspace / view install order.
- `_fix11_activate_part`: Part Editor transaction ordering, especially plan → outgoing save → begin → finish.
- `_phase6_submit_update_intent`: compatibility delegate into `gui_modules.application.command_router`; scheduler ownership remains outside Bridge.
- legacy workspace properties / host facade entries still installed through the one `install_fold_designer_bridge_facade` root.
- no `phase6_part_editor_session.py` move-only owner; prior C-KEEP decision remains valid unless a later DT proves a real deep owner boundary.

## DT-1 — fresh top-level reference census

For each top-level Bridge function below, exact-name occurrence count in the A7 Bridge source is **1**: the definition itself. Therefore there is no Bridge caller, alias assignment, facade binding, or callback wiring in the current A7 source.

Default-branch repository code search for the same exact names returned no external references.

```
_phase6_active_mesh_profiles
_phase6_query_assembly_render_data
_phase6_final_scene_view_request
_phase6_final_scene_set_preview_enabled
_phase6_commit_output_draw_stock
_phase6_export_selected_dxf_from_3d
_phase6_refresh_sticky_structure_tree
_phase6_install_keyboard_shortcuts
_phase6_toggle_parameter_panel
_phase6_save_settings_context_as_defaults
```

Classification for this slice: `NO_CALLER`.

## DT-2 — protected compatibility evidence

Fresh Bridge source still shows:

- `_fix11_activate_part` is a substantial compatibility coordinator and is installed as `activate_part`; it must not be deleted or shallow-moved merely for LOC reduction.
- `_fix11_init` is installed as `__init__` and defines lifecycle ordering.
- `_phase6_submit_update_intent` is installed as `submit_update_intent` and delegates scheduling to command_router.
- composition accessors have multiple live in-Bridge callers and are not in the NO_CALLER deletion set.

Classification: `KEEP_COMPATIBILITY` for this pass.

## DT-3 — P7-R-A RED decision

RED requires:

1. the ten fresh `NO_CALLER` helpers above are absent from Bridge;
2. Part Editor activation ordering remains unchanged;
3. update scheduler remains command-router-owned;
4. bootstrap/lifecycle/install-order remains intact;
5. no reverse import / second composition root / shallow Part Editor session is introduced.

Expected pre-implementation result: first assertion RED because the ten NO_CALLER definitions still exist; protected KEEP assertions should remain GREEN.

## DT-4..DT-6

Pending implementation + focused/broader acceptance. A7 must update this artifact with terminal evidence before closure.


## DT-4 — broader runtime/facade readback correction

Broader acceptance run `36246541254` disproved two DT-1 classifications. The names
`_phase6_refresh_sticky_structure_tree` and `_phase6_install_keyboard_shortcuts`
have no direct Bridge caller, but they are live compatibility ports consumed through
`gui_modules/application/fold_designer_adapter.py` via the composition namespace.

Observed evidence:

- owner-boundary slice before GUI readback: `83 passed, 2 skipped`
- original Bridge / GUI compatibility step: `22 failed, 25 passed`
- repeated failure root:
  `Fold Designer composition port is unavailable: _phase6_install_keyboard_shortcuts`
  and `_phase6_refresh_sticky_structure_tree`

Corrected classification:

- `_phase6_refresh_sticky_structure_tree`: `KEEP_COMPATIBILITY_PORT`
- `_phase6_install_keyboard_shortcuts`: `KEEP_COMPATIBILITY_PORT`
- remaining eight helpers from DT-1: `NO_CALLER`

The correction preserves the A7 rule that repository/facade/runtime readback outranks
Bridge-local occurrence count. It does not restore the other eight dead helpers and
does not transfer scheduler/workspace ownership back into Bridge.


## DT-4b — second broader runtime/facade readback correction

Exact broader verification run `36246812185` at `6c9771cc936cbd7cc368a115ca2348a404a1bb66`
kept the owner-boundary slice GREEN (`84 passed, 2 skipped`) but exposed two additional
namespace-driven compatibility ports that Bridge-local occurrence counting had misclassified.

Runtime evidence:

- `_phase6_final_scene_view_request` is consumed by
  `Phase6FoldDesignerComposition.final_scene_ports(...).request_provider` through
  `required("_phase6_final_scene_view_request")`; deleting it changes the legacy
  missing-provider path into a composition-port failure.
- `_phase6_save_settings_context_as_defaults` is consumed by
  `Phase6FoldDesignerComposition.settings_panel(...).save_defaults` through
  `required("_phase6_save_settings_context_as_defaults")`; deleting it breaks the
  current-context Settings save callback.
- GUI compatibility readback before this correction: `2 failed, 45 passed`.

Corrected classification:

- `_phase6_final_scene_view_request`: `KEEP_COMPATIBILITY_PORT`
- `_phase6_save_settings_context_as_defaults`: `KEEP_COMPATIBILITY_PORT`
- the remaining six P7-R-A deletion targets stay `NO_CALLER`.

This correction does not move FinalScene or Settings ownership back into Bridge. Both restored
functions are bounded delegates into the existing composition/deep owners. Runtime/facade
readback continues to outrank Bridge-local text occurrence counts.
