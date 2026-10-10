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
排程規則及非產品治理文件，依 `AGENTS.md` 的治理直送通道，優先使用 GitHub／雲端的 `governance/*`、`docs/*` 或 `skills/*` 分支，經 `tools/change_lane_gate.py` 白名單確認後 PR 合併至 X，不經 localX，也不需要 `/推推`。未取得使用者當次明確的本機／DC 授權，不得為治理工作讀取或操作 CoreELEC、whd-dev 或本機 shell；雲端能力不足時應明確回報阻塞，不得自動轉向本機。產品／混合修改仍走 localX，發布 X 須當次 `/推推`。
