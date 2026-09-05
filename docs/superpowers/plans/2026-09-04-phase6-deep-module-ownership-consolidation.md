# Phase6 Deep Module Ownership Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Phase6 deep-module ownership consolidation without changing canonical mechanical outputs, then verify and package the result.

**Architecture:** Introduce one pure shared workspace-state contract that is instantiated separately by Main committed and Designer draft lifecycle owners. Deepen the existing cabinet-family registry into a narrow functional capability facade so receiving-specific mechanical choices are resolved by the family owner instead of GUI/Bridge/Fold/Manufacturing literal branches. Run the ProjectSession deletion/reuse test and, because production has only the Controller caller, reduce direct production access to Session while preserving transaction state inside the Controller boundary.

**Tech Stack:** Python 3, pytest, Tk/Xvfb, Phase6 release runner, ZIP release tooling.

**Spec:** `/mnt/data/2026-09-04-phase6-deep-module-ownership-consolidation-design.md`

## Global Constraints

- `config.ini` must remain byte/SHA256 unchanged.
- `.p6fold` schema must not change.
- `INSERT / OVERLAY / INSERT_OVERLAY / WRAP`, CornerType, Certified Registry, canonical manufacturing geometry and receiving mechanical results must not change.
- Main committed workspace and Designer draft workspace must remain separate mutable instances; no third cross-lifecycle mutable store.
- Shared Workspace State Core may contain only `existing_parts`, `active_part`, `part_profiles`, `box_body_structure`.
- Receiving policy must not own Tk/rendering/ProjectSession/manufacturing geometry/Certified Registry answers.
- UPDATE must not include `config.ini`; FULL and UPDATE-family artifacts must share one Asia/Taipei timestamp.
- No git repository is present in the supplied FULL archive, so task checkpoints/journal ZIPs replace git commits/worktrees for recovery evidence.

---

### Task 1: Shared Workspace State Contract

**Files:**
- Create: `phase6_workspace_state.py`
- Modify: `phase6_workspace_controller.py`
- Modify: `phase6_designer_workspace.py`
- Test: `tests/test_phase6_workspace_state.py`
- Test: `tests/test_phase6_workspace_controller.py`
- Test: `tests/test_phase6_designer_workspace.py`

**Interfaces:**
- Produces `SharedWorkspaceState`, `normalize_existing_parts()`, and active repair policies `first`, `none`, `raise`.
- Main Controller owns one instance and chooses `first` for invalid committed active values.
- Designer owns a different instance and chooses `none` for snapshot/remove repair and `raise` for explicit switching.

- [ ] Write failing pure-Python tests for deterministic part ordering, mandatory box_body, duplicate/blank cleanup, three active repair policies, profile stash preservation, defensive snapshot copies, and structure canonicalization.
- [ ] Add ownership AST tests proving the shared core imports no Tk/ProjectSession/renderer/manufacturing and lifecycle-only fields are absent.
- [ ] Run the focused tests and verify RED before implementation.
- [ ] Implement the minimal shared state contract and migrate Main Controller to it without moving fallback/authoritative or box_body_profile responsibility.
- [ ] Migrate DesignerWorkspace to its own shared-state instance without moving selected/features/dirty/switching responsibility.
- [ ] Run focused workspace tests and verify GREEN.
- [ ] Create a physical T1 checkpoint ZIP and append journal evidence.

### Task 2: Workspace Projection and Project Transaction Regression

**Files:**
- Modify: `gui.py`
- Modify: `fold_designer_bridge.py`
- Test: `tests/test_phase6_designer_workspace.py`
- Test: `tests/test_phase6_project_file.py`
- Test: `tests/test_phase6_project_controller.py`

**Interfaces:**
- Main/Designer adapters consume one owner snapshot for the four shared fields instead of reconstructing those fields independently.
- Confirm commits only a Main re-composed canonical snapshot; Save with active draft reads committed only.

- [ ] Add failing AST/integration tests that reject manual shared-field backing state/projection and lock Cancel/Confirm/Save behavior.
- [ ] Run focused tests RED.
- [ ] Replace hand repair/projection of the four shared fields with owner snapshots while preserving lifecycle/domain-specific fields.
- [ ] Run focused transaction tests GREEN.
- [ ] Create a physical T2 checkpoint ZIP and append journal evidence.

### Task 3: Cabinet Family Capability Facade and Receiving Caller Migration

