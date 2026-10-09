---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工

## 硬閘門：`DISPATCH_REMOTE_ONLY`

**`/派工` 絕不能在使用者本機施工。** 其工作位置限於 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION` 的真正雲端／GitHub 端執行器（不得暗接使用者裝置）。禁止 Remote Desktop Commander、RC、CoreELEC、`whd-dev`、`/workspace/whd`、Windows `Z:\新WHD`、任何本機 shell／工作樹，用於本技能的修改、測試、commit、同步或備援。**禁止把 `/派工` 隱性改成 `/接手`。**

在讀取 GitHub 工單並確認依賴、scope、owner 後，**每次實際施工入口**先確認 executor 位置；本機／RC 一律回 `DISPATCH_LOCAL_EXECUTION_DENIED`，不得呼叫使用者裝置。本回合若沒有可執行的 GitHub／雲端施工入口，就記錄 `REMOTE_EXECUTOR_UNAVAILABLE` 和已查到的阻塞，保留工單，不得虛構「已派工」「已施工」，也不能因為 RC 上線便拿它代替。

符合遠端執行條件後，`/派工` 才能以 GitHub Git 為來源，在遠端隔離分支施工、跑驗證、commit，推送到公開倉庫 `looaeedr/whd` 的指定工作分支，建立 base=`localX` 的 PR，追蹤 exact CI，成功後合併 **GitHub 遠端 `localX`**，完成 Issue 留言／close/readback；**這不等於使用者本機 `localX` 已更新**。同一已核准 Issue 不額外要求退役專案 token、receipt、unlock，但外部平台安全審查不能由 Skill 繞過。

只有使用者明確下 `/接手`，才能切到 `執行開發任務/SKILL.md` 並使用 RC → `whd-dev` → `/workspace/whd`；`/派工` 本身不授權此切換。產品不得自動從 `localX` 發布 X；正式 `cleanup/2d-3d-sync` 仍須當次 `/推推`。純治理／技能變更照 `tools/change_lane_gate.py` 的白名單走獨立治理通道，不得藉此把產品或派工送入本機。

## 發出產品 PR 之後必須續作

1. `PR_OPEN / CI_QUEUED / CI_IN_PROGRESS / CI_PENDING` 一律 `CONTINUE_POLL`，**不是可結束的交付狀態**；在當前回合持續輪詢 exact PR SHA 與對應 run，不得把「正在測試」當成派工完成。
2. `CI_SUCCESS` 且 PR mergeable，應直接把工作 PR 合併至 `localX`；隨即讀回 `localX` HEAD、PR merged、Issue 最新狀態並於工單留言；完成後 close Issue 並再次 readback。整段不必使用者再喊「繼續」。
   **重要先後次序**：`localX` merge 成功 + GitHub SHA 回讀後，**立刻啟動 `NEXT_ISSUE_DISCOVERY_REQUIRED`**，同步完成原 Issue 留言／close/readback；**不得等 Issue CLOSED 才找下一張**，也不得以 Issue close/readback 為流程終點。
   搜尋下一張 OPEN 且前置工單已完成的可執行 Issue；檢查相同工作是否已有 owner/PR，避免重複；可施工就建立真實工作分支、寫入派工留言並繼續執行。找不到則輸出已核查清單與 `NO_ELIGIBLE_ISSUE`，不得假報成功派工。

3. `CI_FAILURE / CANCELLED / TIMED_OUT`：讀取 job/step/log，定位和修復後再次測試；若 run 完全缺席，先修正 workflow branch/path 接線並觸發，不得聲稱已驗收。
4. 回報至少每 2–3 次實質操作一次；回報不構成退出。只有**實際無法繼續的外部阻塞**或回合／工具限制造成無法續跑時，才能清楚報出已驗證 blocker、last exact PR/SHA 與下一步，**不可聲稱 DONE**。ChatGPT 回合結束後不會自行輪詢，除非另有正式排程。
5. 產品 `localX → X` 仍需使用者當次 `/推推`。不加新的 GitHub 分支保護、不恢復 Flow v2。
