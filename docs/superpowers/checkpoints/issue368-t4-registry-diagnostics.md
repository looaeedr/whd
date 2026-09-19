---
whd_doc_role: REFERENCE
whd_contract: issue368-t4-registry-diagnostics
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #368 / Phase 3 T4 — Registry / Diagnostics Controller Extraction

## Identity

- Master: #363
- Task: #368 / T4
- Fixed task baseline: `05e7820e319421cbfbd83e5b243d05cdc7596410`
- Branch: `refactor/issue368-phase3-registry-diagnostics-20260919`
- Behavior source SHA: `7a1f405abb84ef0569e240dde2b86f89da1ad23d`
- A/B orchestration SHA: `46fc31ecd55bcd39593b47b915fa3ae5022f4f2b`
- Production branch: `cleanup/2d-3d-sync`
- Status: **ACCEPTED**

## Characterization RED

Formal immutable-baseline RED:

```text
RUN = 35439339184
result = SUCCESS
T4_BASELINE = 05e7820e319421cbfbd83e5b243d05cdc7596410
PASS EXPECTED_T4_RED=1
```

Exact residual ownership:
- missing application-level registry/diagnostics controller
- bridge-owned candidate/evidence/rule-record/promotion-candidate state
- direct registry save/promote/load backend ownership
- missing registry/joint/diagnostic controller delegates

## Implementation

Created:
- `phase6_registry_diagnostics_controller.py`
- class `Phase6RegistryDiagnosticsController`

Controller owns:
- candidate current/stale lifecycle
- formula matrix evidence
- candidate save/promotion command ordering
- rule-record lookup state
- joint add/delete command routing
- diagnostic identity selection
- promotion-candidate state
- presentation-ready diagnostic status

Hard boundary preserved:
- no `fold_designer_bridge` reverse import
- no manufacturing-service ownership
- no assembly-collision solver ownership
- 3D candidate solve remains an injected bridge effect

Legacy fixture compatibility is seed/mirror only; canonical registry state remains controller-owned.

## Focused GREEN

```text
RUN = 35439540879
HEAD = 7a1f405abb84ef0569e240dde2b86f89da1ad23d
result = SUCCESS
```

Results:
- T4 ownership contract: 3 PASS
- pure registry/diagnostics regressions: 42 PASS
- real-Tk registry/diagnostic regressions: 8 PASS

## Task-Scoped A/B

```text
RUN = 35439645420
orchestration HEAD = 46fc31ecd55bcd39593b47b915fa3ae5022f4f2b
TESTED_SHA = 7a1f405abb84ef0569e240dde2b86f89da1ad23d
result = SUCCESS
```

Headless:
- baseline: 42 PASS / 0 FAIL
- candidate: 42 PASS / 0 FAIL
- assigned nodes: 42

Xvfb:
- baseline: 8 PASS / 0 FAIL
- candidate: 8 PASS / 0 FAIL
- assigned nodes: 8

Classifier:
```text
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_DIAGNOSTIC_DELTA = 0
ISSUE368_T4_AB_DECISION = GREEN
```

Both Headless and Xvfb lanes independently verified config.ini / DXF before-after digests.

## Production Acceptance

T4 may integrate only by non-force fast-forward from the immutable T4 baseline line. Final production readback must be identical to the task branch. The resulting production SHA is the immutable `T5_BASELINE`.
