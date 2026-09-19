# Issue #358 T4 — remove manufacturing bridge-callback dependency

## Identity
- Master: #353
- Task: #358 / T4
- Predecessor: #357 accepted HEAD `cffa5dbcdc1a2eb8d69479f8c5b59336930be219`
- Fixed semantic baseline / production remains `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Branch: `refactor/issue358-remove-manufacturing-callbacks-20260919`
- Final tested SHA: `d179e7c46868fbddb9f5aa72a4aad89bc006fb29`

## RED
Initial T4 RED RUN `35404700613`:
- **6 FAIL / 9 PASS**
- failures matched the intended missing architecture:
  - Phase 1 callback registry still present
  - request/result resolver missing
  - three Phase-1-only class wirings still present
  - bridge facade not routed through adapter
  - adapter lacked explicit input providers
  - signature-first app resolver absent

## Focused GREEN
RUN `35405039046` / job `105792917743`:
- **15 PASS / 0 FAIL**
- proved callback registry removal, request/result routing, wiring retirement and prior T2/T3 contracts

A new `SyntaxWarning` at `phase6_manufacturing_geometry.py:301` was detected and removed before final acceptance.

## Expanded parity GREEN
RUN `35407867898` / job `105801256464`:
- **70 PASS / 3 SKIP / 0 FAIL**
- no SyntaxWarning

Expanded suite includes:
- GUI manufacturing adapter
- #295 T7 manufacturing adapter slice
- #347 manufacturing helper extraction
- #349 explicit joint relief extraction
- #350 orchestration extraction contract evolved for T4
- #351 durable compatibility gate evolved for T4
- #355 / #356 / #357 Phase 2 contracts
- #358 callback-removal contracts
- manufacturing API / finished-face / collision dependency / policy boundary
- resolved manufacturing bridge / export / geometry

## Architecture accepted
Service/domain owner now has:
- `bridge_callback_registry_refs = 0`
- `_phase6_call_bridge refs = 0`
- `_phase6_bind_bridge_callbacks refs = 0`
- zero reverse import from `fold_designer_bridge`

Current routing:
```text
bridge facade
  -> phase6_manufacturing_adapter.resolve_manufacturing_for_app
  -> immutable ManufacturingResolveRequest
  -> phase6_manufacturing_geometry._phase6_resolve_manufacturing_result
  -> ManufacturingResolveResult
  -> adapter applies legacy compatibility state
  -> bridge executes explicit publish effect
```

## Wiring lifecycle
Removed Phase-1-only class wiring:
- `_phase6_mesh_profiles_for_part`
- `_phase6_operator_finished_dimensions`
- `_phase6_scene_query_payload_for_part`

Retained deliberately:
- `_phase6_publish_live_state` class wiring — pre-existing compatibility wiring, Phase 3 review

The old binder registry itself is removed.

## Compatibility correction found by expanded parity
The expanded suite found a real legacy provider-arity regression in the new facade.
The facade now accepts both:
- current `_phase6_operator_finished_dimensions(self, key)`
- legacy monkeypatched one-argument `_phase6_operator_finished_dimensions(self)`

Resolved bridge parity returned GREEN after this correction.

## Cache contract
The Phase 1 signature-first short-circuit is still ahead of full immutable request construction.
Cache ownership extraction is deferred to #359 / T5.

Next: #359 / T5 cache ownership + hit/miss parity.
