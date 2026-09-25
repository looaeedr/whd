---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# TEST Cleanup T4 — GUI Characterization Retirement Plan

Issue: #279
Parent: #274
Dependency: #276 / T1
Parallel siblings: T2 / T3 / T4
Authoritative parent: `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`

## Scope lock

This task is test-governance cleanup only. Production/runtime geometry, DXF authority, rendering ownership, UI runtime behavior, persistence, and manufacturing semantics must not change.

T4 does not perform the repository-wide rename/move planned for T5. Issue-number filenames may remain for the durable #210/#211 contracts until T5. The migration-era #206 filename may be retired only after every durable behavior it currently protects has a permanent successor.

## Authoritative parent facts

At the exact T1 parent, `gui.py` imports these extracted presentation helpers:

- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `render_drawing_scene`

from `gui_modules/drawing.py`, and imports `_project_toolbar_presentation` from `gui_modules/layout.py`.

Therefore T4 must preserve the behavior of those extracted helpers while removing migration-era whole-snapshot coupling. The #211 `gui_modules/render_2d.py` contracts are related architecture coverage but are not a replacement for `gui_modules.drawing.render_drawing_scene`.

## Classification

### `tests/test_issue206_gui_modularization_characterization.py`

1. `test_corner_preview_canvas_point_characterizes_current_projection`
   - Classification: permanent UI/drawing projection behavior.
   - Current behavior: preview point projection preserves X scaling and applies either top-style Y reflection across `span` or bottom-style original Y projection according to `flip_y`.
   - Authority: `gui_modules.drawing._corner_preview_canvas_point`.
   - Action: promote to `tests/test_gui_drawing_contract.py` under a semantic name.

2. `test_corner_preview_flip_y_characterizes_target_matrix`
   - Classification: permanent target-orientation behavior.
   - Current behavior: `bottom`, `bottom_left`, and `bottom_right` are unflipped; top-family, blank, and `None` use top-style flip; input is normalized with `strip()`.
   - Authority: `gui_modules.drawing._corner_preview_flip_y_for_target`.
   - Action: promote to the same permanent drawing contract.

3. `test_project_toolbar_presentation_characterizes_current_contract`
   - Classification: mixed durable operator-facing toolbar semantics + migration-era exact styling snapshot.
   - Durable contract:
     - project actions remain `open / 開啟專案`, `save / 儲存專案`, `save_as / 另存新檔` with their current semantic roles;
     - `save` remains the primary action unless product requirements separately change it;
     - workbench title/subtitle remain operator-visible product copy unless separately changed by UI requirements.
   - Migration/styling detail not promoted as a hard permanent contract: exact `toolbar_padx`, `toolbar_pady`, `button_padx`, `button_pady` values and whole-dictionary equality.
   - Authority: `gui_modules.layout._project_toolbar_presentation`.
   - Action: replace with `tests/test_gui_toolbar_contract.py` semantic assertions.

4. `test_render_drawing_scene_characterizes_canvas_projection_and_layer_styles`
   - Classification: mixed permanent drawing behavior + migration-era monolithic exact call-list snapshot.
   - Durable contract:
     - rendering must not mutate the source `DrawingScene`;
     - `skip_layers` must suppress requested layers;
     - polyline / line / circle primitives project through the supplied transform;
     - CUTTING / MARKING / BEND layer semantics and bend dash behavior remain represented.
   - Migration detail not promoted: one whole ordered `canvas.calls == [...]` snapshot tying all primitives, coordinates, colors, widths, and ordering into a single brittle assertion.
   - Authority: `gui_modules.drawing.render_drawing_scene`.
   - Action: promote the durable behavior into focused semantic tests in `tests/test_gui_drawing_contract.py`.
   - Important: #211 is supporting renderer-boundary coverage, not the replacement for this helper.

### `tests/test_issue210_project_actions_move_contract.py`

- Classification: permanent architecture/dependency contract.
- Preserve: project action ownership in `gui_modules/project_actions.py`, host delegation, no reverse dependency.
- T4 action: retain unchanged. Repository-wide naming/move is T5.

### `tests/test_issue211_renderer_dependency_gate.py`

