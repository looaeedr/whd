---
name: monitoring-remote-qa
description: 讀取 GitHub Actions 測試結果並處理失敗，不使用控制交易。
whd_doc_role: CURRENT
whd_contract: monitoring-remote-qa-independent
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# monitoring-remote-qa
追蹤指定 PR 的 exact workflow run、commit 和測試結果；失敗時直接修程式並重測，不得將 pending 當 GREEN。普通產品 QA 不會自動發布正式 X；產品發布權限只來自使用者 /推推。純治理文檔/技能透過 tools/change_lane_gate.py 驗證，可不經一般產品 QA，直接治理分支 PR 合併 X。

## QA 輪詢與交付閘門

- `queued / waiting / pending / in_progress` → **CONTINUE_POLL**。輪詢 exact SHA 的 checks + job；工作仍可執行時不得「CI 跑著就結束」；每 2–3 操作回報，不能用回報代替續作。
- `completed / success` → 若 PR base 是 `localX`、工作分支及核准條件符合，立即合併、回讀 PR merged/branch SHA、工單 close/readback。**測試 GREEN 不是派工終點**。
- `completed / failure / cancelled / timed_out` → 檢查 logs，修復後重試，不得將其他 commit 的 GREEN 當成同一 HEAD。
- 沒有檢查結果 → 先核對 PR target 是否被 workflow branches/paths 覆蓋；不准以「無檢查」當成功。
- 真正不能繼續時提供 exact run/PR/SHA、已確認阻塞及續作動作，不得假稱背景輪詢已安排；未建立排程的聊天執行者不具跨回合自動喚醒能力。
