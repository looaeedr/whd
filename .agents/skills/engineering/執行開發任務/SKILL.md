---
name: 執行開發任務
description: 直接執行 WHD 開發任務，在 localX 整合測試，不使用舊治理狀態機。
whd_doc_role: CURRENT
whd_contract: development-task-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

使用使用者指定的 Issue 或明確開發任務，讀取 GitHub Git 與相關產品規格，在合法工作分支或本地 /workspace/whd 修改、測試、提交，再將成果整合至本地 localX。

使用者下達 /接手 時優先透過 Remote Desktop Commander → CoreELEC whd-dev → /workspace/whd 執行。不因缺少另一個 Agent、工作槽、狀態交易或工單接取紀錄而停止。

保留必要的產品測試、程式碼 review、現場 DXF 驗收，實際交付狀態以 Git HEAD 與 Issue/PR 反讀為準。

任何時候都不得自動將 localX 合併到正式 cleanup/2d-3d-sync；只有使用者當次明確 /推推 可以授權正式發布。
