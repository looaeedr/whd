# #208 / T4 Checkpoint

- Parent: #203
- Depends on: #207 CLOSED / completed
- Current role: T4 實作者
- Base: accepted T3 head `2c3185ca863adf0cd9861ad5e04f594185c95ced`
- Branch: `refactor/issue208-layout-presentation-20260914`
- Active execution PR: #221

## Approved first slice
Move-only extraction of `_project_toolbar_presentation` into `gui_modules/layout.py`.

## Progress
- changed-file Phase6 preflight run `34824145664`: GREEN;
- `gui_modules/layout.py` contains the exact characterized toolbar presentation body;
- later workflow revisions produced Actions check-suite failures with zero check-runs, proving the blocker is workflow-definition parsing/registration rather than production code;
- registered workflow is now minimized at `79985aa490e5f08dce0074c76f129a67e14f654b` to a one-step parser probe;
- this commit intentionally triggers that minimal workflow through its only path filter.

## Pending
1. parser probe GREEN;
2. restore a minimal apply-only gate without the construct that caused zero-job failure;
3. apply exact `gui.py` move-only edit;
4. exact-head acceptance: source contract, import direction, Xvfb regression, invariants;
5. cleanup temporary workflows/QA branch and drift audit.
