---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工
依使用者需求建立或讀取既有 Issue，確認 scope、工作分支及責任人。
能直接完成時直接修改、測試並整合至 localX；不可虛構已派出的代理人或未發生的提交。
若使用者下達 `/接手`，使用 RC → whd-dev → `/workspace/whd` 施工。
產品施工不得自動將 localX 發布至 X；必須使用者當次 `/推推`。純文檔／治理／技能工作不必派工，也不經 localX，可由本地治理分支直接 PR 合併 X，但必須通過 `tools/change_lane_gate.py` 的白名單硬檢查。

## 發出產品 PR 之後必須續作

1. `PR_OPEN / CI_QUEUED / CI_IN_PROGRESS / CI_PENDING` 一律 `CONTINUE_POLL`，**不是可結束的交付狀態**；在當前回合持續輪詢 exact PR SHA 與對應 run，不得把「正在測試」當成派工完成。
2. `CI_SUCCESS` 且 PR mergeable，應直接把工作 PR 合併至 `localX`；隨即讀回 `localX` HEAD、PR merged、Issue 最新狀態並於工單留言；完成後 close Issue 並再次 readback。整段不必使用者再喊「繼續」。
   **重要先後次序**：`localX` merge 成功 + GitHub SHA 回讀後，**立刻啟動 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，同步完成原 Issue 留言／close/readback；**不得等 Issue CLOSED 才找下一張**，也不得以 Issue close/readback 為流程終點。
   搜尋下一張 OPEN 且前置工單已完成的可執行 Issue；檢查相同工作是否已有 owner/PR，避免重複；可施工就建立真實工作分支、寫入派工留言並繼續執行。找不到則輸出已核查清單與 `NO_ELIGIBLE_ISSUE`，不得假報成功派工。

3. `CI_FAILURE / CANCELLED / TIMED_OUT`：讀取 job/step/log，定位和修復後再次測試；若 run 完全缺席，先修正 workflow branch/path 接線並觸發，不得聲稱已驗收。
4. 回報至少每 2–3 次實質操作一次；回報不構成退出。只有**實際無法繼續的外部阻塞**或回合／工具限制造成無法續跑時，才能清楚報出已驗證 blocker、last exact PR/SHA 與下一步，**不可聲稱 DONE**。ChatGPT 回合結束後不會自行輪詢，除非另有正式排程。
5. 產品 `localX → X` 仍需使用者當次 `/推推`。不加新的 GitHub 分支保護、不恢復 Flow v2。
