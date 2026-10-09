---
name: 寫排程
description: WHD 排程設計與管理，不要求原生工單交易流程。
whd_doc_role: CURRENT
whd_contract: scheduler-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /寫排程
既有排程保持獨立存在；按使用者授權變更排程內容或時間，不得自行新增或刪除排程。
執行單次任務可以直接讀 Issue 並施工，保留實質回報，不需要舊版 claim/slot/lease/transaction 機制。
排程規則及非產品治理文件可在本機 `governance/*` 分支直接修改、測試、提交 PR 並合併 X，前提是 `tools/change_lane_gate.py` 完整白名單通過；產品／混合修改仍整合 localX、需要使用者當次 `/推推`。
