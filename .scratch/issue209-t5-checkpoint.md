# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`
- Active PR: #223

## First approved slice
`_phase6_logical_part_present`
- accepted owner: `Phase6ApplicationHost`;
- public compatibility resolves on `BoxCalculatorGUI` by inheritance;
- category: PURE_PRESENTATION; 0 self reads/writes.

## Accepted first-slice evidence
Run `34827516591 @ 5d509f7667b44f2a6c9e98f6853de00a5dedc9ce`:
- fail-closed Preflight GREEN;
- exact AST Move-Only GREEN;
- compatibility/import direction GREEN;
- inherited stale contract proven on both T4 base and T5 current (`base_rc=1 current_rc=1`);
- residual Xvfb: 97 PASS / 0 FAIL / 1 deselected;
- config/baseline invariants + allowed diff GREEN.

## #224 migration
- independent test-only acceptance run `34827792898 @ eb64047ae6ae576dce339fd3809c858f39348fb6`: 29 PASS / 5 SKIP / 0 FAIL;
- only non-scratch diff from accepted T4 was `tests/test_phase6_linked_fold_chain_and_parts.py`;
- config/baseline invariants GREEN;
- accepted #224 test blob was transplanted alone into T5 as commit `738bb24912818e19d18a7c18937e383ace7dfd12`;
- no #224 scratch/QA-runner files were integrated.

## Current gate
Registered T5 workflow now runs full no-exclusion scope under pipefail:
1. Phase6 preflight;
2. exact AST Move-Only + compatibility/import direction;
3. full Xvfb L1/L4 regression with no `-k` exclusion;
4. config/baseline invariants;
5. allowed T5 diff including accepted #224 test migration;
6. exact tested HEAD.

## Pending
- terminal full no-exclusion acceptance;
- inventory review for any additional SAFE T5 panel slice vs HOLD;
- durable QA lesson sync (`tee` requires pipefail; validators pin immutable accepted SHA);
- temporary workflow/script cleanup and cleaned-head drift audit;
- #224 / #209 closure only after those gates.
