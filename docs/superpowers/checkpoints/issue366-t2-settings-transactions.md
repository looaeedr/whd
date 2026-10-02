---
whd_doc_role: REFERENCE
whd_contract: issue366-t2-settings-transactions
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #366 / Phase 3 T2 — Settings / Corner / Structure Transaction Extraction

## Identity

- Master: #363
- Task: #366 / T2
- Fixed task baseline: `bb8c3d0272756629654127fbd86e9d7013d797e4`
- Branch: `refactor/issue366-phase3-settings-transactions-20260919`
- A/B validated candidate: `2adf22fa49d9d58e780bebe90617d68743d8a0a9`
- Production branch: `cleanup/2d-3d-sync`
- Status: **ACCEPTED**

## Characterization RED

Initial T2 ownership RED:

```text
RUN = 35430273758
HEAD = c21eccf3c1abd52bdfd656c2b63c2d69e3024ca3
EXPECTED_RED = 1
```

The RED proved that the bridge still owned canonical settings / corner / structure transaction state and semantic commit ordering.

Additional focused RED evidence:

```text
T2C corner/external RED = 35434127351
T2D family/width RED    = 35436798530
```

## Extracted Owner

Canonical T2 application transaction ownership now lives in:

```text
phase6_settings_transaction_controller.py
Phase6SettingsTransactionController
```

The controller owns:

- staged settings values and pending flush state
- 150 ms debounce transaction decision / job ownership
- box-body structure semantic commits
- EndCap FW and bottom-wrap semantic commits
- corner pair/type/mode/parameter semantic commits
- assembly intent semantic commits
- external revision / transaction-id acceptance
- symmetry transaction commit
- defaults payload construction
- total-width structure reconciliation
- cabinet-family transition semantics

The bridge retains Tk effects, widget reads/writes, event binding, render/invalidate calls, and live-publish effects.

## Focused Slice Evidence

```text
T2A settings stage GREEN     = RUN 35433925935
T2B structure/endcap GREEN   = RUN 35434092161
T2C corner/external GREEN    = RUN 35436580305
T2D family/width GREEN       = RUN 35437041830
```

T2B edge-control diagnostic:

```text
RUN 35430840888
exact baseline/candidate inherited RED parity confirmed
```

T2D Tk diagnostic:

```text
RUN 35436973877
exact baseline/candidate inherited RED parity confirmed
```

## Final Focused Acceptance

```text
RUN = 35437680016
HEAD = 7af7543fde4be8e5f2f205fd34d2153b31e78653
result = SUCCESS
```

Final focused gate proved:

- all five #366 ownership contracts GREEN
- pure settings / structure / assembly regressions GREEN
- all non-inherited real-Tk T2 regressions GREEN
- seven fixed inherited Tk RED nodes have exact baseline/candidate outcome parity
- source scope valid

The seven inherited nodes are baseline debt and were not reclassified as candidate success.

## Task-Scoped A/B Acceptance

```text
RUN = 35437788091
HEAD = 2adf22fa49d9d58e780bebe90617d68743d8a0a9

Headless job = 105883299963
Xvfb job     = 105883299802
classifier   = 105883550430
```

Headless:

```text
baseline  = 34 PASS / 16 SKIP / 0 FAIL
candidate = 34 PASS / 16 SKIP / 0 FAIL
assigned nodes = 50
```

Xvfb:

```text
baseline  = 51 PASS / 7 inherited FAIL
candidate = 51 PASS / 7 inherited FAIL
assigned nodes = 58
```

Classifier:

```text
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_TASK_DELTA = 0
ISSUE366_T2_AB_DECISION = GREEN
```

Artifacts:

- `issue366-t2-headless-ab` / artifact `10582717289`
- `issue366-t2-xvfb-ab` / artifact `10582612461`
- `issue366-t2-ab-qualification` / artifact `10582912225`

## Production Integration

Validated candidate was integrated non-force:

```text
PRE_INTEGRATION_PRODUCTION = bb8c3d0272756629654127fbd86e9d7013d797e4
VALIDATED_CANDIDATE = 2adf22fa49d9d58e780bebe90617d68743d8a0a9
CANDIDATE_AHEAD = 53
CANDIDATE_BEHIND = 0
FORCE = false
```

First production readback:

```text
production HEAD = 2adf22fa49d9d58e780bebe90617d68743d8a0a9
production vs validated candidate = identical
ahead = 0
behind = 0
```

This checkpoint is the only allowed post-validation writeback. The final #366 closure step must prove the checkpoint-containing branch differs from `2adf22fa...` only by this document, then non-force fast-forward production and read back identical.

The resulting production SHA is the immutable #367 / T3 baseline and is recorded in the #366 closure comment and #367 baseline freeze.
