---
name: monitoring-remote-qa
description: 讀取 GitHub Actions 測試結果並處理失敗，不使用控制交易。
whd_doc_role: CURRENT
whd_contract: monitoring-remote-qa-independent
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# monitoring-remote-qa
追蹤指定 PR 的 exact workflow run、commit 和測試結果；失敗時直接修程式並重測，不得將 pending 當 GREEN。普通產品 QA 不會自動發布正式 X；產品發布權限只來自使用者 /推推。純治理文檔／技能可獨立跑治理 QA，但工作分支及 PR 仍以 GitHub `localX` 為 base；正式 X 只走使用者人工驗收及 `/推推` 發布 gate。

## 退出前 CI 狀態查核 `DISPATCH_TURN_EXIT_GATE_V1`

本技能只負責 exact PR SHA 的 GitHub Actions run/job/check 讀取、RED 分析、GREEN 判定；不是另一層 DC 授權、不是另一份 QA，也不發布正式 X。`requested/queued/waiting/pending/in_progress` → `CONTINUE_POLL`；無 SHA 對應 → `RECONCILE_ONLY`；RED → `REPAIR_AND_RETEST`；GREEN → 讓本工單交付流程直接 `GITHUB_LOCALX_FIRST`，不重跑已 GREEN 測試。

## QA 輪詢與交付閘門

- `queued / waiting / pending / in_progress` → `CONTINUE_POLL`。只輪詢 exact SHA 的 GitHub checks／jobs；每 2–3 次操作回報，回報不是停止訊號。
- `completed / success` → 核對 PR base=`localX`、工作 scope、head SHA、mergeable、必要 CI 與最新 base 差異；既有同工單施工授權即可依 `GITHUB_LOCALX_FIRST` 用 GitHub PR merge（`expected_head_sha`）整合遠端 `localX` 並 readback，標 `GITHUB_LOCALX_MERGED + WINDOWS_LOCALX_SYNC_PENDING`。**不先用 DC、不要求每張 PR 重複授權**；這不是 DC 斷線備援，也不需先試探 RC／CoreELEC。
- `completed / failure / cancelled / timed_out / action_required` → 查 exact run 的失敗 job／step／log，回原工作分支修復、更新 SHA 後重驗，不可沿用舊 GREEN。
- 沒有 exact SHA 的檢查結果 → 先核對 workflow branch／path 是否覆蓋；不得以「無檢查」當成功。
- GitHub 拒絕 merge／外部平台審查拒絕 → 回報真實 blocker，不改走 DC 或其他本機管道；只有使用者當次明確指定 DC 裝置／操作、外部核准才另依對應入口辦理，CI GREEN 本身不授權 DC。
- Windows `Z:\\localX` 由使用者 fast-forward 並人工 GUI／製造驗收。未實際讀到 Windows HEAD 不准標 `LOCALX_SYNCED`、UAT GREEN；沒有當次 `/推推` 不可發布 X。
- **`localX` merge + SHA 回讀即 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，不等原工單 close；繼續 Issue 留言、close/readback 與下一張工作搜尋，無候選標 `NO_ELIGIBLE_ISSUE`。
- 真正工具／權限／執行環境阻塞才回報 exact PR／run／SHA、`BLOCKED_WITH_EVIDENCE` 或 `RUNTIME_LIMIT_UNRESOLVED`；未建立排程的聊天不具背景輪詢能力。
