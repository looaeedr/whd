---
name: root-local-first
description: WHD 本地施工與 localX 先行整合，無額外入口閘門。
whd_doc_role: CURRENT
whd_contract: root-local-first-workflow
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# root-local-first

施工來源使用 GitHub Git，日常內容修改在使用者指定的 executor-local workspace 完成。使用者指定 /接手 時，使用 Remote Desktop Commander → whd-dev → /workspace/whd；工作分支修改後經測試整合至本地 localX。不要回退 Google Drive 或 .unpushed 當成工作根目錄。

本 Skill 不得新增啟動授權檢查、claim、lease、工作槽、紀錄或協調交易；程式測試和 Git diff 才是修改成果證據。

產品工作先整合 localX；origin/localX 只作備份，正式 X 需使用者當次 /推推。純非產品文檔、治理、技能及治理專用測試可從本機最新 X 建獨立 governance/docs/skills 分支，直接 push PR merge 到 X；需通過 tools/change_lane_gate.py 的嚴格白名單，不得夾帶產品檔案。
