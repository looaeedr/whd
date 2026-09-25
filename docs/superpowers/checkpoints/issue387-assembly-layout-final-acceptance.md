---
whd_doc_role: REFERENCE
whd_contract: issue387-assembly-layout-final-acceptance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #387 / #382 — 組合體 shared-content UI 最終驗收

## Accepted lineage

- Production baseline: `0947e546063c4c2118cb778d2798da5dbff682b3`
- T0: #383 — ownership characterization
- T1: #384 — retire permanent Structure Tree layout surface
- T2: #385 — presentation-only Door/BasePlate parent groups
- T3: #386 — all fresh assembly rows default collapsed
- T4 integration branch: `integration/issue387-assembly-layout-final-20260919`

T0→T3 is a direct descendant of production; preflight was ahead-only with no production drift.

## Final product result

- Normal part modes do not show/reserve a separate 板件／功能 region.
- Normal parts keep existing input/display content in the shared left area.
- 組合體 alone displays the part/function list in that same area.
- Each real part row retains show/hide plus existing read-only formed/blank/corner data.
- All fresh data rows default collapsed; show/hide remains usable in the header.
- BoxBody physical children stay under 箱身.
- `door_cN_rM` and `base_plate_cN_rM` are grouped under presentation-only 門 / 底板 parents without fake domain parts.
- Collapse is presentation state only.
- Existing main-selector / 截角資料 / MouseWheel contracts remain intact.
- No new editable assembly capability.

## Final combined evidence

RUN `35455382053` → SUCCESS.

- relevant headless ownership/persistence: 30 PASS / 9 SKIP
- Xvfb layout/navigation: 26 PASS / 1 SKIP
- Xvfb physical identity/visibility: 5 PASS
- NEW_EDIT_CAPABILITY = 0
- LAYOUT_ONLY = 1
- GEOMETRY_OWNER_DRIFT = 0
- DATAFLOW_OWNER_DRIFT = 0
- PROTECTED_DRIFT = 0

Validation evidence only judges the accepted result; it is not a production geometry source.
