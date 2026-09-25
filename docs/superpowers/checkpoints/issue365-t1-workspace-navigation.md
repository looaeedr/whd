---
whd_doc_role: REFERENCE
whd_contract: issue365-t1-workspace-navigation
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #365 / Phase 3 T1 — Workspace / Navigation State-Owner Extraction

## Identity

- Master: #363
- Task: #365 / T1
- Fixed task baseline: `0dd6561f3253d0a17714af316d5e9da90e24058f`
- Branch: `refactor/issue365-phase3-workspace-navigation-20260919`
- A/B validated source SHA: `3c7480cbaa30bf9d8286ff8f7eb239055ee92410`
- Production branch: `cleanup/2d-3d-sync`
- Status: **ACCEPTED**

## Characterization RED

Accepted RED evidence:

```text
RUN = 35426691665
job = 105853784269
EXPECTED_RED = 1
```

Baseline violations proved that bridge-owned T1 state-machine functions still directly owned workspace/navigation mutations, including activation begin/finish, selection, add/remove, derived-part synchronization, profile stash and switching flags.

The earlier RUN `35426665859` is not RED evidence; it was a harness error caused by missing `python3-tk`.

## Implementation

A new application-level controller now owns workspace/navigation transition decisions:

```text
phase6_workspace_navigation_controller.py
Phase6WorkspaceNavigationController
```

Existing canonical owners remain authoritative:

- `Phase6DesignerWorkspace` — committed Designer workspace state owner.
- `phase6_part_navigation.py` — pure DM7 navigation identity resolver.
- `Phase6WorkspaceNavigationController` — application-level transition/command owner.
- `fold_designer_bridge.py` — compatibility/view/effect wiring only for this slice.

No manufacturing solver, project I/O or Tk widget ownership was moved into the controller.

## Focused GREEN

```text
RUN = 35429825781
job = 105862291834

ownership contract = 3 PASS
workspace/navigation regressions = 21 PASS / 3 SKIP / 0 FAIL
```

The two intermediate DM7 regressions were compatibility-memory synchronization only. Explicit stable-child selection continued to resolve correctly; the legacy mirror was stale. The fix preserves canonical DM7 rules:

- explicit existing physical child keeps exact identity.
- stale explicit child fails closed.
- stale remembered child is cleared.
- explicit aggregate parent is never replaced by remembered child.

## Task-Scoped A/B Acceptance

Final A/B:

```text
RUN = 35429977766
HEAD = 3c7480cbaa30bf9d8286ff8f7eb239055ee92410
scope job = 105862693093
Headless job = 105862734610
Xvfb job = 105862734705
classifier job = 105862970822
```

Headless:

```text
baseline  = 50 PASS / 5 SKIP
candidate = 50 PASS / 5 SKIP
assigned nodes = 55
```

Xvfb:

```text
baseline  = 115 PASS / 8 inherited FAIL
candidate = 115 PASS / 8 inherited FAIL
assigned nodes = 123
```

The 8 Xvfb failures are exact inherited baseline failures; the node set is identical on baseline and candidate.

Classifier:

```text
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_TASK_DELTA = 0
ISSUE365_T1_AB_DECISION = GREEN
```

Artifacts:

- `issue365-t1-headless-ab` / 10579982722
- `issue365-t1-xvfb-ab` / 10580381630
- `issue365-t1-ab-qualification` / 10580361861

Note: artifact IDs are recorded from RUN 35429977766; GitHub remains the authority if names/IDs are re-read.

## Production Integration

Validated source candidate was integrated non-force:

```text
PRE-INTEGRATION_PRODUCTION = 0dd6561f3253d0a17714af316d5e9da90e24058f
VALIDATED_SOURCE_CANDIDATE = 3c7480cbaa30bf9d8286ff8f7eb239055ee92410
MERGE_BASE_STATUS = ahead
CANDIDATE_AHEAD = 17
CANDIDATE_BEHIND = 0
FORCE = false
```

First production readback:

```text
production HEAD = 3c7480cbaa30bf9d8286ff8f7eb239055ee92410
production vs validated source candidate = identical
ahead = 0
behind = 0
```

This checkpoint is an evidence-only writeback after the validated source integration. Final T1 closure must fast-forward production once more to the checkpoint-containing branch HEAD and prove:

```text
behavior-source diff from 3c7480c... = 0
production readback = identical
```

The exact resulting production SHA is recorded in the #365 closure comment and frozen as the concrete #366 / T2 baseline. This avoids a self-referential checkpoint-SHA writeback loop.
