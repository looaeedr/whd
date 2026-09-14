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

## Pending
1. changed-file Phase6 preflight GREEN;
2. create T4 plan;
3. move exact function body to `gui_modules/layout.py`;
4. compatibility import/re-export from `gui.py`;
5. source-contract/import-direction checks;
6. Xvfb characterization + focused UI regression;
7. config/baseline invariants;
8. remove temporary workflow, drift audit, total-control review.
