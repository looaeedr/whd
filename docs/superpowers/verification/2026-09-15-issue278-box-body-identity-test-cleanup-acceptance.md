---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 278 / T3 Box Body Identity / Single-Source TEST Cleanup Acceptance

- Date: 2026-09-15
- Master: #274
- Task: #278 / T3
- Exact parent: `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`
- RED candidate: `a76b5c413608e1268100bb8db197b6df469a2361`
- RED classifier run: `34985361465` — SUCCESS
- Exact tested head: `8c9596b97b53830034d261955649c47ac4b7cc33`
- Acceptance run: `34986057319` — SUCCESS

## RED classification evidence

The exact T1 parent was re-run before migration and again in acceptance:

1. `tests/test_issue76_box_body_subtabs_2d_3d.py::test_designer_box_body_stays_one_top_level_part_but_has_switchable_physical_subtabs`
   - parent result: RED
   - exact failure: `box_body_piece_selector.winfo_manager()` returned `''`
   - classification: `TEST_CONTRACT_DRIFT_IMPLEMENTATION_DETAIL`
   - reason: the legacy Notebook is internal compatibility state; the common hierarchy / Structure Tree is the current physical-child navigation contract.

2. `tests/test_box_body_single_source_t3.py::test_receiving_corner_data_box_body_uses_same_authoritative_context_projection`
   - parent result: RED
   - exact failure: actual logical identity `box_body` versus stale expected `box_body:left_side`
   - classification: `TEST_CONTRACT_DRIFT_LOGICAL_VS_PHYSICAL`
   - reason: logical aggregate identity and explicit physical-child identities are distinct contracts.

Durable sibling contracts were GREEN in the same RED classifier run before any target-test migration.

## Migrated durable contracts

- `box_body` remains the single logical top-level box-body identity.
- Receiving physical children remain explicit:
  - `box_body:left_side`
  - `box_body:back`
  - `box_body:right_side`
- The hierarchy projection exposes those physical children under logical `box_body` without promoting them to top-level logical parts.
- Explicit physical-child selection retains stable identity and consumes the same authoritative render/material data used by 3D.
- Logical Corner Data selection remains `box_body`; it is not silently rewritten to the first physical child.
- Caller-side structural Box Body rebuild remains forbidden.
- `tests/test_issue209_part_panel_projection.py` continues to verify logical presence projection without redefining physical identity.

## Fresh GREEN evidence

Acceptance run `34986057319` executed the three T3 files under Xvfb:

- `tests/test_issue76_box_body_subtabs_2d_3d.py`
- `tests/test_box_body_single_source_t3.py`
- `tests/test_issue209_part_panel_projection.py`

Result: **11 passed / 0 failed**. Tk emitted 231 missing-glyph font warnings; they did not alter test outcomes.

Additional gates:

- parent RED provenance: **PROVEN**
- outcome-control drift: **0** new skip / skipif / xfail weakening
- production source drift: **0**
- `config.ini` / DXF protected manifest before-after diff: **empty / GREEN**

## Scope / safety

Base→tested changed paths were limited to:

- `tests/test_issue76_box_body_subtabs_2d_3d.py`
- `tests/test_box_body_single_source_t3.py`
- T3 implementation plan
- temporary T3 QA workflow

Production geometry, DXF, dimensions, UI implementation, and runtime physical-part identity were not changed.

## Parallel-chain rule

T3 is a sibling of T2 and T4. Its accepted closing head must be recorded independently on Master #274; it does not advance the serial accepted head and does not become #279 / T4's parent. #279 remains based on the common T1 accepted head:

`a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`

Only #280 / T5 may reconcile the independent T2/T3/T4 accepted heads after all three are accepted.

## Result

`ISSUE278_T3_BOX_BODY_TEST_CLEANUP_ACCEPTED=1`
