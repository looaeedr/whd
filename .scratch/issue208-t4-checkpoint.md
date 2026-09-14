# #208 / T4 Checkpoint

- Parent: #203
- Depends on: #207 CLOSED / completed
- Current role: T4 實作者
- Base: accepted T3 head `2c3185ca863adf0cd9861ad5e04f594185c95ced`
- Branch: `refactor/issue208-layout-presentation-20260914`

## Approved first slice
Move-only extraction of `_project_toolbar_presentation` into `gui_modules/layout.py`.

## Why only this slice
- T1 classified it SAFE.
- #206 characterization already locks its full current observable contract.
- It has no `self`/widget/state/geometry ownership.
- Other layout/frame/selector/scrollbar/panel builders may have runtime/widget coupling and remain HOLD until independently characterized.

## Progress
- changed-file Phase6 preflight run `34824145664`: GREEN;
- `gui_modules/layout.py` created with the exact characterized toolbar presentation body;
- complex dual-mode workflow was rejected/not scheduled by Actions, so the registered gate was simplified to a minimal apply-only workflow at `33419ea37a4abb5436beba795419f8404db85aa0`;
- this checkpoint commit triggers that registered apply gate through a normal matched path.

## Pending
1. apply gate removes only the old toolbar function body from `gui.py` and adds compatibility import;
2. replace registered gate with acceptance-only workflow;
3. connector checkpoint triggers exact-head acceptance;
4. source-contract/import-direction checks;
5. Xvfb characterization + focused UI regression;
6. config/baseline invariants;
7. remove temporary workflows, drift audit, total-control review.
