# Phase 4 T5 — Pure Final Scene projection extraction

## Identity
- Master: #388
- Task: #394 / T5
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T4 accepted candidate: `40f09602dcf1be3d08f859ab88a9780cad075fc5`
- Final tested HEAD: `6b01993014e05139258daaae72633a386bd0217d`

## RED
Intended RED RUN: `35472607378`
- workflow SUCCESS while focused pytest intentionally RED
- **4 FAIL**
- `phase6_final_scene_projection.py` missing
- 22 projection helpers still defined in `phase6_final_scene_view.py`
- marker: `ISSUE394_T5_EXPECTED_RED=1`

## GREEN
Final GREEN RUN: `35472958786`
- Headless job `105977180631`: SUCCESS
- Xvfb job `105977180541`: SUCCESS

Headless:
- T5 projection owner tests: **5 PASS**
- 22-definition predecessor↔candidate AST fingerprint: exact match
- `UNEXPLAINED_3D_PROJECTION_DELTA=0`
- projection/domain matrix: **44 PASS / 5 SKIP**
- `FINAL_SCENE_PROJECTION_RENDERER_MUTATION=0`
- `FINAL_SCENE_PROJECTION_TK_REFS=0`
- `FINAL_SCENE_PROJECTION_REVERSE_IMPORTS=0`
- `FINAL_SCENE_DUPLICATE_PROJECTION_FORMULAS=0`
- `ISSUE394_T5_SCOPE_GREEN=1`
- `ISSUE394_T5_PROTECTED_DRIFT=0`

Xvfb:
- Final Scene real-view regressions: **32 PASS**
- `ISSUE394_T5_XVFB_GREEN=1`

## Implementation
Added `phase6_final_scene_projection.py` and moved the pure projection/calculation owner out of the view:
- profile base/geometry/fold mask
- flat/folded mapping
- folded mesh wrapper
- feature-segment extraction
- fitted limits
- scene fold boundaries/profile remapping
- fold ownership exemptions
- outside envelope/operator fold values
- contract profile rows
- box-body physical-piece projection helpers
- operator info formatting
- triangle bounds/assembly placement wrapper
- assembly-scene DTO projection

`phase6_final_scene_view.py` imports/re-exports the pure helpers and retains renderer + adapter ownership.

Bridge compatibility for `_phase6_make_assembly_scene_render_data` now delegates directly to the pure projection owner; it no longer constructs an adapter without dependencies.

## Recovery notes
- RUN `35472766731`: extraction script truncated one multiline function signature; syntax/harness defect only.
- RUN `35472831527`: revealed the remaining pure assembly DTO projection seam; matrix otherwise 43 PASS / 5 SKIP and Xvfb GREEN.
- Intermediate push runs were superseded. Only `35472958786` at exact tested HEAD `6b019930...` is acceptance evidence.

Next: #395 T6 Final Scene renderer/runtime extraction + owner/service-bag removal.
