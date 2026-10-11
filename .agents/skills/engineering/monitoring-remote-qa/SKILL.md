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

## 退出前 CI 狀態查核 `DISPATCH_TURN_EXIT_GATE_V1`

依 `.agents/contracts/WHD_DISPATCH_TURN_EXIT_GATE_V1.json` 做 exact PR HEAD 判斷：`requested/queued/waiting/pending/in_progress` 一律 `CONTINUE_POLL`；找不到 run 或 SHA 不符 `RECONCILE_ONLY`；同 SHA `completed/success` 必須續做 `LOCALX_INTEGRATION_PENDING`；`failure/cancelled/timed_out/action_required` → `REPAIR_AND_RETEST`。`localX` 整合後仍要完成 Issue 回讀和下一張工單查找 `CONTINUE_FINALIZATION`，不是 GREEN 即 `RELEASED`。只有真實 API/權限/環境阻塞時回報 `BLOCKED_WITH_EVIDENCE` 或 `RUNTIME_LIMIT_UNRESOLVED` 和 `head_sha/run_id/next_exact_action`，不得稱 DONE 或背景會繼續；本規則不具跨回合喚醒能力。

**整合路線先看使用者當次授權範圍，再決定是否可用 DC**：使用者對同一 Issue／PR 明確授權 GitHub-only 遠端 `localX` 合併且禁止 DC 時，exact HEAD CI SUCCESS 後直接走 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1`，**不得先試探、連線或要求 DC 斷線證據**；執行者自己在 PR 寫的「不使用 DC」不能代替使用者授權。若只禁止 DC、沒有遠端合併核准，保持 `LOCALX_INTEGRATION_PENDING` 並明列缺口；不可假記 `DC_UNREACHABLE`。

## QA 輪詢與交付閘門

- `queued / waiting / pending / in_progress` → **CONTINUE_POLL**。輪詢 exact SHA 的 checks + job；工作仍可執行時不得「CI 跑著就結束」；每 2–3 操作回報，不能用回報代替續作。
- `completed / success` → PR base=`localX`、工作分支與 exact SHA 綠燈核對後，**按當次授權選路**：① 同一 Issue／PR 已明確授權 GitHub-only 及不使用 DC → 不探測 DC，按 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1` 合併 GitHub `localX`，回讀 merged／remote HEAD，標 `GITHUB_ONLY_LOCALX_MERGED + LOCALX_SYNC_PENDING`；② 無 GitHub-only 授權但允許標準最終整合 → `/派工` 在 `LOCALX_INTEGRATION` 用 DC 僅整合本機 `localX`，驗證後非強制同步遠端；③ DC 確實無法連線且有證據 → 依既有 `DC_UNREACHABLE` 斷線備援，不能假造失聯；④ 只禁止 DC 但未授權遠端合併 → 停在 `LOCALX_INTEGRATION_PENDING`。凡未實際驗證本機 HEAD，均不能宣稱本機已同步。之後依 Issue close/readback 及下一張工單查找續作；**CI GREEN 不是派工終點**。
- **`localX` merge + SHA 回讀即觸發 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，不等原工單 close；原工單回寫及結案與下一張搜尋銜接處理。可執行者直接續派並施工；若無候選須回報 `NO_ELIGIBLE_ISSUE` 和實際查核依據，不能把 CI/merge/close 當成停止條件。

- `completed / failure / cancelled / timed_out` → 檢查 logs，修復後重試，不得將其他 commit 的 GREEN 當成同一 HEAD。
- 沒有檢查結果 → 先核對 PR target 是否被 workflow branches/paths 覆蓋；不准以「無檢查」當成功。
- 真正不能繼續時提供 exact run/PR/SHA、已確認阻塞及續作動作，不得假稱背景輪詢已安排；未建立排程的聊天執行者不具跨回合自動喚醒能力。
