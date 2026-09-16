# Issue #292 T4 — Physical-Part Panel Extraction Implementation Plan

## Identity

- Parent: #287
- Task: #292 / T4
- Accepted predecessor: `#291 @ cefb1a11c837a73508a6a2b09eac77ba38c798f6`
- Work branch: `refactor/issue292-gui-phase2-t4-panels-20260916`
- Design: `docs/superpowers/specs/2026-09-16-issue292-t4-part-panels-design.md`
- Production integration is out of scope for T4 and remains owned by #296/T8.

## Execution rule

Use test-driven development. Every extraction slice follows RED → smallest GREEN → focused regression → commit. Do not move manufacturing/DXF/project/editor/render authority into panel modules to satisfy a structural gate. Any GitHub Actions validation must have a concrete RUN ID before polling; RUN=0 is a trigger/prerequisite failure, not a wait state.

## Task 1 — Prove the legal T4 LOC/responsibility gate before extraction

**Files**
- Add: `tests/process/test_issue292_t4_scope_reconciliation.py`
- Add only if needed for machine-readable audit: `tools/issue292_t4_scope_inventory.py`
- Modify only if evidence requires gate reconciliation: issue #292 acceptance text/design doc; no production code yet.

**RED first**
1. Add a test/audit that parses `gui.py` on the exact accepted predecessor and records:
   - exact `gui.py` LOC;
   - the reviewed T4-eligible method/callback set grouped by assembly/corner, shared panel helpers, box body, endcap, base plate, divider, door/multipart, indicator-box, and eligible Tk adapters from `init_variables`;
   - excluded T5/T6/T7/HOLD symbols;
   - removable implementation LOC and an explicit thin-delegate/import budget;
   - theoretical post-T4 `gui.py` LOC.
2. The test must fail closed when the issue's raw `<= 5,500` gate cannot be reached using only legal T4 responsibility.
3. Run:
   `python -m pytest -q tests/process/test_issue292_t4_scope_reconciliation.py`
4. Expected first result: RED if the raw 5,500 gate is not legally reachable, with measured numbers in the failure output; otherwise GREEN with proof that the gate is reachable.

**Hard stop**
- If legal T4 scope cannot reach 5,500, do not extract code yet.
- Write the measured responsibility-derived gate into #292/design, preserving a small wiring budget analogous to T2/T3 reconciliation.
- Re-run the reconciliation test until GREEN on the exact accepted predecessor.

**Commit**
- `test(#292): reconcile legal T4 structural scope`

## Task 2 — Add the T4 architecture/ownership RED contract

**Files**
- Add: `tests/test_issue292_gui_phase2_t4_part_panels.py`

**Contract assertions**
1. `gui_modules/parts/panels/` exists with:
   - `__init__.py`
   - `common.py`
   - `assembly_corner.py`
   - `box_body.py`
   - `endcap.py`
   - `base_plate.py`
   - `door.py`
   - `divider.py`
   - `multipart.py`
   - `indicator_box.py`
2. No new panel module imports `gui` or `compatibility.*`.
3. No panel module creates authoritative shadow stores named/serving as `active_part`, `existing_parts`, committed settings, door-layout committed truth, project truth, or geometry truth.
4. Moved root panel methods are removed or reduced to thin delegation within the reconciled line budget.
5. No giant module/class/method exceeds #292 limits.
6. `gui.py` satisfies the Task 1 reconciled T4 gate.
7. Legacy `gui_modules/part_panels.py` cannot remain a duplicate implementation after cutover.

**RED verification**
- Run:
  `python -m pytest -q tests/test_issue292_gui_phase2_t4_part_panels.py`
- Expected: RED because `gui_modules/parts/panels/` does not yet exist and panel implementations remain rooted in `gui.py`.
- Also run accepted T3 contract to prove the harness is healthy:
  `python -m pytest -q tests/test_issue291_gui_phase2_t3_selector.py`
- Expected: T3 GREEN while T4 contract is RED.

**Commit**
- `test(#292): add RED physical-part panel architecture contract`

## Task 3 — Census and retire the legacy shared panel helper correctly

