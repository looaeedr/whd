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
排程規則及非產品治理文件，依最新 GitHub `localX` exact HEAD `AGENTS.md` 與 CURRENT `寫技能`，從 `localX` 建 GitHub／雲端 `governance/*`、`docs/*` 或 `skills/*` 工作分支，經適用治理測試／CI 後 PR 合併 **`localX`**。正式 `X=cleanup/2d-3d-sync` 不論治理或產品均需使用者當次 `/推推` 與受信任 X gate，不能用 `GOVERNANCE_DIRECT_X` 分類繞過。沒有本次明確的 DC／RC 裝置與操作授權，不得為治理工作探測或操作本機；雲端能力不足時回報實際阻塞，不能自動轉本機。
