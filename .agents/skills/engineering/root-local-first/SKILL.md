---
name: root-local-first
description: WHD 本地施工與 localX 先行整合，無額外入口閘門。
whd_doc_role: CURRENT
whd_contract: root-local-first-workflow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first

此 Skill 僅適用於**使用者明確 `/接手`** 的本機施工路線：GitHub Git 供應來源，Remote Desktop Commander → CoreELEC `whd-dev` → `/workspace/whd` 工作，測試後依 `localX` 整合規則交付。**`/派工` 不得讀此 Skill 作為本機施工授權**：其 BUILD/TEST/COMMIT 必須 GitHub／雲端執行；只在 exact CI 通過後的 `LOCALX_INTEGRATION` 才能由 DC 進 RC 做**本機 `localX` 最終合併／驗證／同步**，不准施工。DC 實際無法連線時才能備援遠端 `localX` 並標示 `LOCALX_SYNC_PENDING`；不能用遠端施工能力不足當成使用本機的藉口。不要回退 Google Drive 或 .unpushed 當工作根目錄。

本 Skill 不得新增啟動授權檢查、claim、lease、工作槽、紀錄或協調交易；程式測試和 Git diff 才是修改成果證據。

產品工作先整合 localX；origin/localX 只作備份，正式 X 需使用者當次 /推推。純非產品文檔、治理、技能及治理專用測試可從本機最新 X 建獨立 governance/docs/skills 分支，直接 push PR merge 到 X；需通過 tools/change_lane_gate.py 的嚴格白名單，不得夾帶產品檔案。
