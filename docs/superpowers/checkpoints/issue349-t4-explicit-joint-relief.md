# Issue #349 T4 — Explicit USER_ADDED joint-relief extraction evidence

## Identity
- Master: #344
- Task: #349 / T4
- Predecessor: #348 accepted HEAD `f4a0cbc2ba7bd90bb10ecb2fab92f588f62164d9`
- Branch: `refactor/issue349-explicit-joint-relief-20260918`

## Scope
Move-only extraction of:
- `_phase6_resolve_explicit_joint_reliefs`

Canonical owner:
- `phase6_manufacturing_geometry.py`

Preserved behavior:
- relief/preserve ownership
- WRAP semantics
- topology-level validation
- piece-level UV behavior
- candidate discovery
- replay verification
- atomic multi-corner fixed-point replay
- illegal penetration fail-closed
- provisional state persistence
- diagnostic status/evidence
- `joint_relief_state` schema

## RED
RUN `35359248057`
- expected **1 FAIL**
- owner missing `_phase6_resolve_explicit_joint_reliefs`

## Minimal GREEN
RUN `35359347058`
- extraction contract: SUCCESS

## Solver regression acceptance
RUN `35359416832`
- focused ownership: SUCCESS
- explicit solver regressions: **38 PASS / 0 FAIL**

Coverage:
- USER_ADDED
- WRAP ownership/backprojection
- topology fail-closed
- provisional replay / invalidation
- multi-WRAP fixed-point replay
- collision verification

## Static invariants
- reverse import to bridge: **0**
- duplicate bridge implementation: **0**
- bridge LOC after T4: **9,644**

## Conclusion
T4 accepted. Explicit USER_ADDED joint-relief solver now has one canonical manufacturing owner and all focused behavior remains GREEN.