- Classification: permanent rendering behavior + architecture/dependency contract.
- Preserve:
  - current grid behavior;
  - resolved feature projection behavior;
  - baseline-secondary behavior;
  - 2D renderer ownership in `gui_modules/render_2d.py`;
  - no reverse `gui` dependency;
  - `Phase6FinalSceneView` remains the sole approved new 3D owner; no new `gui_modules/render_3d.py`.
- T4 action: retain unchanged. Repository-wide naming/move is T5.

## TDD / evidence sequence

### Step 1 — Parent classifier

On an isolated QA branch rooted at the task plan head:

- prove the task plan commit has the exact T1 parent;
- inspect the exact T1 #206 file and prove it contains whole toolbar-dictionary and whole `canvas.calls` snapshot coupling;
- prove permanent successor files `tests/test_gui_drawing_contract.py` and `tests/test_gui_toolbar_contract.py` do not yet exist on the parent;
- run current #206/#210/#211 focused tests to establish the parent behavior baseline;
- classify this as `MIGRATION_CHARACTERIZATION_PRESENT`, not as a production defect.

### Step 2 — Permanent successor tests

Create `tests/test_gui_drawing_contract.py`:

- preserve the two current corner-preview projection cases;
- preserve the current target flip matrix including blank / `None` / whitespace normalization;
- split `render_drawing_scene` coverage into semantic assertions for non-mutation, layer skipping, primitive projection, and meaningful layer styling rather than one whole call-list snapshot;
- test the extracted helper directly; do not reintroduce `gui.py` as the behavior authority.

Create `tests/test_gui_toolbar_contract.py`:

- assert the current operator-facing project action identities, Chinese labels, and semantic roles;
- assert `save` is the primary action;
- assert the current workbench title and subtitle;
- explicitly avoid locking exact toolbar/button padding values or whole-dictionary equality.

### Step 3 — Retire migration-only #206 file

Delete `tests/test_issue206_gui_modularization_characterization.py` only after both permanent successor files exist.

Retirement evidence:

| Retired node | Permanent replacement |
| --- | --- |
| corner canvas projection characterization | `tests/test_gui_drawing_contract.py` |
| corner target flip matrix characterization | `tests/test_gui_drawing_contract.py` |
| toolbar whole-dictionary characterization | `tests/test_gui_toolbar_contract.py` semantic contract |
| drawing whole `canvas.calls` characterization | `tests/test_gui_drawing_contract.py` semantic rendering contract |

#210/#211 remain as separate permanent architecture/render-boundary evidence and are re-run in acceptance.

### Step 4 — Focused candidate validation

Run on the exact candidate SHA:

- `tests/test_gui_drawing_contract.py`
- `tests/test_gui_toolbar_contract.py`
- `tests/test_issue210_project_actions_move_contract.py`
- `tests/test_issue211_renderer_dependency_gate.py`

Requirements:

- 0 failures;
- no new skip/xfail masking;
- #210/#211 architecture gates remain green;
- no production/runtime file changes.

### Step 5 — Outcome-control and protected invariants

Verify:

- `PRODUCTION_SOURCE_DRIFT=0`;
- no geometry/DXF authority changes;
- config and protected DXF/schema manifest unchanged;
- no assertion weakening by skip/xfail or broad deselection;
- T1 parent -> candidate diff is TEST + plan/acceptance evidence only.

### Step 6 — Closing

- add permanent T4 acceptance/retirement record with exact run identity and counts;
- remove temporary QA workflow from the QA-only branch / ensure it is absent from task closing head;
- re-run closing drift audit;
- close #279 and mark its coordination claim CLOSED;
- record `T4_ACCEPTED_HEAD` in the master coordination record without moving the shared T1 sibling base;
- hand off to T5 for repository-wide rename/move and collection audit.

## Fail-closed rules

- A failing historical snapshot is not evidence to change production.
- No retired test may disappear without replacement/supersede evidence in this plan and the closing acceptance record.
- No production source file may change in T4.
- If #210/#211 or the promoted drawing/toolbar semantic contracts expose a real production defect, stop TEST retirement and classify the defect separately.
- If no concrete GitHub Actions run exists after a QA trigger, fix the trigger prerequisite immediately; do not poll a nonexistent run.
