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
- minimal parser probe run `34824959521`: GREEN, proving the registered workflow path is valid when YAML is simple;
- exact edit logic moved out of YAML into temporary `.scratch/issue208/apply_t4_move.py`;
- registered gate at `62f91f4e155cbae477e36a3afa55b3cc8d601352` is now a simple checkout/preflight/script/commit workflow;
- this checkpoint commit triggers the script-based apply gate.

## Pending
1. apply gate commits only `gui.py` move-only change;
2. replace gate with acceptance-only workflow;
3. trigger exact-head acceptance;
4. source-contract/import-direction checks;
5. Xvfb characterization + focused UI regression;
6. config/baseline invariants;
7. remove temporary workflows/scripts/QA branch and drift audit.
