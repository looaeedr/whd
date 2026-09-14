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

## First approved slice
`BoxCalculatorGUI._phase6_logical_part_present`
- AST: 0 `self` reads / 0 writes
- category: PURE_PRESENTATION
- function projects authoritative physical IDs into logical top-level UI presence only
- no geometry/state/persistence/visibility/active-child authority
- compatibility surface remains `BoxCalculatorGUI._phase6_logical_part_present` via static binding.

## Characterization
Run `34825759867`: SUCCESS.
- Phase6 preflight GREEN
- focused projection + linked fold-chain regression GREEN
- production-source drift=0

## Current branch state
- `gui_modules/part_panels.py` owns the projector implementation;
- `gui.py` contains only compatibility import + `staticmethod` binding for this seam;
- `.scratch/issue209/validate_t5_first_slice.py` compares accepted T4 parent AST against moved implementation and validates binding/import direction;
- prior apply run `34825889729` fail-closed because the old body was already absent; it did not commit or push any duplicate edit;
- registered T5 workflow is now acceptance-only and must not write production source.

## Exact-head acceptance scope
1. Phase6 preflight;
2. parent-vs-current AST move-only contract;
3. compatibility static binding + no `gui_modules -> gui` import;
4. Xvfb L1/L4 focused regression including linked fold chain, UI state and 3D single-source renderer;
5. config.ini + protected baseline invariants;
6. allowed T5 diff only;
7. tested HEAD recorded before cleanup.

## Hard boundaries
- physical identity remains authoritative;
- logical `box_body` grouping does not replace nested physical child navigation;
- visibility remains renderer-only;
- no Event Bus/Store/geometry/DXF/persistence authority in `part_panels.py`.

## Pending after GREEN
- remove temporary workflow/apply/validate/inventory scripts;
- cleaned-head drift audit;
- decide second T5 slice SAFE vs HOLD from inventory evidence;
- close #209 only if T5 acceptance contract is fully satisfied.
