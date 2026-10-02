---
whd_doc_role: REFERENCE
whd_contract: issue295-t7-controller-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #295 T7 — Project / visibility / remaining controller extraction design

## Identity
- Parent: #287
- Task: #295 / T7
- Accepted predecessor: #294 @ `936d50970b5d360f304f88c76215e3aa3ebe7de2`
- Work branch: `refactor/issue295-gui-phase2-t7-controller-20260918`
- Scope census: Actions `35310346416`
- Production integration remains #296/T8 responsibility.

## Hard gate is unchanged
The Phase 2 structural gate is fixed:

```text
gui.py <= 2,500 lines
```

The gate is not subject to reconciliation in T7.

Live census on the exact accepted #294 predecessor proved:
- `gui.py = 4,718 LOC`
- required removal = `2,218 LOC`
- current T0-labelled T7 surface = `2,310 LOC`
- pure T7 = `1,922 LOC`
- shared T7 = `388 LOC`
- MOVE rows = `158 LOC`
- REVIEW rows = `960 LOC`
- HOLD rows = `1,192 LOC`
- zero-wiring removal of every current T7-labelled node would leave `2,408 LOC`

Therefore the final gate is achievable only if T7 proves and extracts the HOLD adapter/controller boundaries instead of treating HOLD as permanent root implementation. HOLD means “do not move until authority is proven,” not “must remain in gui.py forever.”

## Target architecture

```text
gui.py
  ├─ bootstrap/root lifecycle
  ├─ dependency wiring
  ├─ thin class aliases / event routers
  └─ temporary compatibility surface only when explicitly inventoried

gui_modules/application/
  ├─ state_sync.py
  ├─ cabinet_controller.py
  ├─ fold_designer_adapter.py
  ├─ manufacturing_adapter.py
  └─ calculation_controller.py

gui_modules/project/
  ├─ export_actions.py
  └─ state_projection.py   # only if needed after characterization

gui_modules/visibility/
  └─ controller.py
```

Existing `Phase6ProjectController`, `Phase6WorkspaceController`, `SettingsService`, AE/manufacturing APIs and project-file schema remain authoritative.

## Authority rules

### Project
Project persistence ordering and committed/draft transaction authority remain in `Phase6ProjectController / ProjectSession`.

T7 project modules may:
- open/save dialogs;
- compose/apply GUI projections;
- route save/load/export commands.

They may not:
- redefine `PROJECT_SCHEMA`;
- become a second project path owner;
- write project bytes directly when the controller already owns that path.

### Workspace / visibility
`Phase6WorkspaceController` remains the single owner of:
- existing physical parts;
- active part;
- profiles;
- placements;
- part features / face features.

Visibility/controller code may project and route show/hide commands. It may not copy `existing_parts` into another committed store.

Show/hide must never mutate geometry or placement.

### Settings / cabinet runtime
`SettingsService` remains the committed settings owner. Tk variables are adapters only.

Cabinet runtime capture/restore may move into a focused application controller, but the moved code must continue reading/writing the existing owner fields and services; it may not invent a new committed cabinet state object.

### Manufacturing adapter
The T0 HOLD manufacturing methods may move only after focused characterization proves they are adapters around existing authoritative engine APIs.

The adapter may:
- build existing contract/spec objects from host/controller state;
- call existing manufacturing APIs;
- validate/route exports;
- project existing authoritative render data.

The adapter may not:
- own fold geometry;
- own DXF truth;
- introduce alternate part dimensions;
- own 3D placement;
- persist project state.

### Calculation
`update_calculations` may move as orchestration only. Engine/formula authority stays in AE/manufacturing/domain modules.

## Root-shrink strategy
Because all T7-labelled implementation leaves only ~92 LOC of theoretical zero-wiring margin, T7 must not retain one wrapper body per extracted method.

Preferred compatibility order:
1. direct class attribute alias to focused implementation;
2. one-line event router when event unpacking is required;
3. explicit compatibility shim only for proven external callers.

Accepted earlier-phase wrappers that now contain no owner logic may be collapsed to aliases after caller inventory. This is final-orchestrator cleanup, not behavior movement.

## Compatibility lifecycle
Do not create `compatibility/legacy_exports.py` unless a real external caller requires it.

Any retained shim must document:
- deprecated marker;
- current implementation target;
- current legacy caller inventory;
- planned removal Phase / Issue / Date.

No new `gui_modules/**` production module may import a compatibility layer.

## Dependency rules
Every new module must prove:
- no `import gui`;
- no `from gui import ...`;
- no compatibility-layer import;
- no circular import;
- ordinary module <= 1,500 lines;
- class <= 800 lines;
- method/callback <= 150 lines unless an explicit accepted exception exists.

## Slice ownership

### A — state-sync / variable initialization
Split `init_variables` rather than moving it whole. UI adapters may initialize on the host; committed authority remains SettingsService/WorkspaceController/existing host owner fields.

Move current shared T4/T7 setting serialization and synchronization only with focused parity.

### B — Fold Designer boundary
Extract:
- baseline/secondary-scene query orchestration;
- endcap policy routing;
- corner-policy adapter;
- authoritative render-data routing;
- part-spec-from-payload adapter;
- render-data query adapter;
- original Fold Designer snapshot projection.

### C — cabinet/application controller
Extract:
- known→custom inheritance;
- runtime capture/restore;
- family application;
- baseline change routing;
- numeric input collection;
- indicator result projection helpers.

### D — calculation controller
Extract central calculation orchestration without moving engine/formula authority.

### E — manufacturing adapter
Extract manufacturing context/spec/relief/indicator editor context builders with characterization proving exact contract parity.

### F — export/project state adapter
Extract:
- multi-door export routing;
- selected DXF export routing;
- single/multi indicator state snapshot/apply helpers.

Project file authority remains ProjectController.

### G — visibility/final root cleanup
Move physical presence routing to a focused visibility controller and collapse accepted extracted-owner wrappers to aliases where caller inventory proves no root semantics remain.

## Acceptance
T7 is accepted only when:
- `gui.py <= 2,500`;
- all non-root T0 responsibilities are extracted or have an explicit justified HOLD;
- no new state/geometry/project authority exists;
- full Headless/Xvfb candidate-only failures = 0;
- protected config/DXF/project-schema invariants pass;
- compatibility debt is fully inventoried;
- #295 finalization guard passes.

## No production integration
Do not update `cleanup/2d-3d-sync` in T7. #296/T8 owns final combined acceptance, cleanup/drift audit and non-force production integration.
