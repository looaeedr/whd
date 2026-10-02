---
whd_doc_role: REFERENCE
whd_contract: issue369-t5-2d-corner-view
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #369 / Phase 3 T5 — 2D / Corner-Data View Adapter Extraction

## Identity

- Master: #363
- Task: #369 / T5
- Fixed task baseline: `4137b62887c3dc20c6ee5bbd4d753f485dcaf23b`
- Branch: `refactor/issue369-phase3-2d-corner-view-20260919`
- Behavior source SHA: `823e1dc6ac186d27d814aac0226d4a243273ecee`
- A/B orchestration SHA: `1c1c9da954ba4093732773fed368b47a8f1cb997`
- Production branch: `cleanup/2d-3d-sync`
- Status: **ACCEPTED**

## Characterization RED

Formal immutable-baseline RED:

```text
RUN = 35439906863
result = SUCCESS
T5_BASELINE = 4137b62887c3dc20c6ee5bbd4d753f485dcaf23b
```

The RED established remaining bridge-owned 2D / Corner-Data view responsibilities before extraction.

## Implementation

Created:

- `phase6_corner_data_view_adapter.py`
- class `Phase6CornerDataViewAdapter`

The adapter owns view-only projection/glue for:

- Corner-Data navigation projection
- selected-part view identity
- authoritative unfold projection selection
- formed/unfolded display text formatting
- registry 2D preview geometry
- drawing-edge host placement
- Corner-Data canvas visibility lifecycle
- mousewheel zoom policy
- view payload assembly

Hard boundaries preserved:

- no manufacturing-geometry reconstruction in the view adapter
- no relief recomputation
- no invented physical-piece identity
- no domain/service reverse import of `fold_designer_bridge`
- authoritative workspace/render/manufacturing sinks remain the source of truth

## Focused GREEN

Final focused GREEN:

```text
RUN = 35440946636
HEAD = d93426ca0ef7fb6c7e11876a9b1a4d538c776900
result = SUCCESS
```

Results:

- T5 ownership contract: 3 PASS
- Headless 2D projection regressions: 35 PASS / 1 SKIP
- real-Tk/Xvfb regressions excluding exact inherited RED nodes: 12 PASS / 2 DESELECTED
- exact inherited Xvfb parity: PASS

The earlier run `35440317620` was a QA-harness false red because the GREEN workflow invoked `--json-report` without installing `pytest-json-report`. The harness dependency was fixed without changing T5 production behavior. Diagnostic run `35440205002` had already proven both inherited Xvfb RED nodes matched baseline/candidate exactly.

## Task-Scoped A/B

```text
RUN = 35441115019
orchestration HEAD = 1c1c9da954ba4093732773fed368b47a8f1cb997
TESTED_SHA = 823e1dc6ac186d27d814aac0226d4a243273ecee
result = SUCCESS
```

Headless:

- baseline: 36 assigned nodes / 0 FAIL
- candidate: 36 assigned nodes / 0 FAIL

Xvfb:

- baseline: 14 assigned nodes / 2 inherited FAIL
- candidate: 14 assigned nodes / 2 inherited FAIL
- exact outcome parity preserved

Classifier:

```text
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_2D_DELTA = 0
ISSUE369_T5_AB_DECISION = GREEN
```

Both Headless and Xvfb lanes independently verified config.ini / DXF before-after digests.

## Production Acceptance

T5 may integrate only by non-force fast-forward from the immutable T5 baseline line. Final production readback must be identical to the accepted T5 branch. The resulting production SHA is the immutable `T6_BASELINE`.
