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
- registered workflow `issue208-t4-preflight.yml` upgraded at `a315a89c6a6cc8ba7c0f42c1fb0ce6428037fc4b` into a dual-mode execution/acceptance gate;
- this checkpoint commit intentionally triggers the registered gate through a non-workflow path so the new workflow revision is actually executed.

## Pending
1. execution mode removes only the old toolbar function body from `gui.py` and adds compatibility import;
2. connector checkpoint triggers exact-head acceptance mode;
3. source-contract/import-direction checks;
4. Xvfb characterization + focused UI regression;
5. config/baseline invariants;
6. remove temporary workflows, drift audit, total-control review.
