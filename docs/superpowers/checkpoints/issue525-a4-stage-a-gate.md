---
whd_doc_role: REFERENCE
whd_contract: issue525-a4-stage-a-gate
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #525 / Phase 6 A4 — Stage A Combined + Mandatory Reduction Gate

- Master: #520
- Issue: #525
- Parent accepted HEAD: `144577021f407e4cc0e52dc0a6d433f01c603489`
- First Combined RUN: `35766572872 @ 3fb0c2a1d0b07dde290b1b905c54499ea41896c8` — FAIL
- Replacement Combined RUN: `35766956819 @ d4f2d0139ef022e8586b2cc292a1e87bd642fd2d` — SUCCESS
- Artifact: `10712466696 / issue525-stage-a-gate`

## Recovery from first Combined failure

First Combined result:
- **3 failed / 81 passed / 1 skipped**
- all 3 failures were in `tests/process/test_issue426_phase5_t5_bridge_compression.py`
- stale oracle required `_phase6_assembly_presentation_groups` to remain an `ast.FunctionDef`

Phase 6 v1.4/A3 explicitly permits behavior-identical thin delegates to collapse into direct identity aliases. The stale guard was minimally updated to recognize either:
- top-level `FunctionDef`, or
- top-level direct alias `Assign`

The original 15-entry boundary count and diagnostics-separation assertions remain intact. Production was not changed by this recovery.

## Replacement Combined acceptance

RUN `35766956819`:
- **84 passed / 1 skipped / 0 failed**
- one integrated Stage-A work-order HEAD
- fixed A0 census is the quantitative authority

## Mandatory reduction gate

Machine result:

- `BASELINE_LOC=7806`
- `STAGE_A_FINAL_LOC=7796`
- `STAGE_A_REDUCTION=10`
- `MIN_REDUCTION=1000`
- `EFFECTIVE_FINAL_CEILING=6500`
- `REDUCTION_GATE_GREEN=false`
- `CEILING_GATE_GREEN=false`
- **`STAGE_B_REQUIRED=true`**

This is the only legal Stage-A decision. Stage A is not allowed to end the Master chain after a 10-line reduction.

## Handoff

Stage B is now mandatory. The already-published issues are unblocked:

- #526 B1 — Part Editor Deletion-Test / Boundary Reconsideration
- #527 B2 — Workspace Shell Deletion-Test / Boundary Reconsideration
- #528 B3 — Settings Exact-Six Boundary Reconsideration
- #529 B4 — Linked Endcap Boundary Reconsideration
- #530 B5 — Derived Projection / Request Assembly Reconsideration
- #531 B6 — Facade Compatibility Audit Controller

B6 bounded audit batches must now be materialized from the A0 exact 69-entry facade inventory, at most 12 entries per batch.

## Acceptance

- [x] integrated Stage-A architecture regressions GREEN
- [x] stale architecture oracle repaired without production change
- [x] A0 fixed quantitative authority preserved
- [x] one machine decision emitted
- [x] `STAGE_B_REQUIRED=true`
- [ ] one-shot workflow cleanup
- [ ] tested-head → closing-head production/test drift = 0
