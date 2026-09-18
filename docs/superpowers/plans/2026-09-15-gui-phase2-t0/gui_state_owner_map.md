---
whd_doc_role: REFERENCE
whd_contract: gui-phase2-t0-state-owner-map
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #288 T0 — gui.py State Owner Map

## Evidence identity
- Production baseline: `d72e81b5820b9cb54008a2dda9e96cdc673a9734`
- AST audit run: `34990930540` — SUCCESS
- `gui.py`: **9863 LOC**
- `Phase6ApplicationHost`: **9119 LOC / 237 methods**

## Authoritative committed owners

### SettingsService
`gui.py` explicitly identifies `SettingsService` as the single owner of committed runtime settings. `config.ini` supplies startup defaults / explicit persistence; Tk variables are UI adapters.

### Phase6WorkspaceController
Single committed workspace owner for physical `existing_parts`, `active_part`, box-body profile/structure, part profiles, assembly placements, part features, and part-face features. Legacy properties in `gui.py` delegate to this controller.

### Phase6ProjectController / ProjectSession
Owns committed/draft transaction lifecycle, project path, payload build/save/load ordering and persistence coordination. `_phase6_loaded_project_path` is a delegating compatibility alias, not a second path store.

## Host-owned state requiring explicit T4/T7 review
These direct `Phase6ApplicationHost` clusters must not be duplicated during extraction:

- assembly/corner: `assembly_joint_state`, `assembly_relief_state`, `endcap_fw_state`, `endcap_bottom_wrap_state`, `manual_corner_state`, `manual_corner_pair_same`, parameter lock/override state.
- door/multipart: `door_layout_columns`, `receiving_inner_doors`, `door_layout_scope`, `door_layout_handle_edges`, per-cell feature/indicator maps.
- surface/face features: `surface_features`, `box_body_face_features`, `box_body_face_bounds`.

Classification: `HOST_COMMITTED_STATE_REVIEW`. Either establish a focused owner/controller or keep the ownership in thin root orchestration; never copy it into panels/renderers.

## Non-authoritative UI adapter state
Tk variables, widget/entry collections, notebook/tab/canvas references, click timing, panel frames and enable/disable presentation state may move with their view responsibility **only when state-changing callbacks delegate immediately to the authoritative owner**.

## Derived cache state
`_Phase6DerivedCacheOwner` is explicitly a GUI-derived cache owner, not manufacturing authority. Cache movement must preserve source authority and invalidation; a cache may never become persisted truth.

## Transient editor state
`Phase6HoleEditorSession`/editor-local values may own temporary edit-session state only:
```text
committed owner → transient session → preview/edit
confirm → explicit commit
cancel  → discard, no committed mutation
```

## Rendering state
Rendering may own transform/viewport/hit-test/hover/selection presentation only. It may not own physical presence, project truth, DXF truth, or manufacturing dimensions.

## Compatibility aliases are not owners
- `fold_designer_box_body_profile` → WorkspaceController
- `fold_designer_part_bundle` → WorkspaceController
- `_phase6_existing_parts` → WorkspaceController
- `_fold_designer_last_part_key` → WorkspaceController
- `_phase6_loaded_project_path` → ProjectController

## Task ownership rules
- **T1:** may move scheduler/window lifecycle/command routing; committed domain owners stay put.
- **T2:** layout/widget references only; callbacks delegate.
- **T3:** `active_part`/`existing_parts` remain WorkspaceController-owned.
- **T4:** panel Tk adapters may move; committed values route to SettingsService/WorkspaceController/proven controller.
- **T5:** transient editor state only; confirm/cancel contract preserved.
- **T6:** presentation/derived render state only.
- **T7:** remaining host-owned committed clusters receive an explicit owner or remain documented root orchestration while satisfying final size gate.

## Forbidden shadow-state examples
```text
panel.current_part = authoritative_copy
selector.existing_parts = authoritative_copy
renderer.geometry = new_authoritative_geometry
editor.project_snapshot = permanent_truth
compatibility.legacy_state = shadow_store
```

**State-owner map gate: GREEN for T1.**