**Files:**
- Create: `ae_engine/cabinet_types/policy.py`
- Modify: `ae_engine/cabinet_types/__init__.py`
- Modify: `ae_engine/cabinet_types/registry.py` only if registration metadata is required by the facade
- Modify: `gui.py`
- Modify: `fold_designer_bridge.py`
- Modify: `phase6_fold_profiles.py`
- Modify: `phase6_endcap_semantics.py`
- Modify: `ae_engine/manufacturing_api.py`
- Test: `tests/test_phase6_cabinet_family_policy.py`
- Test: existing receiving/fold/manufacturing ownership tests

**Interfaces:**
- `policy_for_snapshot()` / `policy_for_model()` resolve narrow capabilities from the registered family module.
- Generic callers ask capabilities such as baseline feature model, door nameplate datum, fixed structure, fold transform, EndCap depth compensation/effective FW/corner semantics, and receiving-registry applicability; callers do not import `receiving` directly for mechanical formula selection.
- AssemblyJoint relation remains graph-owned; the family policy supplies only family geometry/query inputs.

- [ ] Add failing tests for generic capability resolution and AST guard preventing new literal `受電箱` + mechanical formula branches/imports in GUI/Bridge/Fold/Manufacturing.
- [ ] Run focused policy tests RED.
- [ ] Implement the functional facade with safe generic defaults for Vault/RO rather than an empty OO hierarchy.
- [ ] Migrate formula-selection callers to the facade, leaving UI labels/migration recognition and explicit operator family selection where legitimate.
- [ ] Run receiving fresh/legacy/WRAP/registry/fold/manufacturing tests GREEN and prove mechanical result equivalence.
- [ ] Create a physical T3 checkpoint ZIP and append journal evidence.

### Task 4: ProjectSession Deletion/Reuse Decision and Public Surface Consolidation

**Files:**
- Modify: `phase6_project_controller.py`
- Modify: `gui.py`
- Modify: tests for controller/project-file/session ownership
- Create: `docs/superpowers/specs/2026-09-04-phase6-project-session-deletion-evidence.md`

**Interfaces:**
- Evidence must list every production `ProjectSession` caller.
- If only Controller is real production caller, Controller becomes the sole production transaction API and stores Session internally; external GUI behavior uses Controller methods/projections only.
- Session state machine may remain in its physical file and keep unit tests as internal implementation evidence.

- [ ] Add failing ownership test proving production outside Controller does not directly coordinate Session ordering.
- [ ] Record deletion/reuse evidence from `rg`/AST audit.
- [ ] Move GUI tests/compatibility reads to Controller projection methods where necessary; keep transaction semantics unchanged.
- [ ] Run ProjectSession state-machine tests plus Controller/GUI transaction tests GREEN.
- [ ] Create a physical T4 checkpoint ZIP and append journal evidence.

### Task 5: Ownership Guard and Focused Integration Gate

**Files:**
- Create/modify ownership guard tests only as required.

- [ ] Run all ownership, workspace, family, receiving, project transaction, assembly, collision, fold, EndCap and manufacturing focused tests in isolated process groups.
- [ ] Fix only regression root causes; do not modify mechanical truth to satisfy tests.
- [ ] Re-run preflight with the final changed-file set and evidence file.
- [ ] Verify `config.ini` SHA256 equals `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.
- [ ] Create a pre-release checkpoint ZIP and append journal evidence.

### Task 6: Full Release Verification and Packaging

**Files:**
- Generate release evidence/logs and delivery artifacts.

- [ ] Run fresh resumable Headless full suite with `tools/phase6_release_test_runner.py` journal/state.
- [ ] Run fresh resumable Xvfb full suite independently with its own journal/state.
- [ ] Run real GUI transaction/stress smoke required by the project gate.
- [ ] Run 2D/3D/DXF/NC parity and assembly matrix gates available in the package.
- [ ] Verify `config.ini` SHA unchanged before packaging.
- [ ] Package FULL with Asia/Taipei timestamp. If canonical update baseline from `release_required_artifacts.json` is unavailable, produce explicitly named `UPDATE_FROM_120434` instead of falsely labeling it canonical UPDATE.
- [ ] Verify ZIP duplicate entries, CRC/testzip, SHA256, UPDATE excludes `config.ini`, and fresh extraction.
- [ ] Run formal fresh extracted FULL release gate.
- [ ] Publish final checkpoint/release links and exact validation counts.
