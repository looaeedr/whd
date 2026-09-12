# DM7 T1 Checkpoint

- Task: #167 — Navigation contract + RED guards
- Parent: #166
- Role: T1 實作者 → 總控審查待交接
- Branch: `test/dm7-t1-navigation-red-guards-20260913`
- Baseline target: `cleanup/2d-3d-sync@e85b10b3bf7957e626abb7c1e1e1f909b1f0ee62`
- Tested head: `2ed2bb2b2f932f07c8596458ef825362016f879b`
- One-shot workflow cleanup commit: `9501ba97535b27e4dd3097c1ba5b77bfb2e91e3f`
- Remote run: `34708622285`
- Remote job: `103593164619`
- Owning Issue: https://github.com/looaeedr/whd/issues/167

## Completed

- Phase6 Knowledge Preflight GREEN for task + all known changed files.
- Fresh branch created from exact latest target.
- Added `docs/superpowers/plans/2026-09-13-dm7-navigation-red-guards.md`.
- Added `tests/test_dm7_part_navigation.py` with seven navigation contracts.
- Superseded legacy #96 stale-child fallback oracle with fail-closed expectation.
- Remote requirement RED reached terminal on exact tested head.
- One-shot workflow removed after terminal run.
- No production source changed.

## Requirement RED evidence

Remote run `34708622285 @ 2ed2bb2b2f932f07c8596458ef825362016f879b`:

- install/setup: PASS
- T1 scope guard: PASS
- `config.ini` before/after: exact `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
- protected `基準檔/**` manifest before/after: PASS
- pytest: **3 failed / 11 passed / 1 warning / 1.42s**

Exact requirement REDs:

1. `test_dm7_stale_explicit_child_fails_closed_instead_of_using_valid_remembered_sibling`
   - expected `None`
   - actual `box_body:back`
2. `test_dm7_stale_remembered_child_is_cleared_instead_of_falling_to_first_child`
   - expected `None`
   - actual `box_body:back`
3. `test_multipart_stale_child_fails_closed_and_clears_stale_memory`
   - expected selected identity `None`
   - actual `box_body:right_side`

Classification: **VALID REQUIREMENT RED**. Failures are assertion-level navigation-contract violations in current production behavior, not dependency/import/setup/workflow failures.

## Pending

- Independent QA review of branch diff vs target.
- Confirm workflow cleanup and tested-head → closing-head non-production drift only.
- Write terminal evidence to Issue #167 and close T1 if QA accepts.

## T1 stop boundary

Do not implement #168/T2 production resolver in this ticket. T1 ends with permanent RED contracts + reproducible requirement RED evidence.
