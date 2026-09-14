# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Current role: T5 實作者
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`
- Active PR: #223

## Dependency inventory
Run `34825565059`: inventory itself GREEN.
- AST inventory GREEN
- repo-wide caller search GREEN
- analysis-only production drift=0

## First approved slice
`BoxCalculatorGUI._phase6_logical_part_present`
- AST: 0 `self` reads / 0 writes
- category: PURE_PRESENTATION
- function projects authoritative physical IDs into logical top-level UI presence only
- no geometry/state/persistence/visibility/active-child authority
- compatibility surface remains `BoxCalculatorGUI._phase6_logical_part_present` via static binding.

## QA correction
Earlier characterization/acceptance workflows used `command | tee` without `set -o pipefail`, so GitHub step status falsely reported GREEN despite command failures. Full logs proved:
- characterization run `34825759867`: actually `1 failed, 34 passed, 5 skipped`;
- acceptance run `34826685129`: actually `1 failed, 97 passed` plus validator failure;
- inherited failing test: `test_confirm_existing_parts_updates_main_2d_export_presence_flags`;
- the same failing assertion exists before the T5 production move and conflicts with current production authority: physical presence must not rewrite DXF export-checkbox intention.

Blocker split to #224 on fresh test-only branch `test/issue209-inherited-export-selection-contract-20260914` from accepted T4 SHA.

## Current branch state
- `gui_modules/part_panels.py` owns the projector implementation;
- `gui.py` contains compatibility import + `staticmethod` binding;
- validator is pinned to accepted T4 SHA `a098498d7459e974bbf18a5573e6b209eaeb4404`, never a movable branch ref;
- T5 workflow is fail-closed with `set -o pipefail` for preflight/validator/pytest;
- current gate records inherited base/current stale-test failure separately and runs remaining L1/L4 scope without masking failures.

## Hard boundaries
- physical identity remains authoritative;
- logical `box_body` grouping does not replace nested physical child navigation;
- visibility remains renderer-only;
- no Event Bus/Store/geometry/DXF/persistence authority in `part_panels.py`;
- validation failures must never be hidden by `tee`.

## Pending
1. fail-closed T5 first-slice acceptance excluding only documented inherited #224 stale assertion;
2. migrate #224 test-only contract on independent branch and verify no production diff;
3. integrate #224 test migration into T5 lineage;
4. rerun full T5 scope with no exclusions;
5. cleanup temporary workflows/scripts and perform cleaned-head drift audit;
6. only then decide T5 close / second slice HOLD.