**Files**
- Read/census: `gui_modules/part_panels.py`, `gui.py`, `gui_modules/parts/selector.py`, all repository callers of `_phase6_logical_part_present`
- Add: `gui_modules/parts/panels/__init__.py`
- Add: `gui_modules/parts/panels/common.py`
- Modify callers as proven by census.
- Delete `gui_modules/part_panels.py` if no real external caller remains; otherwise reduce it to an explicit deprecated compatibility shim with caller inventory and removal issue/date.

**Tests**
- Extend `tests/test_issue292_gui_phase2_t4_part_panels.py` to assert one implementation only and no internal dependency on the legacy path.
- Add focused behavior cases for logical dynamic identities (`door_c*`, `base_plate_c*`, `box_body:*`).
- Run T3 selector tests because presence presentation already consumes this logic.

**Commit**
- `refactor(#292): establish shared panel presentation primitives`

## Task 4 — Extract assembly/corner presentation and routing

**Files**
- Add: `gui_modules/parts/panels/assembly_corner.py`
- Modify: `gui.py`
- Modify/add focused tests for assembly type, endcap FW follow/selection, manual corner controls, parameter-lock presentation, fixed summaries/icons.

**Boundary**
- Move widget construction, display formatting, input normalization and event routing only.
- Keep `assembly_joint_state`, `assembly_relief_state`, `endcap_fw_state`, `manual_corner_state`, pair/lock/override committed ownership in the existing authoritative host/controller seam until T7.
- Do not move manufacturing corner interpretation or finished-dimension calculation.

**TDD sequence**
1. Add/strengthen focused tests that characterize defaults and callback outputs.
2. Observe RED only for the target structural delegation contract.
3. Move presentation functions into `assembly_corner.py` and leave root delegates only where required for compatibility/callers.
4. Run the T4 architecture test plus focused corner/endcap regression tests.

**Commit**
- `refactor(#292): extract assembly and corner panel presentation`

## Task 5 — Extract box-body, endcap, base-plate and divider panels

**Files**
- Add: `gui_modules/parts/panels/box_body.py`
- Add: `gui_modules/parts/panels/endcap.py`
- Add: `gui_modules/parts/panels/base_plate.py`
- Add: `gui_modules/parts/panels/divider.py`
- Modify: `gui.py`
- Preserve: `gui_modules/parts/subtabs.py` as the T3 physical-subtab owner.

**Behavior contracts**
- box-body panel must reuse T3 stable physical identity/subtab routing, not duplicate it;
- endcap FW/default/presence UI parity must remain exact;
- base-plate same/shrink controls must preserve existing values and routing;
- divider panel must preserve existing availability/defaults while leaving flat/form/outer/manufacturing semantics outside the panel.

**L2 rule**
For any input affecting manufacturing output, tests compare authoritative before/after results through the existing engine/controller path. Panel code itself must contain no replacement formula.

**Commit**
- `refactor(#292): extract core physical-part input panels`

## Task 6 — Extract door, multipart and indicator-box panels

**Files**
- Add: `gui_modules/parts/panels/door.py`
- Add: `gui_modules/parts/panels/multipart.py`
- Add: `gui_modules/parts/panels/indicator_box.py`
- Modify: `gui.py`

**Door contract**
- Move door layout widget creation, per-cell selection presentation, dimension input normalization, add/remove UI routing, receiving-inner-door controls and status refresh.
- Do not create a second `door_layout_columns`, `receiving_inner_doors`, handle-edge, scope, feature or indicator committed store.
- Existing state-changing root/controller seam remains authoritative until T7 where required.

**Multipart contract**
- Move only multipart input presentation not already owned by T3 navigation.
- Preserve top-level `箱身` logical selector and stable physical child identities.

**Indicator contract**
- Move input/configuration widgets and normalization/routing only.
- `draw_indicator_box` and other actual drawing remain T6.

**Commit**
- `refactor(#292): extract door multipart and indicator panels`

## Task 7 — Split eligible `init_variables` Tk adapters and remove duplicate root implementations

**Files**
- Modify: `gui.py`
- Modify the focused panel modules from Tasks 4–6.
- Do not add a generic all-part `variables.py`.

