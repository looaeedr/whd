---
whd_doc_role: REFERENCE
whd_contract: issue290-t2-layout-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #290 T2 Main Layout / Toolbar / Workspace Extraction — Design

## Identity and authority

- Parent: #287
- Task: #290 / T2
- Accepted predecessor: `#289 @ 7504e628f7648bb18925151b5e44912c53a913c4`
- Work branch: `refactor/issue290-gui-phase2-t2-layout-20260916`
- T0 authority:
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_responsibility_inventory.md`
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_dependency_map.md`
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_state_owner_map.md`
- UI authority: `.agents/skills/engineering/UI設計與去AI味/SKILL.md`
- Exact reconciliation evidence: GitHub Actions RUN `35055412366` — SUCCESS

## Problem

The original #290 structural gate (`gui.py <= 8,000`) conflicts with the accepted T0 responsibility map and the accepted #289 predecessor.

RUN `35055412366` checked out exact predecessor `7504e628...` and measured:

- `gui.py`: 8,973 LOC
- `setup_styles`: 26 LOC
- `create_widgets`: 311 LOC
- unambiguous T2 method responsibility: 337 LOC
- theoretical root LOC after removing those two complete method bodies: 8,636 LOC
- `init_variables`: 230 LOC but classified T2/T4/T7 mixed and explicitly excluded from T2 structural accounting
- `_apply_ui_text_size_preference`, `on_ui_text_size_changed`, `_current_box_assembly_type`: T2/T4 mixed and excluded from the structural target unless a separate dependency contract proves a presentation-only slice

Therefore `<= 8,000` cannot be reached without stealing T3/T4/T7 scope, moving committed state, or performing meaningless line compression. None is acceptable.

## Reconciled structural gate

The T2 hard gate is:

```text
gui.py <= 8,650 lines
```

This is derived from the exact 8,636-line theoretical root after removing the two unambiguous T2 method bodies, with a maximum 14-line allowance for thin root delegation/import seams.

The gate remains mandatory independent of test status.

The following are forbidden ways to satisfy the gate:

- moving all or part of `init_variables` merely to reduce LOC;
- moving selector/navigation responsibilities assigned to #291/T3;
- moving part-panel/state-changing responsibilities assigned to #292/T4;
- deleting comments/whitespace or compacting statements as the primary LOC strategy;
- moving manufacturing, geometry, DXF, project-schema or committed state authority;
- reopening or rewriting accepted #289 lifecycle responsibility merely to hit the number.

If the T2 design cannot reach `<= 8,650` without one of these violations, #290 is RED and must stop for authority reconciliation.

## Design direction

This is a structural extraction, not a UI redesign. Existing appearance, labels, action hierarchy, control ordering, callbacks, scroll behavior and workspace workflow remain behaviorally equivalent.

WHD remains a dense Tkinter/ttk engineering workbench. `UI設計與去AI味` is an authority for preserving deliberate presentation hierarchy and layout contracts; it is not permission to restyle unrelated regions.

## Module boundary

The current flat `gui_modules/layout.py` becomes a focused `gui_modules/layout/` package while preserving the existing import contract for `_project_toolbar_presentation` through `gui_modules/layout/__init__.py`.

Planned units:

- `gui_modules/layout/__init__.py`
  - compatibility export surface for existing `from gui_modules.layout import ...` callers;
  - no state ownership.
- `gui_modules/layout/styles.py`
  - T2-owned ttk/theme presentation setup moved from `setup_styles`;
  - accepts the host/theme inputs required to configure presentation;
  - no domain state.
- `gui_modules/layout/toolbar.py`
  - constructs project toolbar, project identity block and text-size control;
  - binds callbacks to existing host methods only;
  - does not own project or settings state.
- `gui_modules/layout/main_window.py`
  - root/paned-window composition and orchestration of region builders;
  - no domain calculations or duplicate state.
- `gui_modules/layout/scrolling.py`
  - constructs the left scroll canvas/frame and owns only scroll/resize presentation callbacks;
  - returns widget references needed by the composing layout.
- `gui_modules/layout/left_panel.py`
  - static left-side presentation wiring currently inside `create_widgets`;
  - may construct rows/buttons/checkbuttons and call existing host helpers;
  - may reference existing Tk variables but may not become their authoritative owner;
  - state-changing callbacks remain host/controller delegates.
- `gui_modules/layout/workspace.py`
  - constructs the right-side Fold Designer notice/workspace region and compatibility-only hidden widget host wiring;
  - no 2D geometry, part identity or project state authority.

No layout module may exceed 1,500 lines without explicit re-approval.

## Root seam after cutover

`gui.py` remains the application orchestrator. After extraction:

- `setup_styles` is a thin delegate to `gui_modules.layout.styles`;
- `create_widgets` is a thin delegate to `gui_modules.layout.main_window`;
- moved widget construction has exactly one production location;
- compatibility aliases are import/delegation seams only, not duplicate implementations.

`gui_modules/** -> gui.py` remains forbidden. New modules may not import `compatibility/legacy_exports.py`.

## State and callback contract

No committed owner changes in T2.

Authoritative owners remain:

- `SettingsService` for committed runtime settings;
- `Phase6WorkspaceController` for physical presence/active-part/workspace truth;
- `Phase6ProjectController / ProjectSession` for project transaction and persistence;
- existing host-owned T4/T7 committed clusters remain where they are until their assigned task.

Tk variables and widget references are presentation adapters only.

Callback rule:

```text
widget event -> existing host/router callback -> authoritative service/controller
```

T2 must not introduce:

```text
layout.current_part
layout.existing_parts
layout.project_snapshot
layout.settings_snapshot
layout.geometry
```

or any equivalent shadow store.

## `create_widgets` split rule

T0 explicitly forbids moving the 311-line `create_widgets` method wholesale as one giant replacement module. The cutover is region-based:

1. project toolbar + identity + text size;
2. main paned/root containers;
3. scrollable left-container shell;
4. left static presentation wiring;
5. right workspace notice;
6. compatibility-only hidden widget host wiring.

Each region must have its own functional contract and focused test evidence. `main_window.py` composes these region builders; it does not recreate the original monolith under a new filename.

## Existing UI behavior that must remain observable

- project buttons exist with the same labels and callbacks:
  - 開啟專案 -> `open_phase6_project`
  - 儲存專案 -> `save_phase6_project`
  - 另存新檔 -> `save_phase6_project_as`
- project identity title/subtitle remain unchanged;
- text-size combobox remains readonly, width 4, uses `UI_TEXT_SIZE_LABELS`, and binds `<<ComboboxSelected>>` to `on_ui_text_size_changed`;
- main horizontal paned layout remains present;
- left control region remains vertically scrollable;
- frame resize updates the scroll region/window width;
- mouse wheel continues to scroll the left region;
- baseline selector, Fold Designer entry, result rows, DXF options and export controls keep their existing host callbacks/state sources;
- right workspace message remains a Fold Designer/截角資料 entry rather than reviving a standalone 2D authority;
- compatibility-only hidden legacy 2D hosts remain non-navigation surfaces and non-authoritative.

## Testing strategy

### RED contract first

Create `tests/test_issue290_gui_phase2_t2_layout.py` before production extraction. Initial RED must prove that the accepted predecessor does not yet satisfy the target module ownership/delegation contract.

Behavior/static assertions must cover:

- `gui_modules.layout` is a package with focused modules;
- no focused layout module imports `gui` or `compatibility.legacy_exports`;
- root `setup_styles` and `create_widgets` are thin delegates after cutover;
- moved widget construction does not remain duplicated in root;
- `gui.py <= 8,650`;
- no layout module >1,500 LOC;
- legacy `_project_toolbar_presentation` import surface remains valid.

### Headless focused

Run the new T2 contract plus existing relevant import/layout/project-action/state tests. Headless GREEN cannot substitute for Xvfb.

### Xvfb layout parity

Exercise real Tk widgets for:

- toolbar/button availability and callback identity;
- pane construction and left/right region presence;
- scrollbar ownership and scroll reachability;
- resize callback behavior;
- text size `1.0 / 1.2 / 1.4` with no required-control clipping or loss of scroll reachability;
- short-window behavior where existing contracts cover it.

Any baseline failures must be classified by exact candidate/baseline A/B before being excluded. Candidate-only RED blocks acceptance.

### Protected invariants

No T2 diff may modify:

- `config.ini`;
- `基準檔/**`;
- `ae_engine/**`;
- `fold_designer_bridge.py`;
- `phase6_fold_profiles.py`;
- `phase6_project_file.py`;
- manufacturing/DXF authority;
- project schema.

Temporary QA workflows and extraction helpers must be removed before the accepted predecessor for #291 is declared.

## Acceptance

#290 is accepted only when all are true:

- exact predecessor lineage remains rooted at `7504e628...`;
- layout ownership is split by region into focused modules;
- root only wires/delegates moved layout responsibilities;
- `gui.py <= 8,650`;
- no layout module >1,500 LOC;
- no new authoritative state owner or shadow store;
- Headless focused GREEN;
- Xvfb presentation/layout parity GREEN or only exact A/B-proven inherited baseline reds remain;
- protected artifact invariants GREEN;
- temporary QA/extraction artifacts removed;
- tested -> closing drift contains cleanup/evidence-only changes;
- final accepted branch/HEAD is recorded on #290;
- #290 is `closed/completed` before #291/T3 begins.

Production `cleanup/2d-3d-sync` is not updated by T2; final production integration remains owned by #296/T8.
