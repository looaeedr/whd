---
whd_doc_role: CURRENT
whd_contract: implementation-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 280 / T5 Permanent TEST Reconciliation and Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explicitly reconcile the independently accepted T2/T3/T4 TEST-cleanup siblings, then move/split the already-approved permanent contracts into responsibility-based paths without changing production behavior or silently reducing coverage.

**Architecture:** T5 starts from the common T1 accepted head, merges the three accepted sibling heads as independent ancestors, freezes their accepted test semantics, then performs path-only moves plus the already-approved #211 behavior/architecture split. A machine-readable old-node/path mapping and collection gate make any unexplained disappearance fail closed.

**Tech Stack:** Python 3.12, pytest, Git/GitHub, Tk/Xvfb for UI contracts, existing `tools/test_lane_policy.py` taxonomy.

**Spec:** `WHD_TEST_CLEANUP_SPEC_2026-09-15.md`; Master #274; Issue #280; accepted evidence for #277/#278/#279.

## Global Constraints

- Fresh T5 branch starts from `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`.
- Accepted sibling inputs are immutable: T2 `eb967e92c951cec8fde9c76d171a9685232a3ea2`, T3 `e1d484c247af5b7f384a8883d31357efb7820049`, T4 `0eabb64a8308f74b9c8b66f982626d2907f00646`.
- All three accepted heads must become ancestors of the T5 reconciliation head before any rename/move.
- Tests are judges, never geometry/dimension/DXF/runtime-identity authority.
- No production source change is authorized.
- No skip/xfail masking, assertion weakening, golden rewrite, or behavior change is authorized.
- Collection count may decrease only for an explicitly approved retirement/merge mapping; T5 itself introduces no new retirement classification.
- QA-only workflows/evidence must not survive on the accepted task head.

---

### Task 1: Reconcile accepted T2/T3/T4 siblings

**Files:**
- Modify by merge only: accepted T2/T3/T4 test/docs/governance files.
- Create: `docs/superpowers/verification/2026-09-15-issue280-reconciliation-audit.md`

**Interfaces:**
- Consumes: three immutable accepted heads listed above.
- Produces: one reconciliation head where all three are Git ancestors and no sibling content is dropped.

- [ ] **Step 1: Verify sibling diff disjointness from T1**

Compare each accepted head against T1. Require no overlapping modified path among the T2/T3/T4 payloads unless explicitly reviewed. Current audited payloads are disjoint.

- [ ] **Step 2: Merge T2 into the fresh T5 branch**

Use a non-force merge preserving T2 as an ancestor. Verify `git merge-base --is-ancestor eb967e92... HEAD`.

- [ ] **Step 3: Merge T3 into the same T5 branch**

Use a non-force merge preserving T3 as an ancestor. Verify `git merge-base --is-ancestor e1d484c2... HEAD`.

- [ ] **Step 4: Merge T4 into the same T5 branch**

Use a non-force merge preserving T4 as an ancestor. Verify `git merge-base --is-ancestor 0eabb64a... HEAD`.

- [ ] **Step 5: Run reconciliation focused baseline**

Run the accepted T2/T3/T4 permanent files before moving them. Expected: no candidate regression; any failure stops rename work and is classified before changes.

---

### Task 2: Freeze the approved move/split manifest

**Files:**
- Create: `docs/superpowers/verification/2026-09-15-issue280-test-move-manifest.md`

**Interfaces:**
- Consumes: T0 inventory plus T2/T3/T4 accepted classifications.
- Produces: explicit old path → new path/node mapping used by collection audit.

- [ ] **Step 1: Record exact approved whole-file moves**

Use this mapping:

| Old path | New path | Responsibility |
| --- | --- | --- |
| `tests/test_phase6_semantic_doc_status.py` | `tests/governance/test_semantic_doc_status.py` | structured documentation governance |
| `tests/test_issue76_box_body_subtabs_2d_3d.py` | `tests/ui/test_box_body_physical_child_navigation.py` | user-visible logical/physical box-body navigation |
| `tests/test_box_body_single_source_t3.py` | `tests/architecture/test_box_body_single_source.py` | authoritative render/material single-source and no caller rebuild |
| `tests/test_issue209_part_panel_projection.py` | `tests/projection/test_part_panel_projection.py` | logical presence projection without identity rewrite |
| `tests/test_gui_drawing_contract.py` | `tests/ui/test_gui_drawing_contract.py` | durable drawing behavior |
| `tests/test_gui_toolbar_contract.py` | `tests/ui/test_gui_toolbar_contract.py` | operator-facing toolbar semantics |
| `tests/test_issue210_project_actions_move_contract.py` | `tests/architecture/test_project_actions_ownership.py` | project-action ownership / no reverse GUI dependency |

