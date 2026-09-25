---
whd_doc_role: REFERENCE
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue #281 / T6 full-lane validation preflight evidence

TASK: pytest coverage full lane validation UI Xvfb governance unit geometry projection persistence DXF architecture integration

READ_SKILL: Python測試實務
READ_SKILL: UI設計與去AI味
READ_SKILL: phase6-release-packaging

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

BOUNDARY:
- T6 is validation and classification only; TEST remains judge, never production/domain authority.
- A RED lane must be preserved and classified from exact node/signature before any production change.
- No skip/xfail weakening is authorized.
- Full primary-lane union must equal full collection; Xvfb UI is executed under a real display.
- config.ini, protected DXFs, tracked schema/geometry/runtime sources must not drift during validation.
- Release validation evidence must remain durable and fail closed; package/release policy is read as governance input only and is not promoted into product geometry authority.
