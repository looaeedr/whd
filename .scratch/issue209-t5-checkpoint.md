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
- `tests/test_issue209_part_panel_projection.py` + `tests/test_phase6_linked_fold_chain_and_parts.py` GREEN
- production-source drift=0

## Move-only preparation
- `gui_modules/part_panels.py` now contains the exact projector body;
- temporary `.scratch/issue209/apply_t5_first_slice.py` performs only: import compatibility helper + replace old class staticmethod body with a `staticmethod` binding;
- registered T5 workflow switched to apply-first-slice at `face35457b8becefbef1334e5956ee71f47220f3`;
- this checkpoint commit triggers that apply gate.

## Hard boundaries
- physical identity remains authoritative;
- logical `box_body` grouping does not replace nested physical child navigation;
- visibility remains renderer-only;
- no Event Bus/Store/geometry/DXF/persistence authority in `part_panels.py`.

## Pending
1. exact first-slice apply commit;
2. exact-head source/compatibility/import-direction + linked UI/state acceptance;
3. cleanup temporary workflow/script;
4. decide whether a second T5 slice is actually SAFE or HOLD based on inventory evidence.
