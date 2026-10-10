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

## DC 呼叫前的強制判斷

本 Skill 遵循 `AGENTS.md` 的 `DC_DEFAULT_DENY_EXPLICIT_SCOPE_GATE`：只有使用者在當次明確 `/接手`、`/派工` 最後的 `LOCALX_INTEGRATION` exact CI SUCCESS，或使用者明確授權本次 DC 用途才能使用。**預設 `DC_ACCESS_DENIED_BY_DEFAULT`**，連 `list_devices`／`ping` 都不得探測。其餘需求先說明必要原因、裝置／路徑、預計操作與影響，回報 `DC_AUTHORIZATION_REQUIRED`，取得當次明確核准前完全禁止 DC 或其他本機繞道。

公開交付按 `AGENTS.md` 的 `ISSUE_SCOPE_AUTHORIZATION_REUSE`：同一已核准 Issue、工作分支、`localX` 及施工範圍內的修正 commit 不因 SHA 改變重問；新 SHA 的 diff／CI 仍須核實，不可繞過平台安全審查或擴權至正式 X。

本 Skill 不得新增啟動授權檢查、claim、lease、工作槽、紀錄或協調交易；程式測試和 Git diff 才是修改成果證據.

產品工作先整合 localX；origin/localX 只作備份，正式 X 需使用者當次 /推推。純非產品文檔、治理、技能及治理專用測試，優先由 GitHub／雲端從最新 X 開獨立 governance/docs/skills 分支並直接 PR merge X；需通過 tools/change_lane_gate.py 白名單，不得夾帶產品檔案。**此 root-local-first Skill 不得當成治理任務存取 DC 的授權**；未經使用者本次明確允許，不得存取 CoreELEC／whd-dev。
