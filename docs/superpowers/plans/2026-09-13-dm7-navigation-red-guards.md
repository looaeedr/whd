# DM7 T1 Navigation RED Guards — Implementation Plan

> Owning issue: #167  
> Parent: #166  
> Production target: `cleanup/2d-3d-sync`  
> Work branch: `test/dm7-t1-navigation-red-guards-20260913`

## Goal

Establish permanent RED-first contracts for operator part navigation without modifying production code. T1 only changes tests/process evidence. T2 owns the production deep-module implementation.

## Authority

- `Phase6DesignerWorkspace.available_parts` remains authoritative physical-part presence.
- Explicit aggregate `box_body` must remain aggregate.
- Explicit physical child identity is exact.
- Stale explicit child must fail closed; no remembered/sibling/first-child substitution.
- Remembered child is View/navigation convenience only.
- Menu / Structure Tree / Corner Data must project the same stable hierarchy.
- Display labels and row/tab indexes are presentation only.
- Navigation resolution/projection must not mutate manufacturing workspace state.

## Tasks

1. Re-read current #96/#97 regressions and current bridge resolver.
2. Replace the stale-child legacy oracle that currently expects first-child fallback with the DM7 fail-closed contract.
3. Add `tests/test_dm7_part_navigation.py` covering aggregate parent, exact child, stale child, stale memory/restore contract, hierarchy parity, label independence, and purity.
4. Run focused pytest remotely on this branch and require a real assertion RED caused by current navigation behavior, not import/setup/harness failure.
5. Record exact RED nodeids/result in checkpoint/journal and owning Issue #167.
6. QA-read the diff and leave production files untouched. Do not implement T2 in this ticket.

## Expected RED

Current `_phase6_resolve_operator_part_key()` substitutes a missing `box_body:<role>` with remembered child or `children[0]`. The new stale-child contract must therefore fail against the current production resolver.

## Stop boundary

T1 ends after permanent contracts + reproducible requirement RED evidence. No `phase6_part_navigation.py`, resolver fix, caller migration, geometry, DXF, Fold, Relief, placement, or persistence implementation belongs in T1.
