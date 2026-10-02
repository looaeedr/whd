# Phase 4 T7 — Composition-root integration + bridge compatibility compression

## Identity
- Master: #388
- Task: #396 / T7
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T6 accepted candidate: `f5b3bd7ad64d9c4d18e676296a95de67de34b94e`
- Final tested HEAD: `117655828de9b1a08c4ebd5f29cabf64b006ce76`

## RED
Intended RED RUN: `35474088311` / job `105980193401`
- focused pytest: **4 FAIL / 3 PASS**
- existing adapter had no `Phase6FoldDesignerComposition`
- bridge still directly constructed 5 deep owners
- composition root owned none of those constructors
- facade binding count had grown from T0 70 to **74**
- marker: `ISSUE396_T7_EXPECTED_RED=1`

## GREEN
Final authoritative GREEN RUN: `35474402853`
- Headless job `105981039462`: SUCCESS
- Xvfb job `105981039365`: SUCCESS

Headless:
- T7 composition contracts: **7 PASS**
- Settings ownership/semantic regressions: **32 PASS**
- Final Scene ownership/focused regressions: **58 PASS / 3 SKIP**
- Settings predecessor A/B: `UNEXPLAINED_SETTINGS_DELTA=0`
- `SETTINGS_BRIDGE_REBIND=0`
- `SETTINGS_SCALAR_MIRROR_WRITES=0`
- `FINAL_SCENE_OWNER_DEREF=0`
- `FINAL_SCENE_DYNAMIC_SERVICE_LOOKUP=0`
- `FINAL_SCENE_BRIDGE_MIRROR=0`
- `DIRECT_CLASS_WIRING=0`
- `FACADE_BINDING_COUNT=69`
- `FACADE_BINDINGS_GROWTH=0`
- `ISSUE396_T7_SCOPE_GREEN=1`
- `ISSUE396_T7_PROTECTED_DRIFT=0`

Xvfb:
- composition real UI/renderer regressions: **55 PASS**
- `ISSUE396_T7_XVFB_GREEN=1`

## Implementation
The existing `gui_modules/application/fold_designer_adapter.py` is the single composition root. No second `fold_designer_composition.py` root was created.

Added:
- `FinalSceneCompositionPorts`
- `Phase6FoldDesignerComposition`

Composition root now owns construction/lifetime of:
- `Phase6SettingsTransactionService`
- `Phase6SettingsTransactionController`
- `FinalSceneDependencies`
- `Phase6FinalSceneRenderer`
- `Phase6FinalSceneViewAdapter`

Bridge now supplies typed callback ports and delegates deep-owner construction to the composition root.

Compatibility compression:
- four T3 Settings scalar compatibility properties moved to one composition-backed `__getattr__`
- `queue_update` / `do_update` are instance-bound before inherited Tk construction so trace callbacks keep orchestration semantics without class-facade slots
- facade bindings reduced **74 → 69**, below T0 hard ceiling 70

## Recovery notes
Earlier GREEN runs:
- `35474287763`: stale T3 structural test required direct `_phase6_settings_service` reference in bridge factory
- `35474344710`: stale T4 structural test required direct `FinalSceneDependencies(` construction in bridge

Both tests were evolved to verify the same ownership invariant at the T7 composition root. No production semantic remediation followed those stale-test failures.

Next: #397 T8 cumulative fixed-root A/B / cleanup / closure.
