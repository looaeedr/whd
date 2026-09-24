# Issue #530 / B5 — Derived Projection / Request Assembly Reconsideration

- Master: #520
- Parent accepted HEAD: `8fa30cfc7800afba16b71c7580552893db5d1037`
- Production GREEN HEAD: `9fe131b9574d6fdfb918eca56eaaa7988da75104`
- Final decision: **`DEEPEN_DERIVED_PROJECTION_OWNER`**

## Evidence chain

1. Deletion-Test candidate RUN `35794244876` — SUCCESS
   - two earlier failures (`35794007741`, `35794138484`) were **REVOKED harness indentation errors**, not architecture RED.
   - E variant removed Bridge-local request assembly and reduced the sync body by 52 lines.
2. Replacement requirement RED RUN `35794404726` — SUCCESS as an expected RED harness:
   - **2 failed / 4 passed**
   - failed exactly because the new request-assembly owner was not yet in production and Bridge still owned request assembly.
3. Production GREEN RUN `35794936955` — SUCCESS:
   - Headless: **52 passed**
   - Xvfb: **2 passed / 33 deselected**
   - Bridge LOC: **7482**
   - B5 Bridge reduction: **58 lines**
   - `_phase6_sync_authoritative_derived_parts` span: **193**
   - reverse import bridge: **0**

## CURRENT ownership after B5

- Request assembly input: `phase6_derived_part_projection.py::DerivedPartRequestAssemblyInput`
- Request assembly owner: `phase6_derived_part_projection.py::build_derived_part_projection_request`
- Immutable sync plan: `phase6_derived_part_projection.py::build_derived_part_sync_plan`
- Workspace mutation: `Phase6WorkspaceNavigationController.apply_derived_sync_plan`
- Domain derivation: unchanged; remains in the existing canonical domain/application derivation owners.

Bridge now derives the domain projections, passes already-derived data into the pure request-assembly owner, then passes the immutable plan to navigation. Bridge no longer owns the local remove/add/stash/active/selected repair policy.

Stage B continues with #531/B6.
