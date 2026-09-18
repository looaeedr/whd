# Issue #346 T1 — Manufacturing characterization baseline

## Identity
- Master: #344
- Task: #346 / T1
- Predecessor accepted: #345
- Predecessor HEAD: `75e4f81f365c74ec0e255e847f3db5551c85f6da`
- Branch: `refactor/issue346-manufacturing-characterization-20260918`

## Purpose
Lock the current manufacturing/joint-relief observable behavior before any Phase 1 move-only extraction.

## Baseline matrix
The branch QA workflow runs the same focused suite in:
- Headless
- Xvfb

Coverage includes:
- canonical ResolvedManufacturingGeometry
- USER_ADDED / WRAP / replay / invalidation
- Head/Tail assembly relief and atomic rollback
- joint world-geometry / UV mapping
- Receiving bottom registry and Divider ownership
- multi-WRAP fixed-point replay
- multipart Receiving identities and project round-trip
- 2D ↔ 3D round-trip and idempotence
- DXF/export resolved-data ownership
- project serialization
- cache ownership / baseline cache

Final RUN IDs and totals are appended after terminal classification.