- [ ] **Step 2: Record the approved #211 split**

Split `tests/test_issue211_renderer_dependency_gate.py` without changing assertions:

- behavior nodes → `tests/projection/test_renderer_behavior.py`
  - `test_behavior_draw_grid_preserves_current_canvas_contract`
  - `test_behavior_resolved_feature_projection_preserves_current_primitives`
  - `test_behavior_baseline_secondary_skips_primary_outline_and_bend_layers`
- ownership/dependency nodes → `tests/architecture/test_renderer_ownership.py`
  - `test_structure_safe_helpers_move_to_render_2d_without_reverse_gui_dependency`
  - `test_structure_phase6_host_no_longer_defines_safe_helper_bodies`
  - `test_structure_existing_3d_deep_module_remains_the_only_new_3d_owner`

Shared test-only helpers (`RecordingCanvas`, `_instance`, imports/constants) are copied only where required; production code is not touched.

- [ ] **Step 3: Fail closed on unexplained issue-number migration**

Enumerate `tests/test_issue*.py`. T5 may move only files/nodes whose T0 or T2/T3/T4 classification is recorded in the manifest. Any additional issue-number file remains in place rather than being guessed/deleted.

---

### Task 3: Execute path-only moves and #211 split

**Files:**
- Move/create exactly the paths in Task 2.
- Delete only the old paths that have one-to-one or split mappings in the manifest.

**Interfaces:**
- Consumes: frozen move manifest.
- Produces: responsibility-based test paths with identical durable assertions.

- [ ] **Step 1: Create destination directories as needed**

Destinations: `tests/governance/`, `tests/ui/`, `tests/architecture/`, `tests/projection/`.

- [ ] **Step 2: Move whole-file contracts without semantic edits**

Preserve test function bodies except import/path adjustments strictly required by relocation.

- [ ] **Step 3: Split #211 by behavior vs ownership**

Preserve every existing #211 assertion exactly; only separate the six nodes into the two destination files.

- [ ] **Step 4: Search repository references to old paths**

Update only test-runner/docs/collection references that point to moved files. Do not change production imports or production source ownership.

---

### Task 4: Collection and semantic equivalence gate

**Files:**
- Create temporary QA workflow/evidence only on a delegated QA branch.
- Update move manifest with run identity after GREEN.

**Interfaces:**
- Consumes: post-move candidate.
- Produces: proof that approved node coverage survived relocation/split.

- [ ] **Step 1: Collect old accepted node inventory from pre-move reconciliation head**

Record nodeids for the mapped files before move.

- [ ] **Step 2: Collect new node inventory from candidate**

Normalize only the path prefix through the explicit manifest. Require every non-retired old function name to map to exactly one new node.

- [ ] **Step 3: Run focused governance/UI/projection/architecture contracts**

Run all moved/split destinations; use Xvfb for the UI files that require real Tk.

- [ ] **Step 4: Run outcome-control and source-drift gates**

Require no new skip/skipif/xfail, production-source drift `0`, and unchanged config/DXF protected manifest.

---

### Task 5: Closing audit and handoff to T6

**Files:**
- Create: `docs/superpowers/verification/2026-09-15-issue280-permanent-test-move-acceptance.md`
- Remove temporary QA workflow/evidence from the accepted task head.

**Interfaces:**
- Produces: `T5_ACCEPTED_HEAD` for Master #274 and #281/T6.

- [ ] **Step 1: Verify all three sibling accepted heads remain ancestors**

T2/T3/T4 ancestry must still be GREEN after all move commits.

- [ ] **Step 2: Verify accepted task diff contains tests/docs/governance only**

Any production/runtime file fails closed.

- [ ] **Step 3: Verify cleanup drift**

Tested candidate → closing head may contain acceptance docs/QA cleanup only; any test or production blob drift invalidates the prior GREEN.

- [ ] **Step 4: Close #280 only after terminal remote evidence**

Record run ID, exact counts, move manifest, collection equivalence, invariants, and final accepted head on Master #274. Then hand off to #281/T6.
