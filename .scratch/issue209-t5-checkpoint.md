# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Current role: T5 實作者
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`
- Active PR: #223

## Dependency inventory
Run `34825565059`: SUCCESS.
- Phase6 preflight GREEN
- AST inventory GREEN
- repo-wide caller search GREEN
- analysis-only production drift=0

First manually reviewed candidate:
- `BoxCalculatorGUI._phase6_logical_part_present` at the accepted parent seam
- AST evidence: 0 `self` reads, 0 `self` writes; calls only `set`, `str`, `any`, `startswith`
- responsibility: PURE_PRESENTATION projection from authoritative physical IDs to legacy/logical top-level UI presence
- it does not create physical IDs, mutate workspace state, change active child, visibility mask, geometry, persistence, or DXF authority
- existing caller/regression uses it through `BoxCalculatorGUI._phase6_logical_part_present`, so compatibility surface must remain.

## Characterization gate
- added `tests/test_issue209_part_panel_projection.py` for box-body child aggregation, dynamic door/base-plate IDs, ordinary absent/present logical keys;
- prior inventory run2 RED was workflow-scope-only because the old analysis drift gate correctly saw the newly added test;
- registered workflow was switched to a characterization gate at `eea7344de7e2ef55be4c5ea8409e4723a118823c`;
- this checkpoint commit triggers the characterization gate.

## Hard boundaries
- logical `box_body` presence projection is presentation only; stable physical identity remains authoritative;
- nested active child and renderer visibility remain separate from logical presence;
- no Event Bus/Store/geometry/persistence authority in `part_panels.py`;
- characterization expected values are validation-only.

## Pending
1. focused characterization + linked fold-chain regression GREEN;
2. only then move this one pure projector to `gui_modules/part_panels.py` with compatibility binding in `gui.py`;
3. exact-head acceptance and cleanup before considering a second T5 slice.
