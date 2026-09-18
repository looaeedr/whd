---
whd_doc_role: REFERENCE
whd_contract: gui-phase2-t0-dependency-map
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #288 T0 — gui.py Dependency Map

## Evidence identity
- Production baseline: `d72e81b5820b9cb54008a2dda9e96cdc673a9734`
- AST audit run: `34990930540` — SUCCESS
- `gui.py`: **9863 LOC**

## Current dependency shape
```text
main → Phase6PrimaryApplication → Phase6ApplicationHost
  ├─ SettingsService
  ├─ Phase6ProjectController → ProjectSession → phase6_project_file
  ├─ Phase6WorkspaceController → SharedWorkspaceState
  ├─ Phase6FoldDesignerApp
  ├─ Phase6HoleEditorSession / CanvasView
  ├─ ae_engine.* manufacturing / geometry / drawing APIs
  └─ gui_modules/{drawing,layout,part_panels,render_2d,project_actions}
```

Existing extracted modules establish the correct one-way pattern: `gui.py/orchestrator → focused gui_modules → authoritative controller/engine types`. `drawing.py`, `layout.py`, `part_panels.py`, `render_2d.py`, and `project_actions.py` do not import `gui.py`.

## Non-negotiable direction
```text
gui_modules/* → gui.py                         FORBIDDEN
gui_modules/new_module → compatibility/*       FORBIDDEN
```
Cross-module mutation routes through an explicit command/controller/application orchestrator.

## Authority boundaries

### Settings
`Tk variable/panel → normalize → SettingsService → committed snapshot → consumers`.

### Workspace / physical identity
`selector/panel → command → Phase6WorkspaceController → SharedWorkspaceState`.

### Project / persistence
`file action/dialog → Phase6ProjectController → ProjectSession → phase6_project_file`.

### Manufacturing geometry
`controller input → ae_engine/phase6 authoritative calculation → resolved result/projection → rendering`.

Rendering must never rederive manufacturing geometry or consume test/golden expected data as a production source.

## High-risk hotspots
- `init_variables` (230 LOC): mixed UI adapters + host-owned state; split before movement.
- `create_widgets` (311 LOC): mixed root layout + callbacks; T2/T4 split.
- `_open_unified_hole_editor` (1,333 LOC / 57 nested defs): T5 view/controller/session decomposition.
- L7443–L7976 manufacturing/spec cluster: HOLD/REVIEW; never move to rendering/panel modules.
- L1463–L2599 snapshot/workspace/project bridge: explicit controller/lifecycle contract required.

## Target graph
```text
gui.py
  ├─ application/*
  ├─ layout/* ──→ callbacks/commands only
  ├─ parts/* ───→ WorkspaceController / SettingsService
  ├─ editors/* ─→ transient session → explicit commit
  ├─ rendering/* ← resolved/projection data only
  ├─ project/* ─→ ProjectController
  └─ visibility/* → authoritative owner
```

## Compatibility rule
Only `external legacy caller/test → compatibility/legacy_exports.py → current implementation` is allowed. Every retained shim requires a deprecated marker, caller inventory, and removal Phase/Issue/Date.

## Per-task gates
- **T1:** lifecycle/scheduler/command routing; no domain owner movement.
- **T2:** presentation only; layout cannot calculate manufacturing geometry.
- **T3:** selector queries/commands WorkspaceController; no duplicate active-part/existing-parts state.
- **T4:** panels route commands; no second committed settings/domain store.
- **T5:** transient editor state only; cancel leaves committed state unchanged.
- **T6:** resolved data → rendering only.
- **T7:** project/visibility/focused controllers; compatibility cannot become internal dependency.

## Static circular-import gate
Every new module must prove:
```text
no import gui
no from gui import ...
no gui_modules/** import compatibility/legacy_exports.py
```

**Dependency-map gate: GREEN for T1 planning.**
