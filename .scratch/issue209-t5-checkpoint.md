# #209 / T5 Checkpoint

- Parent: #203
- Depends on: #208 CLOSED / completed
- Current role: T5 實作者
- Base: accepted T4 cleaned head `a098498d7459e974bbf18a5573e6b209eaeb4404`
- Branch: `refactor/issue209-part-panels-20260914`

## Current gate
No production move is authorized yet. First produce a selector/panel dependency inventory and classify candidate seams as:
- PURE_PRESENTATION
- WIDGET_CONSTRUCTION
- EVENT_FORWARDING
- AUTHORITATIVE_MUTATION

Only the first two categories may be first-slice extraction candidates, and widget construction is allowed only if state-changing actions return through explicit callbacks/commands to the root orchestrator.

## Hard boundaries
- logical top-level `box_body` navigation does not replace stable physical child identity;
- nested child navigation, active physical child, renderer visibility and manufacturing identity remain separate;
- no Event Bus or second Store;
- no geometry/DXF/persistence authority in `part_panels.py`;
- no callback contract invented merely to make extraction easier;
- hidden state dependency => HOLD.

## Pending
1. remote Phase6 preflight + AST/caller inventory;
2. manual semantic review of first candidate slice;
3. characterization before move;
4. only then create `gui_modules/part_panels.py`.
