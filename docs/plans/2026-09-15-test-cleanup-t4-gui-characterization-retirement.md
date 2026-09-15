# TEST Cleanup T4 — GUI Characterization Retirement Plan

Issue: #279
Parent: #274
Dependency: #276 / T1
Parallel siblings: T2 / T3 / T4
Authoritative parent: `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`

## Scope lock

This task is test-governance cleanup only. Production/runtime geometry, DXF authority, rendering ownership, UI runtime behavior, persistence, and manufacturing semantics must not change.

T4 does not perform the repository-wide rename/move planned for T5. Issue-number filenames may remain for the durable #210/#211 contracts until T5, but migration-only #206 coverage may be retired only after permanent successor coverage exists.

## Classification

### `tests/test_issue206_gui_modularization_characterization.py`

1. `test_corner_preview_canvas_point_characterization`
   - Classification: permanent UI/drawing transform behavior.
   - Authority: `gui_modules.drawing.transform_corner_preview_point` / host delegation.
   - Action: promote to a permanent semantic drawing contract.

2. `test_corner_preview_transform_keeps_y_flip_and_bias_sign`
   - Classification: permanent UI/drawing transform behavior.
   - Authority: `gui_modules.drawing.transform_corner_preview_point`.
   - Action: promote to the same permanent drawing contract.

3. `test_toolbar_presentation_characterization`
   - Classification: mixed durable toolbar semantics + migration-era exact snapshot.
   - Durable contract: required project action labels map to the expected host callbacks; allowed theme values are Light/Dark; default is a valid current theme and remains Light unless separately changed by product requirements.
   - Incidental detail: exact `theme_width == 8` and whole-dataclass equality are not T4 product requirements.
   - Action: replace with semantic permanent toolbar contract; do not lock width or full object representation.

4. `test_render_drawing_scene_characterization`
   - Classification: migration-only exact canvas-call snapshot / duplicate coverage.
   - Replacement: `tests/test_issue211_renderer_dependency_gate.py` behavior tests cover grid rendering, resolved feature rendering, baseline-secondary rendering, plus permanent renderer ownership/dependency boundaries.
   - Action: retire only after focused #211 behavior tests are re-run green on the exact T4 candidate.

### `tests/test_issue210_project_actions_move_contract.py`

- Classification: permanent architecture/dependency contract.
- Preserve: project action ownership in `gui_modules/project_actions.py`, host delegation, no reverse dependency.
- T4 action: retain unchanged unless a test-only annotation is required. Repository-wide naming/move is T5.

### `tests/test_issue211_renderer_dependency_gate.py`

- Classification: permanent rendering behavior + architecture/dependency contract.
- Preserve:
  - current grid behavior
  - resolved feature projection behavior
  - baseline-secondary behavior
  - 2D renderer ownership in `gui_modules/render_2d.py`
  - no reverse `gui` dependency
  - `Phase6FinalSceneView` remains the sole approved new 3D owner; no new `gui_modules/render_3d.py`
- T4 action: retain unchanged unless a test-only annotation is required. Repository-wide naming/move is T5.

## TDD / evidence sequence

### Step 1 — Parent classifier

On an isolated QA branch rooted at this task head:

- prove the task lineage descends from the T1 parent and not T2/T3 accepted heads;
- prove current #206 contains migration snapshot coupling (whole toolbar snapshot / `theme_width` and exact canvas call list);
- prove permanent successor drawing/toolbar test files do not yet exist on the parent;
- run current #206/#210/#211 focused tests to establish the parent behavior baseline;
- classify this as `MIGRATION_CHARACTERIZATION_PRESENT`, not as a production defect.

### Step 2 — Permanent successor tests

Create `tests/test_gui_drawing_contract.py`:

- verify `(x, y, bias) -> (x, -y-bias)` using representative positive/negative/zero data;
- verify the host corner-preview adapter preserves the same externally observable transform where needed;
- avoid source-text or exact temporary-module-location coupling except the permanent no-reverse-dependency architecture gate already covered elsewhere.

Create `tests/test_gui_toolbar_contract.py`:

- assert required project action label -> callback mapping;
- assert allowed theme values are `Light` and `Dark`;
- assert default is `Light` and belongs to allowed values;
- do not assert combobox pixel/character width or whole-dataclass equality.

### Step 3 — Retire migration-only #206 file

Delete `tests/test_issue206_gui_modularization_characterization.py` only after both permanent successor files exist.

Retirement evidence:

| Retired node | Replacement |
| --- | --- |
| corner preview adapter characterization | `tests/test_gui_drawing_contract.py` |
| corner transform matrix characterization | `tests/test_gui_drawing_contract.py` |
| toolbar exact presentation snapshot | `tests/test_gui_toolbar_contract.py` semantic contract |
| render exact canvas-call snapshot | #211 grid/resolved-feature/baseline behavior tests |

### Step 4 — Focused candidate validation

Run on the exact candidate SHA:

- `tests/test_gui_drawing_contract.py`
- `tests/test_gui_toolbar_contract.py`
- `tests/test_issue210_project_actions_move_contract.py`
- `tests/test_issue211_renderer_dependency_gate.py`

Requirements:

- 0 failures
- no new skip/xfail masking
- #210/#211 architecture gates remain green
- no production/runtime file changes

### Step 5 — Outcome-control and protected invariants

Verify:

- `PRODUCTION_SOURCE_DRIFT=0`
- no geometry/DXF authority changes
- config and protected DXF/schema manifest unchanged
- no assertion weakening by skip/xfail or broad deselection
- T1 parent -> candidate diff is TEST + plan/acceptance evidence only

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
- If #210/#211 permanent contracts expose a real production defect, stop TEST retirement and classify the defect separately.
- If no concrete GitHub Actions run exists after a QA trigger, fix the trigger prerequisite immediately; do not poll a nonexistent run.
