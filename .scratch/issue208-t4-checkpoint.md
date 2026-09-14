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
- minimal parser probe run `34824959521`: GREEN;
- script-based apply run `34825034790`: GREEN;
- Move-Only implementation commit pushed by the gate: `5d8123f2d37af9b1c7f920684705cb861e5f3b8b`;
- `gui_modules/layout.py` owns the exact characterized function body;
- `gui.py` now retains only the compatibility import for `_project_toolbar_presentation`;
- validation logic is isolated in temporary `.scratch/issue208/validate_t4_move.py`;
- registered workflow switched to acceptance-only at `84f34a867d2808f289bf66d4acc597ec67cf3523`;
- this checkpoint commit triggers exact-head acceptance.

## Acceptance scope
1. Phase6 changed-file preflight;
2. exact parent-body == moved-body source contract;
3. old body absent from `gui.py`, compatibility import count == 1;
4. no `gui_modules -> gui` import;
5. allowed T4 production diff only `gui.py` + `gui_modules/layout.py`;
6. Xvfb characterization + focused UI/3D renderer regression;
7. `config.ini` + protected `基準檔/**` invariants;
8. tested HEAD recorded before cleanup.

## Pending after GREEN
- remove temporary workflows/scripts and stale QA runner branch residue;
- cleaned-head drift audit;
- total-control review and #208 closure;
- #209 fresh branch from accepted T4 cleaned head.
