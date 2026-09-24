---
whd_doc_role: REFERENCE
whd_contract: issue528-b3-settings-exact-six-decision
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #528 / B3 — Settings Exact-Six Deletion-Test

- Parent accepted HEAD: `3d6709b3e6aafe5549e92ce6dac93a9dc5ab25ba`
- Tested HEAD: `9d15c242e10440b961cd7ac82c7d5deb1c2750f3`
- Prior decision: `KEEP_BRIDGE_COMPATIBILITY`
- Final decision: **`KEEP_CURRENT_BOUNDARY`**
- Production change: **0**

## DT evidence

- Exact-six total span: **277 LOC**
- Distinct bridge/domain helper dependencies: **16**
- Variant E removes only **1 / 6** old bodies.
- Remaining duplicate path count: **5**
- Full-app dependency in the tiny pure composer: false, but the real five bodies remain outside it.
- Moving the real box/corner projection bodies into `Phase6SettingsPanel` would violate presentation-owner purity.
- Moving them into `phase6_settings_profile_projection.py` would require bridge/domain callbacks or leave duplicate bodies.

## Tests

- RUN `35783860498 @ 9d15c242e10440b961cd7ac82c7d5deb1c2750f3` — SUCCESS.
- Settings owner suite: **26 passed / 6 skipped**.
- Xvfb Settings panel suite: **11 passed**.
- Artifact: `10719556532`.

## Decision

Do not create a second Settings projection owner and do not turn the existing pure projection module into a service bag. The exact-six stays at the application compatibility/dataflow seam for this Phase. This KEEP does not satisfy the Master quantitative budget by itself; Stage B continues with B4/B5/B6.
