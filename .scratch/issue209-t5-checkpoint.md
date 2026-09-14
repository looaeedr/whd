# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Current role: T5 實作者
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`
- Active PR: #223

## First approved slice
`_phase6_logical_part_present`
- accepted owner: `Phase6ApplicationHost`;
- public compatibility resolves on `BoxCalculatorGUI` by inheritance;
- category: PURE_PRESENTATION; 0 self reads/writes.

## QA state
- fail-closed pipefail is active;
- #224 tracks inherited stale export-selection test contract on a fresh test-only branch;
- source validator is pinned to accepted T4 SHA;
- latest owner-corrected run proved a real AST body mismatch, so no acceptance yet.

## Diagnostic gate
Validator now prints parent and moved AST node dumps on mismatch. This checkpoint triggers the diagnostic run. No production source is changed by this diagnostic.

## Pending
1. identify exact AST body delta;
2. restore moved helper to exact accepted Move-Only body;
3. rerun fail-closed acceptance;
4. migrate and integrate #224 test-only contract;
5. full no-exclusion T5 regression, cleanup and drift audit.
