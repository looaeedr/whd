# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Current role: T5 實作者
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`
- Active PR: #223

## Dependency inventory
Run `34825565059`: inventory evidence collected; production drift=0.

## First approved slice
`_phase6_logical_part_present`
- accepted owner is `Phase6ApplicationHost`, not `BoxCalculatorGUI`;
- `BoxCalculatorGUI` inherits `Phase6ApplicationHost`, so the public compatibility surface still resolves there;
- AST inventory: 0 `self` reads / 0 writes;
- category: PURE_PRESENTATION only;
- no geometry/state/persistence/visibility/active-child authority.

## QA correction
Earlier characterization/acceptance workflows used `command | tee` without `set -o pipefail`; raw logs exposed false GREEN statuses. The gate is now fail-closed.
- inherited stale test is #224;
- #224 exists on fresh test-only branch from exact accepted T4 SHA;
- validator is pinned to exact accepted T4 SHA and now validates the actual owner class `Phase6ApplicationHost`;
- production source is unchanged by these QA fixes.

## Current gate
1. Phase6 preflight with pipefail;
2. accepted-parent-vs-moved AST contract on `Phase6ApplicationHost`;
3. current static binding + `BoxCalculatorGUI(Phase6ApplicationHost)` inheritance compatibility;
4. explicit inherited #224 base/current RED evidence;
5. all remaining L1/L4 scope under Xvfb with pipefail;
6. config/baseline invariants and allowed diff.

## Pending
- terminal result for owner-corrected gate;
- #224 test-only migration;
- integrate #224 into T5 lineage and rerun full scope without exclusion;
- cleanup + cleaned-head drift audit;
- review remaining T5 inventory for SAFE vs HOLD before closure.