**Procedure**
1. Census variables created in `init_variables` that are exclusively UI adapters for one physical-part panel.
2. Move only those adapters/bindings to the corresponding panel setup path.
3. Leave cross-domain and host-owned committed values in the root/T7 seam.
4. Remove moved implementation bodies from `gui.py`; retain only explicit thin delegates required by established callers.
5. Re-run static shadow-state, forbidden-import, module/class/method size and root LOC tests.

**Commit**
- `refactor(#292): split panel Tk adapters and remove root duplicates`

## Task 8 — Focused L0/L1/L2/L4 acceptance

**L0 architecture**
Run at minimum:
- `python -m pytest -q tests/test_issue292_gui_phase2_t4_part_panels.py`
- `python -m pytest -q tests/test_issue291_gui_phase2_t3_selector.py`
- import/circular-dependency/static size scans from the new T4 contract.

**L1 model/state parity**
Cover:
- exact defaults;
- enable/disable/presence;
- edit/commit/cancel routing where existing panel controls expose it;
- receiving/vault/multipart availability;
- SettingsService/WorkspaceController ownership.

**L2 geometry-affecting input parity**
Exercise representative box-body/endcap/base-plate/door/divider inputs and compare authoritative resolved/manufacturing outputs to the accepted predecessor; do not compare panel-local formulas.

**L4 Xvfb**
Run relevant existing UI tests plus T4-focused cases for:
- receiving↔vault transitions;
- multipart panel/child behavior;
- door layout edits/cell selection;
- base-plate same/shrink;
- endcap FW;
- divider panel defaults/availability;
- indicator configuration;
- corner/manual controls;
- short-window/scroll behavior affected by moved panels.

**Protected invariants**
Require zero unintended drift under:
- `config.ini`
- `基準檔/**`
- `ae_engine/**` manufacturing authority
- `phase6_project_file.py`
- project schema / baseline DXF/reference artifacts.

**Commit**
- only if focused acceptance requires test-only contract additions: `test(#292): complete focused T4 parity coverage`

## Task 9 — Full Headless and Xvfb candidate acceptance with A/B classification

**QA branch/workflow**
- Create a temporary QA branch from the exact candidate HEAD; never put temporary acceptance workflow into production.
- The workflow must record exact candidate SHA and accepted predecessor SHA `cefb1a11...`.

**Runs**
1. Full Headless candidate suite.
2. Full Xvfb candidate suite.
3. If either is RED, extract exact FAILED nodeid set.
4. Run exact parent/candidate A/B for every residual set before classifying any failure as inherited.
5. Acceptance requires GREEN or candidate-only failure set = 0 with exact A/B proof.
6. Protected-drift and candidate-reconciliation jobs must be GREEN.

**RUN rule**
- After workflow creation, query for a concrete RUN ID.
- If no RUN exists, immediately repair trigger/ref/path/permission prerequisite; do not poll a nonexistent run.
- Once a concrete RUN exists, poll that same RUN/job to terminal.

## Task 10 — QA cleanup, closure proof and #292 completion

**Cleanup**
1. Remove all temporary QA workflows/helpers from QA branches/candidate as applicable.
2. Verify cleanup tree has no content drift relative to the validated candidate except intentional durable production/test/spec files.
3. Fresh-read the candidate branch HEAD and issue state.

**Owning finalization guard**
1. Build a terminal checkpoint for exact:
   - issue `#292`;
   - branch `refactor/issue292-gui-phase2-t4-panels-20260916`;
   - fresh candidate HEAD.
2. Include focused/full acceptance, A/B evidence, protected drift and QA-cleanup evidence.
3. Invoke canonical `tools/continuity_controller.py authorize-finalization` from the accepted guard implementation and save the proof.
4. Invoke `verify-finalization-proof` at the closure boundary using the same issue/branch/HEAD.
5. Any owner mismatch, stale checkpoint/proof or missing actual guard invocation fails closed.
6. Only after fresh issue/branch readback still matches the proof, close #292 as completed and read it back remotely.

**No production integration**
Do not merge/update `cleanup/2d-3d-sync` in T4. The accepted chain remains isolated until #296/T8.
