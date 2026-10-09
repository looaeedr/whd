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

origin/localX 只允許作備份；將 localX 發布到正式 cleanup/2d-3d-sync 必須使用者當次明確 /推推，驗證 exact PR/SHA 與 tools/localx_publish_gate.py。
