---
name: 推推
description: WHD 產品修改由 localX /推推 發布；純治理文件採治理直送硬閘門，不需要 /推推。
whd_doc_role: CURRENT
whd_contract: localx-explicit-publish
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /推推 — 產品通道發布授權

產品程式、GUI、幾何、DXF、製造資料、產品測試及混合變更必須先本地施工、測試、整合至 `localX`，`origin/localX` 只是備份。未收到使用者當次 `/推推`，不得把產品改動合併至 `cleanup/2d-3d-sync`。
產品正式發布仍驗證 exact PR、head SHA、target SHA 及 GitHub owner comment，由 `tools/localx_publish_gate.py` 判斷。
**純治理直送例外**：只有 `tools/change_lane_gate.py` 判定為 `GOVERNANCE_DIRECT_X` 的非產品修改，不需要 `/推推`。從最新 X 建立 `governance/*`、`docs/*` 或 `skills/*` 本地分支，檢查後直接 push/PR/merge 至 X；禁止與產品變更混合。
不得用任意的「文檔」文字標籤繞過機器路徑檢查；unknown/mixed = 產品通道。
`/推推 文檔` 和 `/推推 主體` 為相容命令，不能放寬產品通道的人工授權。
