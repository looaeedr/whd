---
name: 推推
description: WHD localX 人工發布指令；只有當次使用者輸入 /推推 才可提案合併至 X。
whd_doc_role: CURRENT
whd_contract: localx-explicit-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /推推 — 唯一正式 X 發布授權
一般修改和測試於本地 `/workspace/whd` 的 `localX` 完成。
`origin/localX` 僅為備份，不等同於 X 發布。
使用者沒有明確下達當次 `/推推` 前，禁止任何人或排程自動將變更合併至 `cleanup/2d-3d-sync`。
只有在使用者要求發布後，才可確認 exact PR、head SHA、target SHA、測試成果、使用 `tools/localx_publish_gate.py` 校驗 owner 核准並向 X 發布。
`/推推 文檔` 或 `/推推 主體` 只屬範圍分類，不是永久授權。
