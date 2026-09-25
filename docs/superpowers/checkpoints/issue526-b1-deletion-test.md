---
whd_doc_role: REFERENCE
whd_contract: issue526-b1-part-editor-deletion-test
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #526 / B1 — Part Editor Deletion-Test

## Identity

- Master: #520
- Issue: #526
- Requirement Authority: user-approved Phase 6 v1.4
- Approved RED: R1 / R2
- Accepted parent: `4d085c4d2daf172bf55684c87e6086572d9d818c`
- Deletion-Test RUN: `35781297993 @ 0b8126f5b016fc0b1eaa58aad821d79a88b6f1f7`
- Artifact: `10718655323`

## DT-0 — frozen boundary

Candidate cluster:

- `_fix11_activate_part`
- `_fix11_save_current_part`
- `_phase6_install_part_editor_compatibility`

Prior accepted decision: `C_KEEP_BRIDGE_COMPATIBILITY`.

Current deep owners remain:

- `Phase6WorkspaceNavigationController`
- `Phase6DesignerWorkspace`
- `Phase6FoldDesignerSettingsCoordinator`
- `Phase6SettingsPanel`
- `Phase6BendingUI`
- command-router update scheduler
- FinalScene/render sink

## DT-1 — responsibility decomposition

The cluster spans transaction ordering, workspace state reads, presentation construction/effects,
navigation, profile persistence routing, Settings projection, update-intent submission, and
legacy compatibility/public facade routing. Domain/manufacturing ownership is not assigned
to this boundary.

## DT-2 — disposable variants

### Variant K — inline responsibility

The disposable K worktree expands navigation responsibility back into the caller.

Observed:

- direct `designer_workspace.begin_switch` / `finish_switch` mutation returns to caller;
- caller regains save-before-identity-switch ordering knowledge;
- caller must coordinate presentation effect ordering;
- full-app dependency becomes explicit.

This is a KEEP structural signal.

### Variant E — bounded coordinator

The disposable E worktree builds a no-Tk/no-manufacturing/no-bridge coordinator with five
bounded ports and proves the ordering:

`plan → save → begin → presentation → finish`.

Observed:

- forbidden imports: **0**
- full-app dependency: **false**
- ordering unit: **GREEN**
- opaque presentation callback: **true**
- old bridge body removed: **false**
- duplicate path count: **1**
- bridge symbols removed: **0**

The coordinator can reproduce ordering but cannot delete the actual bridge presentation/state
body without hiding that body behind an opaque callback or recreating a full-app-shaped port
surface. That is middle-man extraction rather than a deep owner.

## DT-3 — structural decision signals

KEEP signals:

1. Variant K returns direct Workspace mutation and cross-owner ordering to the caller.
2. Variant K requires full app knowledge.
3. Variant E does not reverse-import bridge and has bounded ports, but old implementation
   remains required.
4. Deleting the old body would require moving unrelated Tk/presentation/state-projection
   responsibilities into the coordinator.
5. Existing owner modules already hold the deep state/navigation/settings/scheduler contracts.

No valid EXTRACT/DEEPEN signal satisfies the v1.4 requirement that the old implementation be
actually deleted with duplicate production path = 0.

## DT-4 — behavior / invariant evidence

- Baseline focused owner/invariant suite: **24 PASS / 3 SKIP**
- Exact Xvfb save-before-identity-switch operator path: **1 PASS**
- Variant E ordering unit: **GREEN**
- No reverse import introduced.
- No second composition root introduced.
- No full-app owner interface introduced.
- Current accepted activation ordering remains:
  `plan → save outgoing → begin activation → presentation/effects → finish activation`.

## DT-5 — decision

**`B1_KEEP_COMPATIBILITY`**

This does not mean “large function therefore keep.” It means the formal v1.4 Deletion-Test
did not prove a deep extraction: K leaks state/order knowledge back to the caller; E becomes
a middle-man unless the old body is retained.

No prior decision is superseded.

## DT-6 — machine evidence

Machine-readable decision:

`docs/superpowers/checkpoints/issue526-b1-deletion-test.json`

Raw disposable-worktree/test evidence remains in GitHub Actions artifact `10718655323`.

## Production effect

- Production behavior change: **0**
- Bridge symbols removed: **0**
- Bridge LOC reduction from B1: **0**

This is allowed for one Stage B boundary; it does **not** satisfy the Master reduction gate.
Continue directly to #527 / B2 Workspace Shell Reconsideration.
