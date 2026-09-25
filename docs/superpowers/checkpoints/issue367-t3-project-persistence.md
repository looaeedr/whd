---
whd_doc_role: REFERENCE
whd_contract: issue367-t3-project-persistence
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #367 / Phase 3 T3 — Project / Persistence / Status / Output Extraction

## Identity

- Master: #363
- Task: #367 / T3
- Fixed task baseline: `e3ff53d3b8509759aed014a3ed8f83f23a65851a`
- Branch: `refactor/issue367-phase3-project-persistence-20260919`
- A/B validated source SHA: `1ab3dead9cc91dafaeba2af54b4e5ef8015281d0`
- Production branch: `cleanup/2d-3d-sync`
- Status: **ACCEPTED**

## Characterization RED

Formal intended RED:

```text
RUN = 35438555123
job = 105885295059
result = SUCCESS
PASS EXPECTED_T3_RED=1
```

Exact baseline ownership gaps:

- 10 missing `Phase6ProjectController` command methods.
- 3 direct bridge I/O owners:
  - `read_project`
  - `write_project`
  - diagnostic JSON writer.
- 9 bridge project/status/output command entry points without controller delegation.

Earlier runs `35438449256` and `35438513301` were harness errors and are not RED evidence.

## Implementation

T3 extends the existing `Phase6ProjectController`; it does not create a second ProjectSession owner.

Controller now owns command/persistence policy for:

- Designer project payload packaging.
- project load validation.
- fallback project write routing.
- diagnostic payload/write routing.
- lightweight dirty-workspace export payload.
- project status projection.
- settings-default persistence routing.
- STOCK output command.
- selected DXF export command.

Bridge retains only UI/effect responsibilities such as file dialogs, message boxes, Tk status variables, callback wiring, and collection of currently visible application state.

## Focused GREEN

```text
RUN = 35438684514
HEAD = 7dc519087afda65911cc81301f99254638d37dc7
job = 105885636849
result = SUCCESS
```

Results:

```text
T3 ownership contract = 3 PASS
pure project/session/file/diagnostics regressions = 33 PASS / 9 SKIP
Xvfb project round-trip authority regressions = 11 PASS
```

## Task-Scoped A/B Acceptance

```text
RUN = 35438810512
HEAD = 1ab3dead9cc91dafaeba2af54b4e5ef8015281d0
xvfb job = 105885967475
headless job = 105885967508
classifier job = 105886069784
result = SUCCESS
```

Headless:

```text
baseline  = 33 PASS / 9 SKIP / 0 FAIL
candidate = 33 PASS / 9 SKIP / 0 FAIL
assigned nodes = 42
```

Xvfb:

```text
baseline  = 22 PASS / 0 FAIL
candidate = 22 PASS / 0 FAIL
assigned nodes = 22
```

Classifier:

```text
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_PERSISTENCE_DELTA = 0
ISSUE367_T3_AB_DECISION = GREEN
```

This establishes task-scoped project round-trip/reload parity with no unexplained config.ini or DXF drift.

## Production Integration

Validated candidate preflight:

```text
PRE-INTEGRATION_PRODUCTION = e3ff53d3b8509759aed014a3ed8f83f23a65851a
VALIDATED_SOURCE_CANDIDATE = 1ab3dead9cc91dafaeba2af54b4e5ef8015281d0
CANDIDATE_AHEAD = 14
CANDIDATE_BEHIND = 0
FORCE = false
```

First production readback:

```text
production HEAD = 1ab3dead9cc91dafaeba2af54b4e5ef8015281d0
production vs validated source candidate = identical
ahead = 0
behind = 0
```

This checkpoint is evidence-only. Final T3 closure requires one docs-only non-force fast-forward and identical production readback. The resulting production SHA is frozen as the concrete #368 / T4 baseline.
