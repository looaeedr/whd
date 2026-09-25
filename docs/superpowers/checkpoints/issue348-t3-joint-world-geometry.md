# Issue #348 T3 — Joint-world geometry extraction evidence

## Identity
- Master: #344
- Task: #348 / T3
- Predecessor: #347 accepted HEAD `d183a4f274ee987f78173b67e371cd7511f1727b`
- Branch: `refactor/issue348-joint-world-geometry-20260918`

## Scope
Move-only extraction of:
- `_phase6_build_joint_world_geometry`

Canonical owner:
- `phase6_manufacturing_geometry.py`

Bridge:
- imports/re-exports the exact same function object
- no duplicate top-level definition remains

## RED
RUN `35358849424`
- **1 FAIL**
- expected ownership assertion: new owner did not yet define `_phase6_build_joint_world_geometry`

## GREEN
RUN `35358958282`
- extraction contract: SUCCESS

## Focused geometry acceptance
RUN `35359041711`
- focused extraction contract: SUCCESS
- world-geometry / collision regressions: **58 PASS / 2 SKIP / 0 FAIL**

Coverage includes:
- canonical joint world geometry
- flat UV mapped skins
- BoxBody aggregate/piece geometry
- WRAP backprojection
- candidate replay
- multi-wrap
- assembly collision
- assembly 3D placement/mating datum

## Static invariants
- reverse import `phase6_manufacturing_geometry -> fold_designer_bridge`: **0**
- duplicate bridge implementation: **0**
- bridge integrity readback: valid
- bridge LOC after T3: **10,137**

## Conclusion
T3 accepted. Joint-world geometry now has one canonical manufacturing owner with focused world/UV/collision parity GREEN.
