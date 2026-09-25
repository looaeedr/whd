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


## Terminal evidence

### Candidate characterization
RUN `35357605585`

- Headless: **140 PASS / 16 SKIP / 0 FAIL**
- Xvfb: **154 PASS / 2 FAIL**
- Xvfb failures:
  - `tests/test_phase6_assembly_3d_view.py::test_real_tk_part_selector_starts_in_assembly_and_switches_to_single_part`
  - `tests/test_phase6_assembly_3d_view.py::test_real_tk_menu_can_switch_from_assembly_to_boxbody_after_radiobutton_sets_label_first`
- Both fail on the same stale expectation: live UI value is `箱身`, legacy test expects `組合體`.

### Predecessor A/B classifier
RUN `35357899165`, exact predecessor checkout `75e4f81f365c74ec0e255e847f3db5551c85f6da`

- `tests/test_phase6_assembly_3d_view.py`: **20 PASS / 2 FAIL**
- exact same two node IDs
- exact same `箱身` vs `組合體` assertion

Classification: **INHERITED_BASELINE_RED**.

Machine-readable contract:
`config/issue346_t1_xvfb_failure_contract.json`

## T1 acceptance

The manufacturing characterization baseline is locked.

- no production implementation change in T1
- no new manufacturing/joint-relief failure
- candidate Headless fully GREEN
- Xvfb delta against predecessor = 0 unexpected failures
- inherited RED set = exact 2-node contract above

Next predecessor-gated task: #347 / T2.
