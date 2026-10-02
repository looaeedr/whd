# Phase 4 T6 — Final Scene renderer/runtime extraction

## Identity
- Master: #388
- Task: #395 / T6
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T5 accepted candidate: `b24625cbc9a75223c02eb16a6128923323c573f5`
- Final tested HEAD: `f54916f4fba5f89e8aeaa9dddc672d055aedf92c`

## RED
Intended RED RUN: `35473307539` / job `105978104609`
- focused pytest: **6 FAIL**
- renderer owner module absent
- adapter still held app owner/runtime state
- bridge compatibility mirror remained
- view facade exceeded quantitative target
- marker: `ISSUE395_T6_EXPECTED_RED=1`

## GREEN
Final authoritative GREEN RUN: `35473914319`
- Headless job `105979726664`: SUCCESS
- Xvfb job `105979726721`: SUCCESS

Headless:
- renderer ownership/contracts: **11 PASS**
- renderer predecessor A/B fingerprint: **19 methods, delta = 0**
- focused Final Scene regressions: **50 PASS / 3 SKIP**
- `UNEXPLAINED_3D_RENDER_DELTA=0`
- `FINAL_SCENE_OWNER_DEREF=0`
- `FINAL_SCENE_DYNAMIC_SERVICE_LOOKUP=0`
- `FINAL_SCENE_BRIDGE_MIRROR=0`
- `FINAL_SCENE_FACADE_LINES_OVER_LIMIT=0`
- `FINAL_SCENE_FACADE_SELF_REFS_OVER_LIMIT=0`
- `FINAL_SCENE_FACADE_UNIQUE_ATTRS_OVER_LIMIT=0`
- `ISSUE395_T6_SCOPE_GREEN=1`
- `ISSUE395_T6_PROTECTED_DRIFT=0`

Xvfb:
- real Tk / Matplotlib regressions: **35 PASS**
- `ISSUE395_T6_XVFB_GREEN=1`

## Quantitative end state
`phase6_final_scene_view.py`:
- **374 lines**
- **20 literal self refs**
- **7 unique self attrs**

Hard limits:
- lines <= 750
- literal self refs <= 48
- unique self attrs <= 12

`phase6_final_scene_renderer.py`:
- **935 lines**
- renderer/runtime state owner only

## Implementation
- added `phase6_final_scene_renderer.py`
- moved Matplotlib renderer mutation/runtime state out of the adapter/view facade
- adapter no longer holds app owner
- renderer imports no bridge/gui owner
- removed `_phase6_sync_final_scene_view_compatibility_mirrors`
- removed `mirror_view_state` dependency
- legacy view state is read-through to the renderer/runtime source
- bridge imports projection helpers and renderer class/constants from canonical owners
- renderer re-exports contract DTO aliases for legacy module consumers without taking ownership
- query-only adapter paths can operate without a renderer; actual render/install/scroll fail closed when renderer is absent
- operator-dimension callback compatibility supports old one-arg and new part-aware providers without restoring dynamic service dispatch

## Recovery notes
Several superseded intermediate GREEN runs exposed compatibility seams only:
- projection/renderer canonical import ownership
- query-only renderer construction
- contract DTO re-export
- explicit dependency local binding
- operator-dimension callback arity

No projection formula changes were made. `phase6_final_scene_projection.py` blob remained byte-identical to T5 accepted.

Next: #396 T7 composition-root integration + bridge compatibility compression.
