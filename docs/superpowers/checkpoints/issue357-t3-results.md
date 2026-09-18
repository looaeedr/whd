# Issue #357 T3 — explicit manufacturing result contracts

## Identity
- Master: #353
- Task: #357 / T3
- Predecessor: #356 accepted HEAD `9a8d647cd537a4ff9e8abf52f3b8daee0e3aa0e0`
- Fixed semantic baseline: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`

## RED
RUN `35404184287`:
- **4 FAIL / 1 PASS**
- exact missing result contracts / adapter-apply RED
- canonical resolver unchanged guard PASS

## GREEN
RUN `35404266626` / job `105790634960`:
- **5 PASS / 0 FAIL**

## Contracts
Added explicit immutable envelopes:
- `ManufacturingDiagnosticsResult`
- `ManufacturingMutationResult`
- `ManufacturingEffects`
- `ManufacturingCacheReceipt`
- `ManufacturingResolveResult`

Metadata/patch containers are defensively frozen. Existing geometry/solver domain objects remain opaque domain objects inside immutable envelopes instead of being incorrectly JSON-coerced.

## Legacy apply compatibility
`apply_manufacturing_result(app, result)` explicitly maps result state back to:
- `_phase6_last_interference_probe_parts`
- `_phase6_last_relief_errors`
- `_phase6_last_relief_solutions`
- `_phase6_last_resolved_manufacturing_geometry`
- `_phase6_last_resolved_manufacturing_signature`
- snapshot patch

It deliberately does **not** execute `ManufacturingEffects`; no hidden live callback is triggered.

## Scope
Canonical manufacturing resolver remains on the Phase 1 path. T3 adds result contracts/application only.

Next: #358 / T4 bridge-callback dependency removal.
