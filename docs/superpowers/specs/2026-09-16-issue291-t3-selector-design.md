---
whd_doc_role: REFERENCE
whd_contract: issue291-t3-selector-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #291 T3 Part Selector / Navigation / Subtab Extraction — Design

## Identity and authority

- Parent: #287
- Task: #291 / T3
- Accepted predecessor: `#290 @ f11ab72850d893f5935ad869ab8ae9205fc0cd92`
- Work branch: `refactor/issue291-gui-phase2-t3-selector-20260916`
- Exact T3 reconciliation RUN: `35058231354` — SUCCESS
- T0 authority:
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_responsibility_inventory.md`
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_dependency_map.md`
  - `docs/superpowers/plans/2026-09-15-gui-phase2-t0/gui_state_owner_map.md`

## Gate reconciliation

The original issue gate `gui.py <= 7,000` is incompatible with the accepted #290 predecessor and the T0 responsibility map.

RUN `35058231354` checked the exact accepted predecessor and measured:

- `gui.py = 8,644 LOC`
- exact whole-method T3 selector/navigation responsibility = `150 LOC`
- selector construction block inside `setup_tab_z_ui` = `5 LOC`
- compatibility-preserving root delegate seam budget = `20 LOC`
- selector-builder seam budget = `1 LOC`
- net legal T3 reduction = `134 LOC`
- theoretical T3 root after complete legal extraction = `8,510 LOC`

The following large matches were explicitly excluded because they belong to later slices or mixed authority:

- `init_variables` — T4/T7 mixed state/Tk adapter
- `setup_tab_endcap_ui`, `setup_tab_door_ui`, indicator/base-plate tab builders — T4 part panels
- `_apply_cabinet_family_for_current_model` / most of `on_baseline_changed` — settings/state/geometry/project boundary, not selector presentation
- `open_part_hole_editor` and `_open_unified_hole_editor` — T5 editors
- `*_part_spec*`, baseline/manufacturing adapters — T7/manufacturing boundary

Therefore the reconciled T3 hard gate is:

```text
gui.py <= 8,520 lines
```

The ten-line margin above the exact 8,510 theoretical root is only for import/delegation wiring. The gate remains mandatory independent of test status.

Forbidden gate shortcuts:

- stealing #292/T4 panel/state responsibility;
- moving editor/dialog code assigned to #293/T5;
- moving manufacturing/geometry/DXF/project-schema authority;
- moving project/controller HOLD/REVIEW responsibility assigned to #295/T7;
- moving mixed cabinet-family business logic merely to reduce LOC;
- whitespace/comment compression as the primary LOC strategy.

## T3 responsibility boundary

T3 owns selector/navigation presentation and callback routing only. Authoritative state remains in `Phase6WorkspaceController` and existing services/controllers.

Exact root responsibilities approved for extraction:

- `_phase6_refresh_presence_ui`
- `_box_body_piece_label`
- `_box_body_piece_face_key`
- `_refresh_box_body_piece_tabs_2d`
- `_on_box_body_piece_2d_tab_changed`
- `on_box_body_piece_double_click`
- the physical box-body subtab widget construction block inside `setup_tab_z_ui`

`_phase6_set_part_presence` remains a host/controller seam in T3 because it combines state mutation, UI refresh and derived-geometry invalidation. It may call the extracted presentation helper, but T3 must not become the committed presence owner.

Cabinet-family selector presentation already lives in the accepted T2 layout package. T3 may characterize and preserve its routing, but must not move `_apply_cabinet_family_for_current_model` or baseline geometry loading into selector modules.

## Focused module direction

Allowed focused units include:

- `gui_modules/parts/selector.py`
  - presence/visibility presentation from already-resolved existing-parts state;
  - no second `existing_parts` store.
- `gui_modules/parts/subtabs.py`
  - physical box-body subtab construction, labels, selection synchronization and event routing;
  - no geometry derivation.
- `gui_modules/parts/navigation.py`
  - thin event/router helpers only when a separate navigation seam is needed;
  - no authoritative `active_part` backing field.

New modules must not import root `gui` or `compatibility.legacy_exports`.

## State ownership invariants

- `Phase6WorkspaceController.active_part` remains the authoritative active physical part.
- `Phase6WorkspaceController` remains authoritative for physical presence.
- `box_body:left_side`, `box_body:back`, `box_body:right_side` remain stable physical identities.
- A top-level UI label of `箱身` must not collapse authoritative physical child identity.
- selector/subtab modules may hold transient Tk widget maps/guards only; they may not mirror committed current-part or presence state.
- 2D and 3D must continue to resolve the same physical child through the authoritative workspace/render data.

## Callback rule

T3 callbacks are limited to:

```text
Event Unpacking -> Normalize -> Route / Dispatch
```

State mutation, geometry invalidation, rendering authority and project persistence remain delegated to existing owners.

## RED contract first

Before production extraction, add `tests/test_issue291_gui_phase2_t3_selector.py` proving the accepted predecessor is RED for the target structure:

- focused selector/subtab package modules do not yet exist;
- root selector/subtab methods are not yet thin delegates;
- the physical box-body subtab builder is still inline;
- final T3 gate is `gui.py <= 8520`;
- new parts modules must not import `gui` or compatibility exports;
- no new authoritative current-part/presence backing state is allowed.

The RED must fail for structure, not dependency/setup errors.

## Behavior evidence

Headless:

- selector/subtab architecture contract;
- stable physical-part identity characterization;
- WorkspaceController active-part/presence state regressions;
- receiving/vault selection routing characterization;
- protected-source drift.

Xvfb:

- receiving/vault family transition parity;
- top-level `箱身` remains one logical choice;
- receiving multipart physical subtabs remain `左側板 / 後面板 / 右側板`;
- switching physical subtab updates authoritative `active_part` without changing top-level `箱身` label;
- hidden/visible selector state parity;
- double-click/editor routing parity where currently observable.

Any red must be exact candidate/baseline A/B classified before exclusion.

## Protected invariants

T3 must not modify manufacturing/DXF/project semantics, including:

- `config.ini`
- `基準檔/**`
- `ae_engine/**`
- `phase6_project_file.py`
- `phase6_fold_profiles.py`
- manufacturing geometry/DXF authority
- project schema

## Acceptance

#291 is accepted only when:

- exact lineage is rooted at `#290 @ f11ab728...`;
- selector/subtab presentation lives in focused modules;
- root methods are thin delegates only;
- `gui.py <= 8520`;
- no new module >1,500 LOC;
- no duplicate current-part/presence authority;
- stable physical-part identity is unchanged;
- applicable L0-L4 evidence is GREEN or only exact A/B-proven inherited baseline reds remain;
- protected invariants are GREEN;
- temporary QA/extraction helpers are removed;
- accepted branch/HEAD is recorded and #291 is closed/completed before #292 begins.

Production `cleanup/2d-3d-sync` is not updated by T3; final production integration remains owned by #296/T8.
