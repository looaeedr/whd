# Issue #360 T6 — pure manufacturing orchestration cutover

## Identity
- Master: #353
- Task: #360 / T6
- Predecessor: #359 accepted HEAD `43037abf1730356d69c6f1b413984dba16461e23`
- Fixed Phase 2 semantic baseline / production: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Final expanded parity RUN: `35415470368` / job `105823159339`
- Tested SHA: `e34b9f966dcee560fba93ecdf3d5f13d3f8efbc4`

## Pure service
New canonical orchestration owner:
- `phase6_manufacturing_service.py`
- public entry: `resolve(request)`
- service length at acceptance: **536 lines**

Static purity readback:
- app/self references: **0**
- Tk/tkinter references: **0**
- `fold_designer_bridge` references/imports: **0**
- `designer_workspace` references: **0**
- Phase 1 bridge callback registry references: **0**

The geometry helper owner no longer owns the orchestration entry; orchestration logic moved into the pure service while shared geometry/joint helpers remain in `phase6_manufacturing_geometry.py`.

## Input boundary
Before service entry, the adapter materializes domain inputs:
- immutable request DTO
- canonical part inventory
- profiles/dimensions
- render data / committed render data
- PartSpec + ManufacturingContext where available
- cache key fingerprint

The service receives no app instance, Tk variable, workspace object, or bridge callback.

## Output boundary
The service returns `ManufacturingResolveResult` containing:
- geometry
- diagnostics
- mutation patch
- explicit effects
- cache receipt

Application publication/state application remains outside the service.

## Focused GREEN
RUN `35415433257`:
- **27 PASS / 0 FAIL**
- cache performance gate: PASS
- phase1 hit: **51,867 ns**
- phase2 hit: **62,595 ns**
- ratio: **1.2125x**
- absolute delta: **10,972 ns**

## Expanded parity GREEN
RUN `35415470368` / job `105823159339`:
- **82 PASS / 3 SKIP / 0 FAIL**
- cache performance gate: PASS

Expanded suite covers:
- GUI manufacturing adapter
- previous manufacturing adapter slice
- manufacturing helper extraction
- explicit joint relief extraction
- orchestration / compatibility gates
- Phase 2 T1–T6 contracts
- manufacturing API / finished-face / collision dependency / policy boundary
- resolved manufacturing bridge / export / geometry

## Runtime compatibility fixes during T6
Two non-semantic migration issues were corrected before acceptance:
1. adapter local-name collision between explicit cache service and `phase6_manufacturing_service` module;
2. T5 cache benchmark miss fixture was updated to supply the explicit render-data input now required before pure service entry.

No solver formula, relief policy, collision policy, persistence schema, or manufacturing topology semantics changed.

## Timing semantics
#354 T0 already proved direct/transitive Tk event-loop pump count = 0 on the solve path, so moving application publication outside the pure service does not cross a hidden Tk reentrancy point.

## Scope
No config, DXF, or protected manufacturing reference files changed.
Production remains untouched.

Next: #361 / T7 bridge one-line manufacturing compatibility facade.
