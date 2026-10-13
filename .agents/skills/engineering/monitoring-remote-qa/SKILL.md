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

本技能只負責 exact PR SHA 的 GitHub Actions run/job/check 讀取、RED 分析、GREEN 判定；不是另一層 DC 授權、不是另一份 QA，也不發布正式 X。`requested/queued/waiting/pending/in_progress` → `CONTINUE_POLL`；無 SHA 對應 → `RECONCILE_ONLY`；RED → `REPAIR_AND_RETEST`；GREEN → 讓本工單交付流程直接 `GITHUB_LOCALX_FIRST`，不重跑已 GREEN 測試。

## QA 輪詢與交付閘門

- 成功時核對 PR base=`localX`、工作 scope、mergeable、exact SHA 與最新 base 影響，GitHub 合併（`expected_head_sha`）後 readback `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`。**不先用 DC、不要求每張 PR 重複授權**。
- Windows `Z:\localX` fast-forward 與實際 GUI 人工驗收由使用者另行完成；沒本機回讀就不能報 `LOCALX_SYNCED` 或 UAT GREEN。
- GitHub 平台拒絕 merge／CI RED，記錄真實 blocker／job／run_id／SHA，不繞過外部審查或改用 DC。
- 合併後續行 Issue close/readback、下一張工單尋找；產品正式 X 仍限當次 `/推推`。
## QA 輪詢與交付閘門

- `queued / waiting / pending / in_progress` → **CONTINUE_POLL**。輪詢 exact SHA 的 checks + job；工作仍可執行時不得「CI 跑著就結束」；每 2–3 操作回報，不能用回報代替續作。
- `completed / success` → PR base=`localX`、工作分支與 exact SHA 綠燈核對後，**按當次授權選路**：① 同一 Issue／PR 已明確授權 GitHub-only 及不使用 DC → 不探測 DC，按 `GITHUB_ONLY_LOCALX_EXPLICIT_SCOPE_V1` 合併 GitHub `localX`，回讀 merged／remote HEAD，標 `GITHUB_ONLY_LOCALX_MERGED + LOCALX_SYNC_PENDING`；② **既有 `/派工` 同一 Issue／PR 且沒有當次 GitHub-only 覆寫（預設）** → 無須新合併指令，於 `LOCALX_INTEGRATION` 用 DC 僅安全整合本機 `localX`，完成必要驗證、非強制同步遠端及雙端 SHA readback 才標 `LOCALX_SYNCED`；③ DC 確實無法連線且有證據 → 依既有 `DC_UNREACHABLE` 斷線備援，不能假造失聯；④ 只禁止 DC 但未授權遠端合併 → 保持 `LOCALX_INTEGRATION_PENDING` 並說明真正缺口（不得假造遠端合併授權）。凡未實際驗證本機 HEAD，均不能宣稱本機已同步。之後依 Issue close/readback 及下一張工單查找續作；**CI GREEN 不是派工終點**。
- **`localX` merge + SHA 回讀即觸發 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，不等原工單 close；原工單回寫及結案與下一張搜尋銜接處理。可執行者直接續派並施工；若無候選須回報 `NO_ELIGIBLE_ISSUE` 和實際查核依據，不能把 CI/merge/close 當成停止條件。

- `completed / failure / cancelled / timed_out` → 檢查 logs，修復後重試，不得將其他 commit 的 GREEN 當成同一 HEAD。
- 沒有檢查結果 → 先核對 PR target 是否被 workflow branches/paths 覆蓋；不准以「無檢查」當成功。
- 真正不能繼續時提供 exact run/PR/SHA、已確認阻塞及續作動作，不得假稱背景輪詢已安排；未建立排程的聊天執行者不具跨回合自動喚醒能力。
